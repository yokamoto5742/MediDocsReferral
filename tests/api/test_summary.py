from unittest.mock import patch

from fastapi import status

from app.core.constants import MESSAGES
from app.services.sse_helpers import sse_error, sse_event


def _stream(*events: str):
    """サービス層のSSEジェネレータの代わりに使うイテレータ"""
    return iter(events)


def test_generate_summary_stream_passes_request_to_service(
    client, test_db, csrf_headers
):
    """文書生成API - リクエストをそのままサービス層に渡し、SSEを返す"""
    complete = sse_event("complete", {"success": True, "output_summary": "生成結果"})

    with patch("app.api.summary.execute_summary_generation_stream") as mock_execute:
        mock_execute.return_value = _stream(complete)

        payload = {
            "medical_text": "患者は60歳男性。2型糖尿病にて加療中。",
            "additional_info": "HbA1c 7.5%",
            "current_prescription": "メトホルミン500mg",
            "referral_purpose": "精査加療依頼",
            "department": "眼科",
            "doctor": "橋本義弘",
            "document_type": "返書",
            "model": "Gemini",
            "model_explicitly_selected": True,
        }

        response = client.post(
            "/api/summary/generate-stream", json=payload, headers=csrf_headers
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert response.headers["cache-control"] == "no-cache"
    assert response.text == complete

    request, user_ip = mock_execute.call_args[0]
    assert request.model_dump(exclude={"previous_summary", "evaluation_feedback"}) == payload
    assert user_ip == "testclient"


def test_generate_summary_stream_default_fields(client, test_db, csrf_headers):
    """文書生成API - オプションフィールド省略時はデフォルト値を使用"""
    with patch("app.api.summary.execute_summary_generation_stream") as mock_execute:
        mock_execute.return_value = _stream()

        response = client.post(
            "/api/summary/generate-stream",
            json={"medical_text": "患者は40歳女性。"},
            headers=csrf_headers,
        )

    assert response.status_code == status.HTTP_200_OK

    request = mock_execute.call_args[0][0]
    assert request.additional_info == ""
    assert request.department == "default"
    assert request.doctor == "default"
    assert request.document_type == "他院への紹介"
    assert request.model == "Claude"
    assert request.model_explicitly_selected is False


def test_generate_summary_stream_service_error_event(client, test_db, csrf_headers):
    """文書生成API - サービス層のエラーは error イベントとして返る"""
    with patch("app.api.summary.execute_summary_generation_stream") as mock_execute:
        mock_execute.return_value = _stream(sse_error("カルテ情報を入力してください"))

        response = client.post(
            "/api/summary/generate-stream",
            json={"medical_text": "短"},
            headers=csrf_headers,
        )

    assert response.status_code == status.HTTP_200_OK
    assert "event: error" in response.text
    assert "カルテ情報を入力してください" in response.text


def test_generate_summary_stream_missing_required_field(client, test_db, csrf_headers):
    """文書生成API - 必須フィールド不足"""
    payload = {
        "additional_info": "追加情報",
        # medical_text が欠落
    }

    response = client.post(
        "/api/summary/generate-stream", json=payload, headers=csrf_headers
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # 検証に失敗したフィールド名はクライアントに返さず定型文のみ
    data = response.json()
    assert data["error_message"] == MESSAGES["ERROR"]["INPUT_ERROR"]
    assert "medical_text" not in response.text.lower()


def test_non_streaming_generate_endpoint_removed(client, test_db, csrf_headers):
    """非ストリーミングの文書生成APIは廃止済み"""
    response = client.post(
        "/api/summary/generate",
        json={"medical_text": "患者は40歳女性。"},
        headers=csrf_headers,
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_available_models_claude_only(client, test_db):
    """利用可能モデル取得 - Claude のみ"""
    with patch("app.services.model_selector.settings") as mock_settings:
        mock_settings.anthropic_model = "claude-3-5-sonnet-20241022"
        mock_settings.gemini_model = None

        response = client.get("/api/summary/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available_models"] == ["Claude"]
        assert data["default_model"] == "Claude"


def test_get_available_models_gemini_only(client, test_db):
    """利用可能モデル取得 - Gemini のみ"""
    with patch("app.services.model_selector.settings") as mock_settings:
        mock_settings.anthropic_model = None
        mock_settings.gemini_model = "gemini-1.5-pro-002"

        response = client.get("/api/summary/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available_models"] == ["Gemini"]
        assert data["default_model"] == "Gemini"


def test_get_available_models_both(client, test_db):
    """利用可能モデル取得 - 両方"""
    with patch("app.services.model_selector.settings") as mock_settings:
        mock_settings.anthropic_model = "claude-3-5-sonnet-20241022"
        mock_settings.gemini_model = "gemini-1.5-pro-002"

        response = client.get("/api/summary/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available_models"] == ["Claude", "Gemini"]
        assert data["default_model"] == "Claude"


def test_get_available_models_none(client, test_db):
    """利用可能モデル取得 - なし"""
    with patch("app.services.model_selector.settings") as mock_settings:
        mock_settings.anthropic_model = None
        mock_settings.gemini_model = None

        response = client.get("/api/summary/models")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["available_models"] == []
        assert data["default_model"] is None
