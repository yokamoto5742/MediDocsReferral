"""統合テスト: 評価フロー（API層→Service層→DB）"""

from fastapi import status

from app.core.constants import MESSAGES
from app.models.evaluation_prompt import EvaluationPrompt
from tests.integration.conftest import (
    parse_sse_events,
    patch_ai_client,
    sse_event_data,
)

VALID_OUTPUT_SUMMARY = (
    "現病歴: 2型糖尿病にて加療中。\n"
    "入院経過: 血糖コントロール良好となり退院。\n"
    "退院時状況: 全身状態良好。"
)


class TestStreamingEvaluation:
    def test_success_emits_complete_event(
        self, integration_client, db_session, csrf_headers
    ):
        """正常系: 評価プロンプトあり状態でprogress→completeのSSEイベントが返る"""
        db_session.add(
            EvaluationPrompt(
                document_type="退院時サマリ",
                content="以下の退院時サマリを評価してください。",
                is_active=True,
            )
        )
        db_session.commit()

        with patch_ai_client(
            "evaluation", result=("評価結果: 適切な要約です。", 500, 200)
        ) as mock_client:
            response = integration_client.post(
                "/api/evaluation/evaluate-stream",
                json={
                    "document_type": "退院時サマリ",
                    "input_text": "患者は67歳男性。糖尿病にて加療中。",
                    "current_prescription": "メトホルミン500mg",
                    "additional_info": "",
                    "output_summary": VALID_OUTPUT_SUMMARY,
                },
                headers=csrf_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        assert "text/event-stream" in response.headers["content-type"]

        event_types = [e["type"] for e in parse_sse_events(response.text)]
        assert event_types[0] == "progress"
        assert event_types[-1] == "complete"

        data = sse_event_data(response, "complete")
        assert data["success"] is True
        assert data["evaluation_result"] == "評価結果: 適切な要約です。"
        assert data["input_tokens"] == 500
        assert data["output_tokens"] == 200

        # 評価モデル(既定はGemini)のモデル名と、DBの評価プロンプトが使われる
        user_prompt, model_name, system_prompt = mock_client.generate.call_args[0]
        assert VALID_OUTPUT_SUMMARY in user_prompt
        assert model_name == "gemini-test-model"
        assert "以下の退院時サマリを評価してください。" in system_prompt

    def test_no_prompt_emits_error_event(
        self, integration_client, db_session, csrf_headers
    ):
        """評価プロンプトが未設定の場合はerrorイベントが返る"""
        response = integration_client.post(
            "/api/evaluation/evaluate-stream",
            json={
                "document_type": "退院時サマリ",
                "input_text": "患者情報テキスト",
                "current_prescription": "",
                "additional_info": "",
                "output_summary": VALID_OUTPUT_SUMMARY,
            },
            headers=csrf_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = sse_event_data(response, "error")
        assert data["success"] is False
        assert "退院時サマリ" in data["error_message"]

    def test_empty_output_summary_emits_validation_error(
        self, integration_client, db_session, csrf_headers
    ):
        """評価対象の出力が空の場合はバリデーションエラーのerrorイベントが返る"""
        response = integration_client.post(
            "/api/evaluation/evaluate-stream",
            json={
                "document_type": "退院時サマリ",
                "input_text": "患者情報",
                "current_prescription": "",
                "additional_info": "",
                "output_summary": "",
            },
            headers=csrf_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        data = sse_event_data(response, "error")
        assert data["error_message"] == MESSAGES["VALIDATION"]["EVALUATION_NO_OUTPUT"]

    def test_evaluation_prompt_crud_then_evaluate(
        self, integration_client, db_session, csrf_headers
    ):
        """評価プロンプトをAPI経由で登録してから評価を実行できる"""
        integration_client.post(
            "/api/evaluation/prompts",
            json={
                "document_type": "現病歴",
                "content": "以下の現病歴を詳細に評価してください。",
            },
            headers=csrf_headers,
        )

        with patch_ai_client("evaluation", result=("詳細な評価結果です。", 500, 200)):
            response = integration_client.post(
                "/api/evaluation/evaluate-stream",
                json={
                    "document_type": "現病歴",
                    "input_text": "患者情報テキスト",
                    "current_prescription": "",
                    "additional_info": "",
                    "output_summary": VALID_OUTPUT_SUMMARY,
                },
                headers=csrf_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = sse_event_data(response, "complete")
        assert data["evaluation_result"] == "詳細な評価結果です。"
