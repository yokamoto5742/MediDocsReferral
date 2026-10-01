"""統合テスト: エラーハンドリング（AI API障害）"""

from fastapi import status

from app.core.constants import MESSAGES
from app.models.evaluation_prompt import EvaluationPrompt
from app.models.usage import SummaryUsage
from app.utils.exceptions import APIError
from tests.integration.conftest import patch_ai_client, sse_event_data

_VALID_MEDICAL_TEXT = (
    "患者は70歳女性。慢性心不全、2型糖尿病にて長期加療中。"
    "今回は心不全増悪にて入院し、治療後症状改善し退院となった。"
)

_VALID_OUTPUT_SUMMARY = (
    "現病歴: 慢性心不全、糖尿病にて加療中。\n"
    "入院経過: 心不全増悪後、治療により改善。\n"
    "退院時状況: 症状改善し退院。"
)


class TestStreamingErrors:
    def test_ai_exception_emits_error_event(
        self, integration_client, db_session, csrf_headers
    ):
        """文書生成でAI APIが例外を投げると定型メッセージのerrorイベントが返る"""
        with patch_ai_client("summary", error=Exception("Bedrock接続エラー")):
            response = integration_client.post(
                "/api/summary/generate-stream",
                json={
                    "medical_text": _VALID_MEDICAL_TEXT,
                    "model": "Claude",
                    "model_explicitly_selected": True,
                },
                headers=csrf_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = sse_event_data(response, "error")
        assert data["success"] is False
        assert data["error_message"] == MESSAGES["ERROR"]["API_ERROR"]
        # 例外詳細はクライアントに返さない
        assert "Bedrock接続エラー" not in response.text
        assert "event: complete" not in response.text

        # 失敗した生成は使用量に計上しない
        db_session.expire_all()
        assert db_session.query(SummaryUsage).count() == 0

    def test_empty_ai_response_emits_error_event(
        self, integration_client, db_session, csrf_headers
    ):
        """AI APIが空の応答を返した場合 (APIError) もerrorイベントになる"""
        with patch_ai_client(
            "summary", error=APIError(MESSAGES["ERROR"]["EMPTY_RESPONSE"])
        ):
            response = integration_client.post(
                "/api/summary/generate-stream",
                json={
                    "medical_text": _VALID_MEDICAL_TEXT,
                    "model": "Claude",
                    "model_explicitly_selected": True,
                },
                headers=csrf_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = sse_event_data(response, "error")
        assert data["error_message"] == MESSAGES["ERROR"]["API_ERROR"]

    def test_evaluation_exception_emits_error_event(
        self, integration_client, db_session, csrf_headers
    ):
        """評価でAI APIが例外を投げると定型メッセージのerrorイベントが返る"""
        db_session.add(
            EvaluationPrompt(
                document_type="退院時サマリ",
                content="評価プロンプト",
                is_active=True,
            )
        )
        db_session.commit()

        with patch_ai_client("evaluation", error=Exception("Gemini API障害")):
            response = integration_client.post(
                "/api/evaluation/evaluate-stream",
                json={
                    "document_type": "退院時サマリ",
                    "input_text": "患者情報テキスト",
                    "current_prescription": "",
                    "additional_info": "",
                    "output_summary": _VALID_OUTPUT_SUMMARY,
                },
                headers=csrf_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = sse_event_data(response, "error")
        assert data["success"] is False
        assert data["error_message"] == MESSAGES["ERROR"]["EVALUATION_ERROR"]
        # 例外詳細はクライアントに返さない
        assert "Gemini API障害" not in response.text

    def test_invalid_model_name_emits_error_event(
        self, integration_client, db_session, csrf_headers
    ):
        """サポートされていないモデル名はerrorイベントが返る"""
        response = integration_client.post(
            "/api/summary/generate-stream",
            json={
                "medical_text": _VALID_MEDICAL_TEXT,
                "model": "UnsupportedModel",
                "model_explicitly_selected": True,
            },
            headers=csrf_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = sse_event_data(response, "error")
        assert data["success"] is False
        assert "UnsupportedModel" in data["error_message"]
