import asyncio
import logging
import time
from typing import AsyncGenerator

from app.core.config import get_settings
from app.core.constants import EVALUATION_GROUNDING_INSTRUCTION, MESSAGES, get_message
from app.core.database import get_db_session
from app.external.api_factory import create_client
from app.schemas.evaluation import EvaluationRequest
from app.services.evaluation_prompt_service import get_evaluation_prompt
from app.services.model_selector import get_model_name
from app.services.sse_helpers import heartbeat_events, sse_error, sse_event
from app.services.usage_service import check_daily_limit
from app.utils.audit_logger import log_audit_event
from app.utils.input_sanitizer import sanitize_medical_text, validate_medical_input

settings = get_settings()

logger = logging.getLogger(__name__)

# サニタイズ対象の自由入力欄
_FREE_TEXT_FIELDS = (
    "input_text",
    "current_prescription",
    "additional_info",
    "output_summary",
)


def _validate_request(request: EvaluationRequest) -> None:
    """入力を検証（プロンプトインジェクション検出を含む）。問題があれば ValueError"""
    if not request.output_summary:
        raise ValueError(MESSAGES["VALIDATION"]["EVALUATION_NO_OUTPUT"])

    error_msg = validate_medical_input(
        request.output_summary, settings.max_input_tokens
    ) or validate_medical_input(request.input_text, settings.max_input_tokens)
    if error_msg:
        raise ValueError(error_msg)


def _get_prompt_template(document_type: str) -> str:
    """文書タイプの評価プロンプトをDBから取得。未設定なら ValueError"""
    with get_db_session() as db:
        prompt_data = get_evaluation_prompt(db, document_type)
        if not prompt_data:
            raise ValueError(
                get_message(
                    "VALIDATION",
                    "EVALUATION_PROMPT_NOT_SET",
                    document_type=document_type,
                )
            )
        return prompt_data.content


def build_evaluation_prompt(
    prompt_template: str,
    input_text: str,
    current_prescription: str,
    additional_info: str,
    output_summary: str,
) -> tuple[str, str]:
    """評価用の (システムプロンプト, ユーザープロンプト) を構築"""
    system_prompt = f"{prompt_template.strip()}\n\n{EVALUATION_GROUNDING_INSTRUCTION}"
    user_prompt = f"""<カルテ記載>
{input_text}
</カルテ記載>

<現在の処方>
{current_prescription}
</現在の処方>

<追加情報>
{additional_info}
</追加情報>

<生成された出力>
{output_summary}
</生成された出力>"""
    return system_prompt, user_prompt


def _log_failure(
    request: EvaluationRequest, user_ip: str | None, error_message: str
) -> None:
    log_audit_event(
        event_type=MESSAGES["AUDIT"]["EVALUATION_FAILURE"],
        user_ip=user_ip,
        document_type=request.document_type,
        success=False,
        error_message=error_message,
    )


async def execute_evaluation_stream(
    request: EvaluationRequest, user_ip: str | None = None
) -> AsyncGenerator[str, None]:
    """SSEストリーミングで評価を実行"""
    log_audit_event(
        event_type=MESSAGES["AUDIT"]["EVALUATION_START"],
        user_ip=user_ip,
        document_type=request.document_type,
    )

    limit_error = check_daily_limit()
    if limit_error:
        yield sse_error(limit_error)
        return

    request = request.model_copy(
        update={
            field: sanitize_medical_text(getattr(request, field))
            for field in _FREE_TEXT_FIELDS
        }
    )

    # いずれの失敗も ValueError のメッセージをそのままユーザーに返す
    try:
        _validate_request(request)
        model_name = get_model_name(settings.evaluation_model)
        prompt_template = _get_prompt_template(request.document_type)
    except ValueError as e:
        _log_failure(request, user_ip, str(e))
        yield sse_error(str(e))
        return

    system_prompt, user_prompt = build_evaluation_prompt(
        prompt_template,
        request.input_text,
        request.current_prescription,
        request.additional_info,
        request.output_summary,
    )

    start_time = time.time()
    # クライアント生成とAPI呼び出しは同期処理のため、スレッドで実行してイベントループを塞がない
    task = asyncio.create_task(
        asyncio.to_thread(
            lambda: create_client(settings.evaluation_model).generate(
                user_prompt, model_name, system_prompt
            )
        )
    )
    async for event in heartbeat_events(
        task,
        start_message=MESSAGES["STATUS"]["EVALUATION_START"],
        running_status="evaluating",
        running_message=MESSAGES["STATUS"]["EVALUATING"],
        elapsed_message_template=MESSAGES["STATUS"]["EVALUATING_ELAPSED"],
    ):
        yield event

    try:
        evaluation_text, input_tokens, output_tokens = task.result()
    except Exception as e:
        # 例外詳細はサーバーログのみに記録（外部APIの例外文字列に入力断片が含まれる可能性があるため）
        logger.error("評価API呼び出しエラー", exc_info=True)
        _log_failure(request, user_ip, type(e).__name__)
        yield sse_error(MESSAGES["ERROR"]["EVALUATION_ERROR"])
        return

    processing_time = time.time() - start_time
    log_audit_event(
        event_type=MESSAGES["AUDIT"]["EVALUATION_SUCCESS"],
        user_ip=user_ip,
        document_type=request.document_type,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        processing_time=processing_time,
    )

    yield sse_event(
        "complete",
        {
            "success": True,
            "evaluation_result": evaluation_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "processing_time": processing_time,
        },
    )
