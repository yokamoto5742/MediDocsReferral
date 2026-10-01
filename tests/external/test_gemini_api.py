import json
import socket
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.genai import interactions

from app.core.constants import MESSAGES
from app.external.gemini_api import GeminiAPIClient
from app.schemas.summary import SummaryRequest
from app.utils.exceptions import APIError


def create_mock_settings(**kwargs):
    """テスト用の設定モックを作成"""
    mock = MagicMock()
    mock.google_project_id = kwargs.get("google_project_id", "test-project")
    mock.google_location = kwargs.get("google_location", "global")
    mock.google_credentials_json = kwargs.get("google_credentials_json", None)
    mock.gemini_thinking_level = kwargs.get("gemini_thinking_level", "HIGH")
    return mock


def create_interaction(text=None, input_tokens=None, output_tokens=None):
    """テスト用の Interaction を作成"""
    data: dict[str, Any] = {
        "id": "interaction-1",
        "status": "completed",
        "created": "2026-01-01T00:00:00Z",
        "updated": "2026-01-01T00:00:00Z",
        "model": "test-model",
    }
    if text is not None:
        data["steps"] = [{"type": "model_output", "content": [{"type": "text", "text": text}]}]
    if input_tokens is not None or output_tokens is not None:
        data["usage"] = {"total_input_tokens": input_tokens, "total_output_tokens": output_tokens}
    return interactions.Interaction.model_validate(data)


@pytest.fixture
def mock_get_settings():
    with patch("app.external.gemini_api.get_settings") as mock:
        mock.return_value = create_mock_settings()
        yield mock


@pytest.fixture
def mock_genai_client():
    """genai.Client をモックし、クラスのモックを返す（インスタンスは return_value）"""
    with patch("app.external.gemini_api.genai.Client") as mock:
        yield mock


class TestGeminiAPIClientInitialization:
    """GeminiAPIClient 初期化のテスト"""

    @patch("app.external.gemini_api.service_account.Credentials.from_service_account_info")
    def test_init_with_credentials_json_success(
        self, mock_from_service_account_info, mock_get_settings, mock_genai_client
    ):
        """初期化 - GOOGLE_CREDENTIALS_JSON を使用して成功"""
        credentials_dict = {
            "type": "service_account",
            "project_id": "test-project-123",
            "private_key_id": "key123",
            "private_key": "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        mock_get_settings.return_value = create_mock_settings(
            google_project_id="test-project-123",
            google_location="us-central1",
            google_credentials_json=json.dumps(credentials_dict),
        )

        client = GeminiAPIClient()

        assert client.client is mock_genai_client.return_value
        mock_from_service_account_info.assert_called_once_with(
            credentials_dict,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        mock_genai_client.assert_called_once_with(
            vertexai=True,
            project="test-project-123",
            location="us-central1",
            credentials=mock_from_service_account_info.return_value,
        )

    @pytest.mark.parametrize("credentials_json", [None, ""])
    def test_init_without_credentials_json(
        self, mock_get_settings, mock_genai_client, credentials_json
    ):
        """初期化 - GOOGLE_CREDENTIALS_JSON なし（デフォルト認証）"""
        mock_get_settings.return_value = create_mock_settings(
            google_project_id="test-project-456",
            google_credentials_json=credentials_json,
        )

        client = GeminiAPIClient()

        assert client.client is mock_genai_client.return_value
        mock_genai_client.assert_called_once_with(
            vertexai=True,
            project="test-project-456",
            location="global",
        )

    @pytest.mark.parametrize("project_id", [None, ""])
    def test_init_missing_project_id(
        self, mock_get_settings, mock_genai_client, project_id
    ):
        """初期化 - GOOGLE_PROJECT_ID 未設定"""
        mock_get_settings.return_value = create_mock_settings(
            google_project_id=project_id
        )

        with pytest.raises(APIError) as exc_info:
            GeminiAPIClient()

        assert str(exc_info.value) == MESSAGES["CONFIG"]["VERTEX_AI_PROJECT_MISSING"]
        mock_genai_client.assert_not_called()

    def test_init_invalid_json_format(self, mock_get_settings):
        """初期化 - 不正なJSON形式"""
        mock_get_settings.return_value = create_mock_settings(
            google_credentials_json="{ invalid json format"
        )

        with pytest.raises(APIError) as exc_info:
            GeminiAPIClient()

        assert "認証情報JSONのパースに失敗しました" in str(exc_info.value)

    @pytest.mark.parametrize(
        ("error", "expected_message"),
        [
            (KeyError("project_id"), "認証情報に必要なフィールドがありません"),
            (Exception("認証情報作成失敗"), "認証情報の処理中にエラーが発生しました"),
        ],
    )
    @patch("app.external.gemini_api.service_account.Credentials.from_service_account_info")
    def test_init_credentials_error(
        self, mock_from_service_account_info, mock_get_settings, error, expected_message
    ):
        """初期化 - 認証情報の生成に失敗"""
        mock_get_settings.return_value = create_mock_settings(
            google_credentials_json=json.dumps({"type": "service_account"})
        )
        mock_from_service_account_info.side_effect = error

        with pytest.raises(APIError) as exc_info:
            GeminiAPIClient()

        assert expected_message in str(exc_info.value)

    def test_init_genai_client_error(self, mock_get_settings, mock_genai_client):
        """初期化 - genai.Client 作成エラー"""
        mock_genai_client.side_effect = Exception("API接続エラー")

        with pytest.raises(APIError) as exc_info:
            GeminiAPIClient()

        error_message = str(exc_info.value)
        assert "Vertex AI初期化エラー" in error_message
        assert "API接続エラー" in error_message


class TestGeminiAPIClientGenerate:
    """GeminiAPIClient generate メソッドのテスト"""

    def test_generate_success(self, mock_get_settings, mock_genai_client):
        """generate - 正常系"""
        create = mock_genai_client.return_value.interactions.create
        create.return_value = create_interaction("生成されたサマリー", 2000, 1000)

        result = GeminiAPIClient().generate(
            prompt="テストプロンプト", model_name="gemini-3.8-flash"
        )

        assert result == ("生成されたサマリー", 2000, 1000)

        call_kwargs = create.call_args[1]
        assert call_kwargs["model"] == "gemini-3.8-flash"
        assert call_kwargs["input"] == "テストプロンプト"
        # 患者情報を含むためサーバー側に保存しない
        assert call_kwargs["store"] is False
        assert "stream" not in call_kwargs
        assert "system_instruction" not in call_kwargs

    @pytest.mark.parametrize(
        ("setting", "expected"),
        [("LOW", "low"), ("HIGH", "high")],
    )
    def test_generate_thinking_level(
        self, mock_get_settings, mock_genai_client, setting, expected
    ):
        """generate - thinking_level が小文字で渡されること"""
        mock_get_settings.return_value = create_mock_settings(
            gemini_thinking_level=setting
        )
        create = mock_genai_client.return_value.interactions.create
        create.return_value = create_interaction("テキスト")

        GeminiAPIClient().generate(prompt="プロンプト", model_name="test-model")

        assert create.call_args[1]["generation_config"] == {"thinking_level": expected}

    def test_generate_with_system_prompt(self, mock_get_settings, mock_genai_client):
        """generate - システムプロンプトが system_instruction で渡されること"""
        create = mock_genai_client.return_value.interactions.create
        create.return_value = create_interaction("テキスト")

        GeminiAPIClient().generate(
            prompt="プロンプト", model_name="test-model", system_prompt="システム指示"
        )

        assert create.call_args[1]["system_instruction"] == "システム指示"

    def test_generate_no_usage(self, mock_get_settings, mock_genai_client):
        """generate - usage なしの場合はトークン数 0"""
        create = mock_genai_client.return_value.interactions.create
        create.return_value = create_interaction("サマリー")

        result = GeminiAPIClient().generate(prompt="プロンプト", model_name="test-model")

        assert result == ("サマリー", 0, 0)

    def test_generate_no_text_output(self, mock_get_settings, mock_genai_client):
        """generate - テキスト出力がない場合に空文字を返すこと"""
        create = mock_genai_client.return_value.interactions.create
        create.return_value = create_interaction()

        result = GeminiAPIClient().generate(prompt="テスト", model_name="test-model")

        assert result == ("", 0, 0)

    def test_generate_unexpected_response(self, mock_get_settings, mock_genai_client):
        """generate - Interaction 以外の応答"""
        mock_genai_client.return_value.interactions.create.return_value = MagicMock()

        with pytest.raises(APIError) as exc_info:
            GeminiAPIClient().generate(prompt="プロンプト", model_name="test-model")

        assert str(exc_info.value) == MESSAGES["ERROR"]["GEMINI_UNEXPECTED_RESPONSE"]

    @pytest.mark.parametrize(
        "error",
        [
            Exception("Vertex AI APIエラー"),
            socket.timeout("接続タイムアウト"),
            ConnectionResetError("接続がリセットされました"),
            Exception("503 Service Unavailable"),
        ],
    )
    def test_generate_api_error(self, mock_get_settings, mock_genai_client, error):
        """generate - API呼び出しの例外は APIError にラップされる"""
        mock_genai_client.return_value.interactions.create.side_effect = error

        with pytest.raises(APIError) as exc_info:
            GeminiAPIClient().generate(prompt="プロンプト", model_name="test-model")

        error_message = str(exc_info.value)
        assert "Vertex AI API呼び出しエラー" in error_message
        assert str(error) in error_message
        assert exc_info.value.__cause__ is error

    @pytest.mark.parametrize(
        "prompt",
        ["あ" * 200000, "特殊文字: \n\t\r\n!@#$%^&*(){}[]<>?/\\|`~", ""],
        ids=["long", "special_characters", "empty"],
    )
    def test_generate_passes_prompt_as_is(
        self, mock_get_settings, mock_genai_client, prompt
    ):
        """generate - 長文・特殊文字・空のプロンプトをそのまま渡す"""
        create = mock_genai_client.return_value.interactions.create
        create.return_value = create_interaction("結果", 100, 50)

        result = GeminiAPIClient().generate(prompt=prompt, model_name="test-model")

        assert result == ("結果", 100, 50)
        assert create.call_args[1]["input"] == prompt


class TestGeminiAPIClientIntegration:
    """GeminiAPIClient 統合テスト"""

    @patch("app.external.base_api.get_prompt", return_value=None)
    @patch("app.external.base_api.get_db_session")
    def test_full_generate_summary_flow(
        self, _mock_db_session, _mock_get_prompt, mock_get_settings, mock_genai_client
    ):
        """完全な文書生成フロー"""
        create = mock_genai_client.return_value.interactions.create
        create.return_value = create_interaction("生成された診療情報提供書", 3000, 1500)

        result = GeminiAPIClient().generate_summary(
            SummaryRequest(
                medical_text="患者情報",
                additional_info="追加情報",
                current_prescription="処方内容",
                document_type="他院への紹介",
            ),
            "gemini-1.5-pro-002",
        )

        assert result == ("生成された診療情報提供書", 3000, 1500)
        call_kwargs = create.call_args[1]
        assert call_kwargs["model"] == "gemini-1.5-pro-002"
        assert "患者情報" in call_kwargs["input"]
