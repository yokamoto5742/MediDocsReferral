from anthropic import AnthropicBedrock, omit  # type: ignore[attr-defined]
from anthropic.types import TextBlock

from app.core.config import get_settings
from app.core.constants import CLAUDE_GENERATION_TEMPERATURE, MESSAGES, get_message
from app.external.base_api import BaseAPIClient
from app.utils.exceptions import APIError


class ClaudeAPIClient(BaseAPIClient):
    def __init__(self) -> None:
        try:
            # 認証情報は boto3 の既定の認証チェーン (環境変数・IAMロール) から解決される
            self.client = AnthropicBedrock(aws_region=get_settings().aws_region)
        except Exception as e:
            raise APIError(
                get_message("ERROR", "BEDROCK_INIT_ERROR", error=str(e))
            ) from e

    def generate(
        self, prompt: str, model_name: str, system_prompt: str = ""
    ) -> tuple[str, int, int]:
        try:
            response = self.client.messages.create(
                model=model_name,
                max_tokens=6000,
                system=system_prompt or omit,
                messages=[{"role": "user", "content": prompt}],
                # anthropic SDK 1.x で temperature 引数が削除されたため extra_body で送信する
                extra_body={"temperature": CLAUDE_GENERATION_TEMPERATURE},
            )
        except Exception as e:
            raise APIError(
                get_message("ERROR", "BEDROCK_API_ERROR", error=str(e))
            ) from e

        summary_text = next(
            (
                block.text
                for block in response.content or []
                if isinstance(block, TextBlock)
            ),
            "",
        )
        # 空の応答を成功扱いにすると、エラー文言が生成結果として表示・計上されてしまう
        if not summary_text:
            raise APIError(MESSAGES["ERROR"]["EMPTY_RESPONSE"])

        # max_tokens到達で途中終了した場合はユーザーに分かるよう警告を付加
        if response.stop_reason == "max_tokens":
            summary_text += "\n\n" + MESSAGES["WARNING"]["OUTPUT_TRUNCATED"]

        return summary_text, response.usage.input_tokens, response.usage.output_tokens
