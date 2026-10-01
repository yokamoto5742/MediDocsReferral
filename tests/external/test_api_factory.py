from unittest.mock import patch

import pytest

from app.core.constants import ModelType
from app.external.api_factory import create_client
from app.utils.exceptions import APIError


class TestCreateClient:
    """create_client 関数のテスト"""

    @patch("app.external.api_factory.ClaudeAPIClient")
    def test_create_client_claude(self, mock_claude):
        """クライアント作成 - Claude"""
        assert create_client("Claude") is mock_claude.return_value
        mock_claude.assert_called_once_with()

    @patch("app.external.api_factory.GeminiAPIClient")
    def test_create_client_gemini(self, mock_gemini):
        """クライアント作成 - Gemini"""
        assert create_client("Gemini") is mock_gemini.return_value
        mock_gemini.assert_called_once_with()

    @patch("app.external.api_factory.ClaudeAPIClient")
    def test_create_client_model_type_enum(self, mock_claude):
        """クライアント作成 - ModelType を直接渡せる"""
        assert create_client(ModelType.CLAUDE) is mock_claude.return_value

    @patch("app.external.api_factory.ClaudeAPIClient")
    def test_create_client_returns_independent_instances(self, mock_claude):
        """呼び出しごとにクライアントを生成すること"""
        create_client("Claude")
        create_client("Claude")
        assert mock_claude.call_count == 2

    @pytest.mark.parametrize("model", ["gpt-4", "openai", "claude", "", "123"])
    def test_create_client_unsupported_model(self, model):
        """クライアント作成 - 未対応のモデル種別は APIError"""
        with pytest.raises(APIError) as exc_info:
            create_client(model)

        assert "未対応のAPIプロバイダー" in str(exc_info.value)
        assert model in str(exc_info.value)

    @patch("app.external.api_factory.GeminiAPIClient")
    def test_create_client_propagates_init_error(self, mock_gemini):
        """クライアント初期化時の APIError が伝播すること"""
        mock_gemini.side_effect = APIError("Vertex AI初期化エラー")

        with pytest.raises(APIError, match="Vertex AI初期化エラー"):
            create_client("Gemini")
