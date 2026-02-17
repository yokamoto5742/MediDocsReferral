import pytest
from fastapi.testclient import TestClient

from app.main import app


class TestCORS:
    """CORS設定のテスト"""

    @pytest.fixture
    def client(self):
        """テストクライアント"""
        return TestClient(app)

    def test_cors_headers_present(self, client):
        """CORSヘッダーが存在する"""
        response = client.options("/health", headers={"Origin": "http://localhost:8000"})
        assert "access-control-allow-origin" in response.headers

    def test_cors_allowed_origin(self, client):
        """許可されたオリジンからのリクエストが許可される"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:8000"

    def test_cors_credentials_allowed(self, client):
        """credentialsが許可される"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "GET"
            }
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_methods_allowed(self, client):
        """許可されたメソッドが設定されている"""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8000",
                "Access-Control-Request-Method": "POST"
            }
        )
        allowed_methods = response.headers.get("access-control-allow-methods", "").upper()
        assert "GET" in allowed_methods
        assert "POST" in allowed_methods
        assert "PUT" in allowed_methods
        assert "DELETE" in allowed_methods
