import asyncio
import logging
import time
from typing import AsyncGenerator

from app.core.config import get_settings
from app.core.constants import MESSAGES
from app.external.api_factory import create_client
from app.schemas.summary import SummaryRequest
from app.services.model_selector import determine_model, get_model_name
from app.services.sse_helpers import heartbeat_events, sse_error, sse_event
from app.services.usage_service import check_daily_limit, save_usage
from app.utils.audit_logger import log_audit_event
from app.utils.input_sanitizer import sanitize_medical_text, validate_medical_input
from app.utils.text_processor import format_output_summary, parse_output_summary

settings = get_settings()

logger = logging.getLogger(__name__)

# サニタイズ対象の自由入力欄
_FREE_TEXT_FIELDS = (
    "medical_text",
    "additional_info",
    "current_prescription",
    "previous_summary",
    "evaluation_feedback",
)


def validate_input(medical_text: str) -> str | None:
    """テキスト入力を検証し、問題があればエラーメッセージを返す。問題なければNone"""
    if not medical_text or not medical_text.strip():
        return MESSAGES["VALIDATION"]["NO_INPUT"]

    # min_input_tokens / max_input_tokens は設定名に反して文字数として比較する
    input_length = len(medical_text.strip())
    if input_length < settings.min_input_tokens:
        return MESSAGES["VALIDATION"]["INPUT_TOO_SHORT"]
    if input_length > settings.max_input_tokens:
        return MESSAGES["VALIDATION"]["INPUT_TOO_LONG"]

    # プロンプトインジェクション検出（文字数上限は上で検査済み）
    return validate_medical_input(medical_text)


def _sanitize_request(request: SummaryRequest) -> SummaryRequest:
    """自由入力欄をサニタイズしたリクエストを返す"""
    return request.model_copy(
        update={
            field: sanitize_medical_text(getattr(request, field))
            for field in _FREE_TEXT_FIELDS
        }
    )


def _log_failure(
    request: SummaryRequest, user_ip: str | None, model: str, error_message: str
) -> None:
    log_audit_event(
        event_type=MESSAGES["AUDIT"]["DOCUMENT_GENERATION_FAILURE"],
        user_ip=user_ip,
        document_type=request.document_type,
        model=model,
        success=False,
        error_message=error_message,
    )


def _complete_event(
    request: SummaryRequest,
    user_ip: str | None,
    final_model: str,
    model_switched: bool,
    generated: tuple[str, int, int],
    processing_time: float,
) -> str:
    """生成結果を整形・記録し、SSEのcompleteイベントを生成"""
    output_summary, input_tokens, output_tokens = generated
    formatted_summary = format_output_summary(output_summary)

    save_usage(
        department=request.department,
        doctor=request.doctor,
        document_type=request.document_type,
        model=final_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        processing_time=processing_time,
    )
    log_audit_event(
        event_type=MESSAGES["AUDIT"]["DOCUMENT_GENERATION_SUCCESS"],
        user_ip=user_ip,
        document_type=request.document_type,
        model=final_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        processing_time=processing_time,
    )

    return sse_event(
        "complete",
        {
            "success": True,
            "output_summary": formatted_summary,
            "parsed_summary": parse_output_summary(formatted_summary),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "processing_time": processing_time,
            "model_used": final_model,
            "model_switched": model_switched,
        },
    )


async def execute_summary_generation_stream(
    request: SummaryRequest, user_ip: str | None = None
) -> AsyncGenerator[str, None]:
    """SSEストリーミングで文書生成を実行"""
    log_audit_event(
        event_type=MESSAGES["AUDIT"]["DOCUMENT_GENERATION_START"],
        user_ip=user_ip,
        document_type=request.document_type,
        model=request.model,
        department=request.department,
        doctor=request.doctor,
    )

    limit_error = check_daily_limit()
    if limit_error:
        yield sse_error(limit_error)
        return

    request = _sanitize_request(request)

    error_msg = validate_input(request.medical_text)
    if error_msg:
        _log_failure(request, user_ip, request.model, error_msg)
        yield sse_error(error_msg)
        return

    total_length = len(request.medical_text) + len(request.additional_info)
    try:
        final_model, model_switched = determine_model(
            request.model,
            total_length,
            request.department,
            request.document_type,
            request.doctor,
            request.model_explicitly_selected,
        )
        model_name = get_model_name(final_model)
    except ValueError as e:
        _log_failure(request, user_ip, request.model, type(e).__name__)
        yield sse_error(str(e))
        return

    start_time = time.time()
    # クライアント生成とAPI呼び出しは同期処理のため、スレッドで実行してイベントループを塞がない
    task = asyncio.create_task(
        asyncio.to_thread(
            lambda: create_client(final_model).generate_summary(request, model_name)
        )
    )
    async for event in heartbeat_events(
        task,
        start_message=MESSAGES["STATUS"]["DOCUMENT_GENERATION_START"],
        running_status="generating",
        running_message=MESSAGES["STATUS"]["DOCUMENT_GENERATING"],
        elapsed_message_template=MESSAGES["STATUS"]["DOCUMENT_GENERATING_ELAPSED"],
    ):
        yield event

    try:
        generated = task.result()
    except Exception as e:
        # 例外詳細はサーバーログのみに記録（外部APIの例外文字列に入力断片が含まれる可能性があるため）
        logger.error("文書生成API呼び出しエラー", exc_info=True)
        _log_failure(request, user_ip, final_model, type(e).__name__)
        yield sse_error(MESSAGES["ERROR"]["API_ERROR"])
        return

    yield _complete_event(
        request,
        user_ip,
        final_model,
        model_switched,
        generated,
        processing_time=time.time() - start_time,
    )
