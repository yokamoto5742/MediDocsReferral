import logging

from app.core.constants import MESSAGES, ModelType, get_message
from app.external.base_api import BaseAPIClient
from app.external.claude_api import ClaudeAPIClient
from app.external.gemini_api import GeminiAPIClient
from app.utils.exceptions import APIError

logger = logging.getLogger(__name__)


def create_client(model: str) -> BaseAPIClient:
    """モデル種別 (ModelType) に応じたクライアントを生成"""
    if model == ModelType.GEMINI:
        logger.info(MESSAGES["LOG"]["CLIENT_DIRECT_GEMINI"])
        return GeminiAPIClient()

    if model == ModelType.CLAUDE:
        logger.info(MESSAGES["LOG"]["CLIENT_DIRECT_CLAUDE"])
        return ClaudeAPIClient()

    raise APIError(get_message("ERROR", "UNSUPPORTED_API_PROVIDER", provider=model))
