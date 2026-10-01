from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_client_ip
from app.schemas.summary import SummaryRequest
from app.services.model_selector import get_available_models
from app.services.sse_helpers import SSE_HEADERS
from app.services.summary_service import execute_summary_generation_stream

# 公開ルーター(読み取り専用、CSRF保護なし)
public_router = APIRouter(prefix="/summary", tags=["summary"])

# CSRF保護ありのルーター
router = APIRouter(prefix="/summary", tags=["summary"])


@router.post("/generate-stream")
async def generate_summary_stream(
    request: SummaryRequest, user_ip: str | None = Depends(get_client_ip)
):
    """SSEストリーミング文書生成API"""
    return StreamingResponse(
        execute_summary_generation_stream(request, user_ip),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@public_router.get("/models")
def list_available_models():
    """利用可能なモデル一覧を取得"""
    models = get_available_models()
    return {
        "available_models": models,
        "default_model": models[0] if models else None,
    }
