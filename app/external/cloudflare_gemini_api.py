from typing import Tuple

import httpx

from app.core.config import get_settings
from app.core.constants import MESSAGES
from app.external.base_api import BaseAPIClient
from app.utils.exceptions import APIError


class CloudflareGeminiAPIClient(BaseAPIClient):
    """Cloudflare AI Gateway経由でVertex AI Gemini APIに接続するクライアント"""

    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        model = model_name or settings.gemini_model
        super().__init__(None, model)
        self.settings = settings

    def initialize(self) -> bool:
        try:
            if not all([
                self.settings.cloudflare_account_id,
                self.settings.cloudflare_gateway_id,
                self.settings.cloudflare_aig_token,
            ]):
                raise APIError(MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"])

            if not self.settings.google_project_id:
                raise APIError(MESSAGES["CONFIG"]["VERTEX_AI_PROJECT_MISSING"])

            return True
        except APIError:
            raise
        except Exception as e:
            raise APIError(MESSAGES["ERROR"]["VERTEX_AI_INIT_ERROR"].format(error=str(e)))

    def _generate_content(self, prompt: str, model_name: str) -> Tuple[str, int, int]:
        try:
            if not all([
                self.settings.cloudflare_account_id,
                self.settings.cloudflare_gateway_id,
                self.settings.cloudflare_aig_token,
            ]):
                raise APIError(MESSAGES["ERROR"]["CLOUDFLARE_GATEWAY_NOT_INITIALIZED"])

            base_url = (
                f"https://gateway.ai.cloudflare.com/v1/"
                f"{self.settings.cloudflare_account_id}/"
                f"{self.settings.cloudflare_gateway_id}/"
                f"google-vertex-ai/v1/projects/{self.settings.google_project_id}/"
                f"locations/{self.settings.google_location}/"
                f"publishers/google/models/{model_name}:generateContent"
            )

            headers = {
                "cf-aig-authorization": f"Bearer {self.settings.cloudflare_aig_token}",
                "Content-Type": "application/json",
            }

            thinking_level = (
                "LOW"
                if self.settings.gemini_thinking_level == "LOW"
                else "HIGH"
            )

            request_body = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "thinkingConfig": {
                        "thinkingLevel": thinking_level
                    }
                }
            }

            response = httpx.post(
                base_url,
                headers=headers,
                json=request_body,
                timeout=120.0
            )
            response.raise_for_status()

            response_data = response.json()

            result_text = ""
            if "candidates" in response_data and response_data["candidates"]:
                candidate = response_data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    parts = candidate["content"]["parts"]
                    if parts and "text" in parts[0]:
                        result_text = parts[0]["text"]

            if not result_text:
                result_text = MESSAGES["ERROR"]["EMPTY_RESPONSE"]

            input_tokens = 0
            output_tokens = 0

            if "usageMetadata" in response_data:
                metadata = response_data["usageMetadata"]
                input_tokens = metadata.get("promptTokenCount", 0)
                output_tokens = metadata.get("candidatesTokenCount", 0)

            return result_text, input_tokens, output_tokens

        except httpx.HTTPStatusError as e:
            raise APIError(
                MESSAGES["ERROR"]["CLOUDFLARE_GATEWAY_API_ERROR"].format(
                    error=f"HTTP {e.response.status_code}: {e.response.text}"
                )
            )
        except Exception as e:
            raise APIError(MESSAGES["ERROR"]["CLOUDFLARE_GATEWAY_API_ERROR"].format(error=str(e)))
