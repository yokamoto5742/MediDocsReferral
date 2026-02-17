from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.constants import MESSAGES
from app.external.cloudflare_gemini_api import CloudflareGeminiAPIClient
from app.utils.exceptions import APIError


def create_mock_settings(**kwargs):
    """テスト用の設定モックを作成"""
    mock = MagicMock()
    mock.gemini_model = kwargs.get("gemini_model", "gemini-2.0-flash")
    mock.google_project_id = kwargs.get("google_project_id", "test-project")
    mock.google_location = kwargs.get("google_location", "global")
    mock.gemini_thinking_level = kwargs.get("gemini_thinking_level", "HIGH")
    mock.cloudflare_account_id = kwargs.get("cloudflare_account_id", "test-account-id")
    mock.cloudflare_gateway_id = kwargs.get("cloudflare_gateway_id", "test-gateway-id")
    mock.cloudflare_aig_token = kwargs.get("cloudflare_aig_token", "test-token")
    return mock


class TestCloudflareGeminiAPIClientInitialization:
    """CloudflareGeminiAPIClient 初期化のテスト"""

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_init_with_default_model(self, mock_get_settings):
        """初期化 - デフォルトモデル使用"""
        mock_get_settings.return_value = create_mock_settings(
            gemini_model="gemini-2.0-flash"
        )

        client = CloudflareGeminiAPIClient()

        assert client.default_model == "gemini-2.0-flash"
        assert client.settings is not None

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_init_with_custom_model(self, mock_get_settings):
        """初期化 - カスタムモデル指定"""
        mock_get_settings.return_value = create_mock_settings()

        client = CloudflareGeminiAPIClient(model_name="gemini-custom-model")

        assert client.default_model == "gemini-custom-model"

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_init_without_gemini_model(self, mock_get_settings):
        """初期化 - gemini_model なし"""
        mock_get_settings.return_value = create_mock_settings(gemini_model=None)

        client = CloudflareGeminiAPIClient()

        assert client.default_model is None


class TestCloudflareGeminiAPIClientInitialize:
    """CloudflareGeminiAPIClient initialize メソッドのテスト"""

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_initialize_success(self, mock_get_settings):
        """initialize - 正常に成功"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id="test-account",
            cloudflare_gateway_id="test-gateway",
            cloudflare_aig_token="test-token",
            google_project_id="test-project"
        )

        client = CloudflareGeminiAPIClient()
        result = client.initialize()

        assert result is True

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_initialize_missing_cloudflare_account_id(self, mock_get_settings):
        """initialize - CLOUDFLARE_ACCOUNT_ID 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id=None
        )

        client = CloudflareGeminiAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"] in str(exc_info.value)

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_initialize_missing_cloudflare_gateway_id(self, mock_get_settings):
        """initialize - CLOUDFLARE_GATEWAY_ID 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_gateway_id=None
        )

        client = CloudflareGeminiAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"] in str(exc_info.value)

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_initialize_missing_cloudflare_aig_token(self, mock_get_settings):
        """initialize - CLOUDFLARE_AIG_TOKEN 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_aig_token=None
        )

        client = CloudflareGeminiAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["CLOUDFLARE_GATEWAY_SETTINGS_MISSING"] in str(exc_info.value)

    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_initialize_missing_google_project_id(self, mock_get_settings):
        """initialize - GOOGLE_PROJECT_ID 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            google_project_id=None
        )

        client = CloudflareGeminiAPIClient()

        with pytest.raises(APIError) as exc_info:
            client.initialize()
        assert MESSAGES["CONFIG"]["VERTEX_AI_PROJECT_MISSING"] in str(exc_info.value)


class TestCloudflareGeminiAPIClientGenerateContent:
    """CloudflareGeminiAPIClient _generate_content メソッドのテスト"""

    @patch("app.external.cloudflare_gemini_api.httpx.post")
    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_generate_content_success(self, mock_get_settings, mock_httpx_post):
        """_generate_content - 正常に成功"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id="test-account",
            cloudflare_gateway_id="test-gateway",
            cloudflare_aig_token="test-token",
            google_project_id="test-project",
            google_location="us-central1",
            gemini_thinking_level="HIGH"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "生成されたサマリー"}]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 2000,
                "candidatesTokenCount": 1000
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareGeminiAPIClient()
        result = client._generate_content("テストプロンプト", "gemini-2.0-flash")

        assert result == ("生成されたサマリー", 2000, 1000)

        call_args = mock_httpx_post.call_args
        assert "gateway.ai.cloudflare.com" in call_args[0][0]
        assert "test-account" in call_args[0][0]
        assert "test-gateway" in call_args[0][0]
        assert "test-project" in call_args[0][0]
        assert "gemini-2.0-flash" in call_args[0][0]

        assert call_args[1]["headers"]["cf-aig-authorization"] == "Bearer test-token"
        assert call_args[1]["headers"]["Content-Type"] == "application/json"

        request_body = call_args[1]["json"]
        assert request_body["contents"][0]["role"] == "user"
        assert request_body["contents"][0]["parts"][0]["text"] == "テストプロンプト"
        assert request_body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "HIGH"

    @patch("app.external.cloudflare_gemini_api.httpx.post")
    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_generate_content_with_low_thinking_level(self, mock_get_settings, mock_httpx_post):
        """_generate_content - LOW thinking level"""
        mock_get_settings.return_value = create_mock_settings(
            gemini_thinking_level="LOW"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "生成されたサマリー"}]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 1500,
                "candidatesTokenCount": 800
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareGeminiAPIClient()
        result = client._generate_content("テストプロンプト", "gemini-2.0-flash")

        assert result == ("生成されたサマリー", 1500, 800)

        call_args = mock_httpx_post.call_args
        request_body = call_args[1]["json"]
        assert request_body["generationConfig"]["thinkingConfig"]["thinkingLevel"] == "LOW"

    @patch("app.external.cloudflare_gemini_api.httpx.post")
    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_generate_content_empty_response(self, mock_get_settings, mock_httpx_post):
        """_generate_content - レスポンスが空"""
        mock_get_settings.return_value = create_mock_settings()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [],
            "usageMetadata": {
                "promptTokenCount": 100,
                "candidatesTokenCount": 0
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareGeminiAPIClient()
        result = client._generate_content("テストプロンプト", "gemini-2.0-flash")

        assert result[0] == MESSAGES["ERROR"]["EMPTY_RESPONSE"]
        assert result[1] == 100
        assert result[2] == 0

    @patch("app.external.cloudflare_gemini_api.httpx.post")
    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_generate_content_missing_usage_metadata(self, mock_get_settings, mock_httpx_post):
        """_generate_content - usageMetadata なし"""
        mock_get_settings.return_value = create_mock_settings()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "生成されたサマリー"}]
                }
            }]
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareGeminiAPIClient()
        result = client._generate_content("テストプロンプト", "gemini-2.0-flash")

        assert result == ("生成されたサマリー", 0, 0)

    @patch("app.external.cloudflare_gemini_api.httpx.post")
    @patch("app.external.cloudflare_gemini_api.get_settings")
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

        client = CloudflareGeminiAPIClient()

        with pytest.raises(APIError) as exc_info:
            client._generate_content("テストプロンプト", "gemini-2.0-flash")
        error_msg = str(exc_info.value)
        assert "Cloudflare AI Gateway" in error_msg
        assert "HTTP 400" in error_msg

    @patch("app.external.cloudflare_gemini_api.httpx.post")
    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_generate_content_missing_settings(self, mock_get_settings, mock_httpx_post):
        """_generate_content - Cloudflare設定が不完全"""
        mock_get_settings.return_value = create_mock_settings(
            cloudflare_account_id=None
        )

        client = CloudflareGeminiAPIClient()

        with pytest.raises(APIError) as exc_info:
            client._generate_content("テストプロンプト", "gemini-2.0-flash")
        assert "Cloudflare Gateway が初期化されていません" in str(exc_info.value)

    @patch("app.external.cloudflare_gemini_api.httpx.post")
    @patch("app.external.cloudflare_gemini_api.get_settings")
    def test_generate_content_network_error(self, mock_get_settings, mock_httpx_post):
        """_generate_content - ネットワークエラー"""
        mock_get_settings.return_value = create_mock_settings()

        mock_httpx_post.side_effect = Exception("Network connection failed")

        client = CloudflareGeminiAPIClient()

        with pytest.raises(APIError) as exc_info:
            client._generate_content("テストプロンプト", "gemini-2.0-flash")
        error_msg = str(exc_info.value)
        assert "Cloudflare AI Gateway" in error_msg
        assert "Network connection failed" in error_msg


class TestCloudflareGeminiAPIClientIntegration:
    """CloudflareGeminiAPIClient 統合テスト"""

    @patch("app.external.base_api.get_selected_model")
    @patch("app.external.base_api.get_prompt")
    @patch("app.external.base_api.get_db_session")
    @patch("app.external.cloudflare_gemini_api.get_settings")
    @patch("app.external.cloudflare_gemini_api.httpx.post")
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
        mock_get_selected_model.return_value = "gemini-2.0-flash"

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "生成された診療情報提供書"}]
                }
            }],
            "usageMetadata": {
                "promptTokenCount": 3000,
                "candidatesTokenCount": 1500
            }
        }
        mock_httpx_post.return_value = mock_response

        client = CloudflareGeminiAPIClient()
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
