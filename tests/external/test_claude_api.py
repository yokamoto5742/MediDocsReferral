"""ClaudeAPIClient のテスト"""

import socket
from unittest.mock import MagicMock, patch

import pytest
from anthropic import omit
from anthropic.types import TextBlock

from app.core.constants import CLAUDE_GENERATION_TEMPERATURE, MESSAGES
from app.external.claude_api import ClaudeAPIClient
from app.schemas.summary import SummaryRequest
from app.utils.exceptions import APIError


def create_response(text: str | None, input_tokens: int = 100, output_tokens: int = 50):
    """テスト用のレスポンスモックを作成（text=None の場合は content が空）"""
    response = MagicMock()
    response.content = [] if text is None else [TextBlock(type="text", text=text)]
    response.stop_reason = "end_turn"
    response.usage.input_tokens = input_tokens
    response.usage.output_tokens = output_tokens
    return response


@pytest.fixture
def mock_bedrock():
    """AnthropicBedrock と設定をモックし、Bedrock クライアントのモックを返す"""
    with (
        patch("app.external.claude_api.get_settings") as mock_get_settings,
        patch("app.external.claude_api.AnthropicBedrock") as mock_bedrock_class,
    ):
        mock_get_settings.return_value.aws_region = "ap-northeast-1"
        yield mock_bedrock_class


class TestClaudeAPIClientInitialization:
    """ClaudeAPIClient 初期化のテスト"""

    def test_init_creates_bedrock_client(self, mock_bedrock):
        """初期化 - 設定のリージョンで Bedrock クライアントを生成（認証情報はIAMロール等から解決）"""
        client = ClaudeAPIClient()

        assert client.client is mock_bedrock.return_value
        mock_bedrock.assert_called_once_with(aws_region="ap-northeast-1")

    @pytest.mark.parametrize(
        "error",
        [Exception("認証エラー"), ConnectionError("ネットワーク接続エラー")],
    )
    def test_init_bedrock_error(self, mock_bedrock, error):
        """初期化 - AnthropicBedrock の生成に失敗した場合は APIError"""
        mock_bedrock.side_effect = error

        with pytest.raises(APIError) as exc_info:
            ClaudeAPIClient()

        assert "Amazon Bedrock Claude API初期化エラー" in str(exc_info.value)
        assert str(error) in str(exc_info.value)


class TestClaudeAPIClientGenerate:
    """ClaudeAPIClient generate メソッドのテスト"""

    def test_generate_success(self, mock_bedrock):
        """generate - 正常系"""
        create = mock_bedrock.return_value.messages.create
        create.return_value = create_response("生成されたサマリー", 1500, 800)

        result = ClaudeAPIClient().generate(
            prompt="テストプロンプト", model_name="claude-3-5-sonnet-20241022"
        )

        assert result == ("生成されたサマリー", 1500, 800)
        create.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            max_tokens=6000,
            system=omit,
            messages=[{"role": "user", "content": "テストプロンプト"}],
            extra_body={"temperature": CLAUDE_GENERATION_TEMPERATURE},
        )

    def test_generate_with_system_prompt(self, mock_bedrock):
        """generate - システムプロンプト指定"""
        create = mock_bedrock.return_value.messages.create
        create.return_value = create_response("生成されたサマリー")

        ClaudeAPIClient().generate(
            prompt="ユーザープロンプト",
            model_name="claude-3-5-sonnet-20241022",
            system_prompt="システムプロンプト",
        )

        assert create.call_args[1]["system"] == "システムプロンプト"

    def test_generate_truncated_output(self, mock_bedrock):
        """generate - max_tokens到達時に警告を付加"""
        response = create_response("途中で切れた文書", 1500, 6000)
        response.stop_reason = "max_tokens"
        mock_bedrock.return_value.messages.create.return_value = response

        summary_text, _, _ = ClaudeAPIClient().generate(
            prompt="テストプロンプト", model_name="claude-3-5-sonnet-20241022"
        )

        assert summary_text.startswith("途中で切れた文書")
        assert MESSAGES["WARNING"]["OUTPUT_TRUNCATED"] in summary_text

    def test_generate_empty_response(self, mock_bedrock):
        """generate - content が空の応答は成功扱いにせず APIError"""
        mock_bedrock.return_value.messages.create.return_value = create_response(None)

        with pytest.raises(APIError) as exc_info:
            ClaudeAPIClient().generate(prompt="テスト", model_name="test-model")

        assert str(exc_info.value) == MESSAGES["ERROR"]["EMPTY_RESPONSE"]

    def test_generate_no_text_block(self, mock_bedrock):
        """generate - TextBlock 以外のブロックのみの応答は APIError"""
        response = create_response(None)
        response.content = [MagicMock(spec=[])]
        mock_bedrock.return_value.messages.create.return_value = response

        with pytest.raises(APIError) as exc_info:
            ClaudeAPIClient().generate(prompt="テスト", model_name="test-model")

        assert str(exc_info.value) == MESSAGES["ERROR"]["EMPTY_RESPONSE"]

    @pytest.mark.parametrize(
        "error",
        [
            Exception("API接続エラー"),
            socket.timeout("接続タイムアウト"),
            ConnectionResetError("接続がリセットされました"),
            Exception("503 Service Unavailable"),
            Exception("rate limit exceeded"),
        ],
    )
    def test_generate_api_error(self, mock_bedrock, error):
        """generate - API呼び出しの例外は APIError にラップされる"""
        mock_bedrock.return_value.messages.create.side_effect = error

        with pytest.raises(APIError) as exc_info:
            ClaudeAPIClient().generate(prompt="テストプロンプト", model_name="test-model")

        error_message = str(exc_info.value)
        assert "Amazon Bedrock Claude API呼び出しエラー" in error_message
        assert str(error) in error_message
        assert exc_info.value.__cause__ is error

    @pytest.mark.parametrize(
        "prompt",
        ["あ" * 100000, "特殊文字: \n\t\r\n!@#$%^&*(){}[]<>?/\\|`~"],
        ids=["long", "special_characters"],
    )
    def test_generate_passes_prompt_as_is(self, mock_bedrock, prompt):
        """generate - 長文や特殊文字を含むプロンプトをそのまま渡す"""
        create = mock_bedrock.return_value.messages.create
        create.return_value = create_response("結果")

        result = ClaudeAPIClient().generate(prompt=prompt, model_name="test-model")

        assert result[0] == "結果"
        assert create.call_args[1]["messages"] == [{"role": "user", "content": prompt}]


class TestClaudeAPIClientIntegration:
    """ClaudeAPIClient 統合テスト"""

    @patch("app.external.base_api.get_prompt", return_value=None)
    @patch("app.external.base_api.get_db_session")
    def test_full_generate_summary_flow(
        self, _mock_db_session, _mock_get_prompt, mock_bedrock
    ):
        """完全な文書生成フロー"""
        create = mock_bedrock.return_value.messages.create
        create.return_value = create_response("生成された診療情報提供書", 2000, 1000)

        result = ClaudeAPIClient().generate_summary(
            SummaryRequest(
                medical_text="患者情報",
                additional_info="追加情報",
                current_prescription="処方内容",
                document_type="他院への紹介",
            ),
            "claude-3-5-sonnet-20241022",
        )

        assert result == ("生成された診療情報提供書", 2000, 1000)
        call_kwargs = create.call_args[1]
        assert call_kwargs["model"] == "claude-3-5-sonnet-20241022"
        assert "患者情報" in call_kwargs["messages"][0]["content"]
