import json
from typing import Any

from google import genai
from google.genai import interactions
from google.oauth2 import service_account

from app.core.config import get_settings
from app.core.constants import MESSAGES, get_message
from app.external.base_api import BaseAPIClient
from app.utils.exceptions import APIError


class GeminiAPIClient(BaseAPIClient):
    """Gemini API クライアント"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = self._create_client()

    def _create_client(self) -> genai.Client:
        try:
            if not self.settings.google_project_id:
                raise APIError(MESSAGES["CONFIG"]["VERTEX_AI_PROJECT_MISSING"])

            google_credentials_json = self.settings.google_credentials_json

            if google_credentials_json:
                try:
                    credentials_dict = json.loads(google_credentials_json)

                    credentials = service_account.Credentials.from_service_account_info(
                        credentials_dict,
                        scopes=['https://www.googleapis.com/auth/cloud-platform']
                    )

                    return genai.Client(
                        vertexai=True,
                        project=self.settings.google_project_id,
                        location=self.settings.google_location,
                        credentials=credentials
                    )

                except json.JSONDecodeError as e:
                    raise APIError(get_message("ERROR", "VERTEX_AI_CREDENTIALS_JSON_PARSE_ERROR", error=str(e)))
                except KeyError as e:
                    raise APIError(get_message("ERROR", "VERTEX_AI_CREDENTIALS_FIELD_MISSING", error=str(e)))
                except Exception as e:
                    raise APIError(get_message("ERROR", "VERTEX_AI_CREDENTIALS_ERROR", error=str(e)))

            # 認証情報JSONが未設定の場合はアプリケーションのデフォルト認証情報を使う
            return genai.Client(
                vertexai=True,
                project=self.settings.google_project_id,
                location=self.settings.google_location,
            )
        except APIError:
            raise
        except Exception as e:
            raise APIError(get_message("ERROR", "VERTEX_AI_INIT_ERROR", error=str(e)))

    def _thinking_level(self) -> str:
        return "low" if self.settings.gemini_thinking_level == "LOW" else "high"

    def generate(
        self, prompt: str, model_name: str, system_prompt: str = ""
    ) -> tuple[str, int, int]:
        request: dict[str, Any] = {
            "model": model_name,
            "input": prompt,
            "generation_config": {"thinking_level": self._thinking_level()},
            # 患者情報を含むためサーバー側に保存しない
            "store": False,
        }
        if system_prompt:
            request["system_instruction"] = system_prompt

        # クライアントへの配信は完了時の1回だけなので、ストリーミングAPIは使わない
        try:
            interaction = self.client.interactions.create(**request)
        except Exception as e:
            raise APIError(
                get_message("ERROR", "VERTEX_AI_API_ERROR", error=str(e))
            ) from e

        if not isinstance(interaction, interactions.Interaction):
            raise APIError(MESSAGES["ERROR"]["GEMINI_UNEXPECTED_RESPONSE"])

        input_tokens, output_tokens = _token_counts(interaction.usage)
        return interaction.output_text or "", input_tokens, output_tokens


def _token_counts(usage: interactions.Usage | None) -> tuple[int, int]:
    """(入力トークン数, 出力トークン数) を返す"""
    if usage is None:
        return 0, 0
    return usage.total_input_tokens or 0, usage.total_output_tokens or 0
