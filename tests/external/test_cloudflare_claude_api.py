from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.constants import MESSAGES
from app.external.cloudflare_claude_api import CloudflareClaudeAPIClient
from app.utils.exceptions import APIError


def create_mock_settings(**kwargs):
    """テスト用の設定モックを作成"""
    mock = MagicMock()
    mock.anthropic_model = kwargs.get("anthropic_model", "anthropic.claude-3-5-sonnet-20241022-v2:0")
    mock.aws_access_key_id = kwargs.get("aws_access_key_id", "test-access-key")
    mock.aws_secret_access_key = kwargs.get("aws_secret_access_key", "test-secret-key")
    mock.aws_region = kwargs.get("aws_region", "us-east-1")
    mock.cloudflare_account_id = kwargs.get("cloudflare_account_id", "test-account-id")
    mock.cloudflare_gateway_id = kwargs.get("cloudflare_gateway_id", "test-gateway-id")
    mock.cloudflare_aig_token = kwargs.get("cloudflare_aig_token", "test-token")
    return mock


class TestCloudflareClaudeAPIClientInitialization:
    """CloudflareClaudeAPIClient 初期化のテスト"""

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_init_with_default_model(self, mock_get_settings):
        """初期化 - デフォルトモデル使用"""
        mock_get_settings.return_value = create_mock_settings(
            anthropic_model="anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

        client = CloudflareClaudeAPIClient()

        assert client.default_model == "anthropic.claude-3-5-sonnet-20241022-v2:0"
        assert client.settings is not None
        assert client.aws_access_key_id == "test-access-key"
        assert client.aws_secret_access_key == "test-secret-key"
        assert client.aws_region == "us-east-1"

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_init_with_custom_model(self, mock_get_settings):
        """初期化 - カスタムモデル指定"""
        mock_get_settings.return_value = create_mock_settings()

        client = CloudflareClaudeAPIClient(model_name="anthropic.claude-custom-model:0")

        assert client.default_model == "anthropic.claude-custom-model:0"

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_init_without_anthropic_model(self, mock_get_settings):
        """初期化 - anthropic_model なし"""
        mock_get_settings.return_value = create_mock_settings(anthropic_model=None)

        client = CloudflareClaudeAPIClient()

        assert client.default_model is None


class TestCloudflareClaudeAPIClientInitialize:
    """CloudflareClaudeAPIClient initialize メソッドのテスト"""

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_initialize_success(self, mock_get_settings):
        """initialize - 正常に成功"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id="test-account",
            cloudflare_gateway_id="test-gateway",
            cloudflare_aig_token="test-token",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_region="us-east-1",
            anthropic_model="anthropic.claude-3-5-sonnet-20241022-v2:0"
        )

        client = CloudflareClaudeAPIClient()
        result = client.initialize()

        assert result is True

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_initialize_missing_cloudflare_account_id(self, mock_get_settings):
        """initialize - CLOUDFLARE_ACCOUNT_ID 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id=None
        )

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"] in str(exc_info.value)

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_initialize_missing_cloudflare_gateway_id(self, mock_get_settings):
        """initialize - CLOUDFLARE_GATEWAY_ID 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_gateway_id=None
        )

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"] in str(exc_info.value)

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_initialize_missing_cloudflare_aig_token(self, mock_get_settings):
        """initialize - CLOUDFLARE_AIG_TOKEN 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_aig_token=None
        )

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"] in str(exc_info.value)

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_initialize_missing_aws_credentials(self, mock_get_settings):
        """initialize - AWS認証情報未設定"""
        mock_get_settings.return_value = create_mock_settings(
            aws_access_key_id=None
        )

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["AWS_CREDENTIALS_MISSING"] in str(exc_info.value)

    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_initialize_missing_anthropic_model(self, mock_get_settings):
        """initialize - ANTHROPIC_MODEL 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            anthropic_model=None
        )

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["ANTHROPIC_MODEL_MISSING"] in str(exc_info.value)


class TestCloudflareClaudeAPIClientGenerateContent:
    """CloudflareClaudeAPIClient _generate_content メソッドのテスト"""

    @patch("app.external.cloudflare_claude_api.httpx.post")
    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_generate_content_success(self, mock_get_settings, mock_httpx_post):
        """_generate_content - 正常に成功"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id="test-account",
            cloudflare_gateway_id="test-gateway",
            cloudflare_aig_token="test-token",
            aws_access_key_id="test-access-key",
            aws_secret_access_key="test-secret-key",
            aws_region="us-east-1"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "生成されたサマリー"}]
                }
            },
            "usage": {
                "inputTokens": 2000,
                "outputTokens": 1000
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareClaudeAPIClient()
        result = client._generate_content("テストプロンプト", "anthropic.claude-3-5-sonnet-20241022-v2:0")

        assert result == ("生成されたサマリー", 2000, 1000)

        call_args = mock_httpx_post.call_args
        assert "gateway.ai.cloudflare.com" in call_args[0][0]
        assert "test-account" in call_args[0][0]
        assert "test-gateway" in call_args[0][0]
        assert "aws-bedrock" in call_args[0][0]
        assert "us-east-1" in call_args[0][0]
        assert "anthropic.claude-3-5-sonnet-20241022-v2:0" in call_args[0][0]

        assert call_args[1]["headers"]["cf-aig-authorization"] == "Bearer test-token"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"
        assert "Authorization" in call_args[1]["headers"]

    @patch("app.external.cloudflare_claude_api.httpx.post")
    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_generate_content_empty_response(self, mock_get_settings, mock_httpx_post):
        """_generate_content - レスポンスが空"""
        mock_get_settings.return_value = create_mock_settings()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {
                "message": {
                    "content": []
                }
            },
            "usage": {
                "inputTokens": 100,
                "outputTokens": 0
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareClaudeAPIClient()
        result = client._generate_content("テストプロンプト", "anthropic.claude-3-5-sonnet-20241022-v2:0")

        assert result[0] == MESSAGES["ERROR"]["EMPTY_RESPONSE"]
        assert result[1] == 100
        assert result[2] == 0

    @patch("app.external.cloudflare_claude_api.httpx.post")
    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_generate_content_missing_usage(self, mock_get_settings, mock_httpx_post):
        """_generate_content - usage なし"""
        mock_get_settings.return_value = create_mock_settings()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "生成されたサマリー"}]
                }
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareClaudeAPIClient()
        result = client._generate_content("テストプロンプト", "anthropic.claude-3-5-sonnet-20241022-v2:0")

        assert result == ("生成されたサマリー", 0, 0)

    @patch("app.external.cloudflare_claude_api.httpx.post")
    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_generate_content_http_error(self, mock_get_settings, mock_httpx_post):
        """_generate_content - HTTPエラー"""
        mock_get_settings.return_value = create_mock_settings()

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_httpx_post.return_value = mock_response
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_response
        )

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client._generate_content("テストプロンプト", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        error_msg = str(exc_info.value)
        assert "Cloudflare AI Gateway" in error_msg
        assert "HTTP 400" in error_msg

    @patch("app.external.cloudflare_claude_api.httpx.post")
    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_generate_content_missing_settings(self, mock_get_settings, mock_httpx_post):
        """_generate_content - Cloudflare設定が不完全"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id=None
        )

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client._generate_content("テストプロンプト", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        assert "Cloudflare Gateway が初期化されていません" in str(exc_info.value)

    @patch("app.external.cloudflare_claude_api.httpx.post")
    @patch("app.external.cloudflare_claude_api.get_settings")
    def test_generate_content_network_error(self, mock_get_settings, mock_httpx_post):
        """_generate_content - ネットワークエラー"""
        mock_get_settings.return_value = create_mock_settings()

        mock_httpx_post.side_effect = Exception("Network connection failed")

        client = CloudflareClaudeAPIClient()

        with pytest.raises(APIError) as exc_info:
            client._generate_content("テストプロンプト", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        error_msg = str(exc_info.value)
        assert "Cloudflare AI Gateway" in error_msg
        assert "Network connection failed" in error_msg


class TestCloudflareClaudeAPIClientIntegration:
    """CloudflareClaudeAPIClient 統合テスト"""

    @patch("app.external.base_api.get_selected_model")
    @patch("app.external.base_api.get_prompt")
    @patch("app.external.base_api.get_db_session")
    @patch("app.external.cloudflare_claude_api.get_settings")
    @patch("app.external.cloudflare_claude_api.httpx.post")
    def test_generate_summary_full_flow(
        self,
        mock_httpx_post,
        mock_get_settings,
        mock_db_session,
        mock_get_prompt,
        mock_get_selected_model
    ):
        """generate_summary - 完全なフロー"""
        mock_get_settings.return_value = create_mock_settings()

        mock_db = MagicMock()
        mock_db_session.return_value.__enter__.return_value = mock_db

        mock_prompt = MagicMock()
        mock_prompt.content = "テストプロンプト"
        mock_get_prompt.return_value = mock_prompt
        mock_get_selected_model.return_value = "anthropic.claude-3-5-sonnet-20241022-v2:0"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "output": {
                "message": {
                    "content": [{"text": "生成された診療情報提供書"}]
                }
            },
            "usage": {
                "inputTokens": 3000,
                "outputTokens": 1500
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareClaudeAPIClient()
        result = client.generate_summary(
            medical_text="患者情報",
            additional_info="追加情報",
            referral_purpose="検査依頼",
            current_prescription="薬剤A",
            department="内科",
            document_type="他院への紹介",
            doctor="山田太郎"
        )

        assert result == ("生成された診療情報提供書", 3000, 1500)
        mock_httpx_post.assert_called_once()
