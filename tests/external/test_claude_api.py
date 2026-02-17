"""ClaudeAPIClient のテスト"""

import os
from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import TextBlock

from app.core.constants import MESSAGES
from app.external.claude_api import ClaudeAPIClient
from app.utils.exceptions import APIError


class TestClaudeAPIClientInitialization:
    """ClaudeAPIClient 初期化のテスト"""

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_access_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret_key",
            "AWS_REGION": "ap-northeast-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_init_with_environment_variables(self):
        """初期化 - 環境変数から設定取得"""
        client = ClaudeAPIClient()

        assert client.aws_access_key_id == "test_access_key"
        assert client.aws_secret_access_key == "test_secret_key"
        assert client.aws_region == "ap-northeast-1"
        assert client.anthropic_model == "claude-3-5-sonnet-20241022"
        assert client.default_model == "claude-3-5-sonnet-20241022"
        assert client.client is None

    @patch.dict(os.environ, {}, clear=True)
    def test_init_without_environment_variables(self):
        """初期化 - 環境変数なし"""
        client = ClaudeAPIClient()

        assert client.aws_access_key_id is None
        assert client.aws_secret_access_key is None
        assert client.aws_region is None
        assert client.anthropic_model is None


class TestClaudeAPIClientInitialize:
    """ClaudeAPIClient initialize メソッドのテスト"""

    @patch("app.external.claude_api.AnthropicBedrock")
    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key_id",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_initialize_success(self, mock_anthropic_bedrock):
        """initialize - 正常系"""
        mock_client = MagicMock()
        mock_anthropic_bedrock.return_value = mock_client

        client = ClaudeAPIClient()
        result = client.initialize()

        assert result is True
        assert client.client is mock_client

        # AnthropicBedrock が正しい引数で呼ばれたことを確認
        mock_anthropic_bedrock.assert_called_once_with(
            aws_access_key="test_key_id",
            aws_secret_key="test_secret",
            aws_region="us-east-1",
        )

    @patch.dict(
        os.environ,
        {
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
        clear=True,
    )
    def test_initialize_missing_access_key_id(self):
        """initialize - AWS_ACCESS_KEY_ID 未設定"""
        client = ClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()

        assert "AWS認証情報が設定されていません" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
        clear=True,
    )
    def test_initialize_missing_secret_access_key(self):
        """initialize - AWS_SECRET_ACCESS_KEY 未設定"""
        client = ClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()

        assert "AWS認証情報が設定されていません" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
        clear=True,
    )
    def test_initialize_missing_region(self):
        """initialize - AWS_REGION 未設定"""
        client = ClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()

        assert "AWS認証情報が設定されていません" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
        },
        clear=True,
    )
    def test_initialize_missing_anthropic_model(self):
        """initialize - ANTHROPIC_MODEL 未設定"""
        client = ClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()

        assert "ANTHROPIC_MODELが設定されていません" in str(exc_info.value)

    @patch("app.external.claude_api.AnthropicBedrock")
    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_initialize_anthropic_bedrock_error(self, mock_anthropic_bedrock):
        """initialize - AnthropicBedrock 初期化エラー"""
        mock_anthropic_bedrock.side_effect = Exception("認証エラー")

        client = ClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()

        assert "Amazon Bedrock Claude API初期化エラー" in str(exc_info.value)
        assert "認証エラー" in str(exc_info.value)

    @patch("app.external.claude_api.AnthropicBedrock")
    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_initialize_empty_credentials(self, mock_anthropic_bedrock):
        """initialize - 空の認証情報"""
        client = ClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()

        assert "AWS認証情報が設定されていません" in str(exc_info.value)


class TestClaudeAPIClientGenerateContent:
    """ClaudeAPIClient _generate_content メソッドのテスト"""

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_success(self):
        """_generate_content - 正常系"""
        # モッククライアントを設定
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="生成されたサマリー")]
        mock_response.usage.input_tokens = 1500
        mock_response.usage.output_tokens = 800

        mock_client.messages.create.return_value = mock_response

        client = ClaudeAPIClient()
        client.client = mock_client

        result = client._generate_content(
            prompt="テストプロンプト", model_name="claude-3-5-sonnet-20241022"
        )

        assert result == ("生成されたサマリー", 1500, 800)

        # messages.create が正しい引数で呼ばれたことを確認
        mock_client.messages.create.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            max_tokens=6000,
            messages=[{"role": "user", "content": "テストプロンプト"}],
        )

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_empty_response(self):
        """_generate_content - 空のレスポンス"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = []
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 0

        mock_client.messages.create.return_value = mock_response

        client = ClaudeAPIClient()
        client.client = mock_client

        result = client._generate_content(
            prompt="テストプロンプト", model_name="claude-3-5-sonnet-20241022"
        )

        assert result == (MESSAGES["ERROR"]["EMPTY_RESPONSE"], 100, 0)

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_api_error(self):
        """_generate_content - API呼び出しエラー"""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API接続エラー")

        client = ClaudeAPIClient()
        client.client = mock_client

        with pytest.raises(APIError) as exc_info:
            client._generate_content(
                prompt="テストプロンプト", model_name="claude-3-5-sonnet-20241022"
            )

        error_message = str(exc_info.value)
        assert "API接続エラー" in error_message
        # MESSAGES["BEDROCK_API_ERROR"] のフォーマットを確認
        assert "Amazon Bedrock Claude API呼び出しエラー" in error_message

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_uses_anthropic_model(self):
        """_generate_content - 渡された model_name パラメータを使用"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="テキスト")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client.messages.create.return_value = mock_response

        client = ClaudeAPIClient()
        client.client = mock_client

        # model_name パラメータに渡した値が使用される
        test_model = "different-model-name"
        client._generate_content(
            prompt="プロンプト", model_name=test_model
        )

        # 渡された model_name が使用されることを確認
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["model"] == test_model

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_max_tokens_6000(self):
        """_generate_content - max_tokens が 6000 に設定"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="テキスト")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client.messages.create.return_value = mock_response

        client = ClaudeAPIClient()
        client.client = mock_client

        client._generate_content(prompt="プロンプト", model_name="test-model")

        # max_tokens が 6000 であることを確認
        call_args = mock_client.messages.create.call_args
        assert call_args[1]["max_tokens"] == 6000

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_message_format(self):
        """_generate_content - メッセージフォーマット確認"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="結果")]
        mock_response.usage.input_tokens = 200
        mock_response.usage.output_tokens = 100

        mock_client.messages.create.return_value = mock_response

        client = ClaudeAPIClient()
        client.client = mock_client

        test_prompt = "これはテストプロンプトです"
        client._generate_content(prompt=test_prompt, model_name="test-model")

        # messages 引数のフォーマットを確認
        call_args = mock_client.messages.create.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == test_prompt


class TestClaudeAPIClientIntegration:
    """ClaudeAPIClient 統合テスト"""

    @patch("app.external.claude_api.AnthropicBedrock")
    @patch("app.services.prompt_service.get_prompt")
    @patch("app.core.database.get_db_session")
    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_full_generate_summary_flow(
        self, mock_db_session, mock_get_prompt, mock_anthropic_bedrock
    ):
        """完全な文書生成フロー"""
        from unittest.mock import MagicMock

        # モック設定
        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db
        mock_get_prompt.return_value = None

        mock_bedrock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="生成された診療情報提供書")]
        mock_response.usage.input_tokens = 2000
        mock_response.usage.output_tokens = 1000

        mock_bedrock_client.messages.create.return_value = mock_response
        mock_anthropic_bedrock.return_value = mock_bedrock_client

        # テスト実行
        client = ClaudeAPIClient()
        result = client.generate_summary(medical_text="患者情報", additional_info="追加情報",
                                         referral_purpose="精査依頼", current_prescription="処方内容",
                                         document_type="他院への紹介")

        assert result == ("生成された診療情報提供書", 2000, 1000)

    @patch("app.external.claude_api.AnthropicBedrock")
    @patch.dict(
        os.environ,
        {
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
        clear=True,
    )
    def test_generate_summary_initialization_error(self, mock_anthropic_bedrock):
        """generate_summary - 初期化エラー"""
        client = ClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.generate_summary(medical_text="データ")

        assert "AWS認証情報が設定されていません" in str(exc_info.value)


class TestClaudeAPIClientEdgeCases:
    """ClaudeAPIClient エッジケース"""

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "ap-northeast-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_very_long_prompt(self):
        """_generate_content - 非常に長いプロンプト"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="サマリー")]
        mock_response.usage.input_tokens = 50000
        mock_response.usage.output_tokens = 1000

        mock_client.messages.create.return_value = mock_response

        client = ClaudeAPIClient()
        client.client = mock_client

        long_prompt = "あ" * 100000
        result = client._generate_content(prompt=long_prompt, model_name="test-model")

        assert result == ("サマリー", 50000, 1000)

    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "test_key",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
    )
    def test_generate_content_special_characters_in_prompt(self):
        """_generate_content - 特殊文字を含むプロンプト"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [TextBlock(type="text", text="結果")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50

        mock_client.messages.create.return_value = mock_response

        client = ClaudeAPIClient()
        client.client = mock_client

        special_prompt = "特殊文字: \n\t\r\n!@#$%^&*(){}[]<>?/\\|`~"
        result = client._generate_content(
            prompt=special_prompt, model_name="test-model"
        )

        assert result[0] == "結果"

    @patch("app.external.claude_api.AnthropicBedrock")
    @patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "   ",
            "AWS_SECRET_ACCESS_KEY": "test_secret",
            "AWS_REGION": "us-east-1",
            "ANTHROPIC_MODEL": "claude-3-5-sonnet-20241022",
        },
        clear=True,
    )
    def test_initialize_whitespace_only_credentials(self, mock_anthropic_bedrock):
        """initialize - 空白のみの認証情報"""
        mock_anthropic_bedrock.side_effect = Exception("無効な認証情報")

        client = ClaudeAPIClient()

        # 空白のみの認証情報でもall()はTrueになるが、API呼び出し時にエラー
        with pytest.raises(APIError) as exc_info:
            client.initialize()

        assert "Amazon Bedrock Claude API初期化エラー" in str(exc_info.value)
