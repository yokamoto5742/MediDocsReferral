import json
from typing import Tuple

import httpx
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from app.core.config import get_settings
from app.core.constants import MESSAGES
from app.external.base_api import BaseAPIClient
from app.utils.exceptions import APIError


class CloudflareClaudeAPIClient(BaseAPIClient):
    """Cloudflare AI Gateway経由でAmazon Bedrock Claude APIに接続するクライアント"""

    def __init__(self, model_name: str | None = None):
        settings = get_settings()
        model = model_name or settings.anthropic_model
        super().__init__(None, model)
        self.settings = settings
        self.aws_access_key_id = settings.aws_access_key_id
        self.aws_secret_access_key = settings.aws_secret_access_key
        self.aws_region = settings.aws_region

    def initialize(self) -> bool:
        try:
            if not all([
                self.settings.cloudflare_account_id,
                self.settings.cloudflare_gateway_id,
                self.settings.cloudflare_aig_token,
            ]):
                raise APIError(MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"])

            if not all([
                self.aws_access_key_id,
                self.aws_secret_access_key,
                self.aws_region,
            ]):
                raise APIError(MESSAGES["CONFIG"]["AWS_CREDENTIALS_MISSING"])

            if not self.default_model:
                raise APIError(MESSAGES["CONFIG"]["ANTHROPIC_MODEL_MISSING"])

            return True
        except APIError:
            raise
        except Exception as e:
            raise APIError(MESSAGES["ERROR"]["BEDROCK_INIT_ERROR"].format(error=str(e)))

    def _generate_content(self, prompt: str, model_name: str) -> Tuple[str, int, int]:
        try:
            if not all([
                self.settings.cloudflare_account_id,
                self.settings.cloudflare_gateway_id,
                self.settings.cloudflare_aig_token,
            ]):
                raise APIError(MESSAGES["ERROR"]["CLOUDFLARE_GATEWAY_NOT_INITIALIZED"])

            request_body = {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": 6000
                }
            }

            body_str = json.dumps(request_body)

            # Bedrock URL（署名用）
            stock_url = (
                f"https://bedrock-runtime.{self.aws_region}.amazonaws.com"
                f"/model/{model_name}/converse"
            )

            # AWS SigV4署名
            credentials = Credentials(
                access_key=self.aws_access_key_id,
                secret_key=self.aws_secret_access_key
            )

            headers = {
                "Content-Type": "application/json",
            }

            request = AWSRequest(
                method="POST",
                url=stock_url,
                data=body_str,
                headers=headers
            )

            SigV4Auth(credentials, "bedrock", self.aws_region).add_auth(request)

            # Cloudflare AI Gateway URL
            gateway_url = (
                f"https://gateway.ai.cloudflare.com/v1/"
                f"{self.settings.cloudflare_account_id}/"
                f"{self.settings.cloudflare_gateway_id}/"
                f"aws-bedrock/bedrock-runtime/{self.aws_region}/"
                f"model/{model_name}/converse"
            )

            # Cloudflare認証ヘッダーを追加
            final_headers = dict(request.headers)
            final_headers["cf-aig-authorization"] = f"Bearer {self.settings.cloudflare_aig_token}"

            response = httpx.post(
                gateway_url,
                headers=final_headers,
                content=body_str,
                timeout=120.0
            )
            response.raise_for_status()

            response_data = response.json()

            # レスポンスからテキストを抽出
            result_text = ""
            if "output" in response_data and "message" in response_data["output"]:
                message = response_data["output"]["message"]
                if "content" in message and message["content"]:
                    for content_block in message["content"]:
                        if "text" in content_block:
                            result_text = content_block["text"]
                            break

            if not result_text:
                result_text = MESSAGES["ERROR"]["EMPTY_RESPONSE"]

            # トークン数を抽出
            input_tokens = 0
            output_tokens = 0

            if "usage" in response_data:
                usage = response_data["usage"]
                input_tokens = usage.get("inputTokens", 0)
                output_tokens = usage.get("outputTokens", 0)

            return result_text, input_tokens, output_tokens

        except httpx.HTTPStatusError as e:
            raise APIError(
                MESSAGES["ERROR"]["CLOUDFLARE_GATEWAY_API_ERROR"].format(
                    error=f"HTTP {e.response.status_code}: {e.response.text}"
                )
            )
        except Exception as e:
            raise APIError(MESSAGES["ERROR"]["CLOUDFLARE_GATEWAY_API_ERROR"].format(error=str(e)))
