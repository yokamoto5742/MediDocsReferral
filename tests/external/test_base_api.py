from unittest.mock import MagicMock, patch

import pytest

from app.core.constants import (
    DEFAULT_DOCUMENT_TYPE,
    GROUNDING_INSTRUCTION,
    KARTE_JSON_INSTRUCTION,
    REFINEMENT_INSTRUCTION,
)
from app.external.base_api import BaseAPIClient
from app.schemas.summary import SummaryRequest
from app.utils.exceptions import APIError


class MockAPIClient(BaseAPIClient):
    """テスト用のモックAPIクライアント（呼び出し引数を記録する）"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def generate(
        self, prompt: str, model_name: str, system_prompt: str = ""
    ) -> tuple[str, int, int]:
        self.calls.append((prompt, model_name, system_prompt))
        return "生成されたテキスト", 1000, 500


@pytest.fixture
def mock_get_prompt():
    """DBのプロンプト取得をモック（既定ではプロンプト未登録）"""
    with (
        patch("app.external.base_api.get_db_session") as mock_db_session,
        patch("app.external.base_api.get_prompt", return_value=None) as mock,
    ):
        mock_db_session.return_value.__enter__.return_value = MagicMock()
        yield mock


class TestCreateSummaryPrompt:
    """create_summary_prompt メソッドのテスト"""

    def test_create_summary_prompt_minimal(self, mock_get_prompt):
        """プロンプト生成 - 最小パラメータ"""
        system_prompt, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(medical_text="患者情報")
        )

        assert "以下のカルテ情報を要約してください" in system_prompt
        assert GROUNDING_INSTRUCTION in system_prompt
        assert "<カルテ情報>" in user_prompt
        assert "患者情報" in user_prompt

    def test_create_summary_prompt_all_params(self, mock_get_prompt):
        """プロンプト生成 - 全パラメータ"""
        _, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(
                medical_text="カルテデータ",
                additional_info="追加情報テキスト",
                current_prescription="処方内容",
                referral_purpose="精査加療依頼",
                department="眼科",
                document_type="他院への紹介",
                doctor="橋本義弘",
            )
        )

        assert "<カルテ情報>" in user_prompt
        assert "カルテデータ" in user_prompt
        assert "<紹介目的>" in user_prompt
        assert "精査加療依頼" in user_prompt
        assert "<現在の処方>" in user_prompt
        assert "処方内容" in user_prompt
        assert "<追加情報>" in user_prompt
        assert "追加情報テキスト" in user_prompt

    def test_create_summary_prompt_empty_optional_fields(self, mock_get_prompt):
        """プロンプト生成 - 空のオプションフィールド"""
        _, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(medical_text="データ")
        )

        assert "<カルテ情報>" in user_prompt
        assert "データ" in user_prompt
        # 空のオプションフィールドはセクション自体が含まれない
        assert "<紹介目的>" not in user_prompt
        assert "<現在の処方>" not in user_prompt
        assert "<追加情報>" not in user_prompt
        assert "<前回の生成結果>" not in user_prompt

    def test_create_summary_prompt_whitespace_optional_fields(self, mock_get_prompt):
        """プロンプト生成 - 空白のみのオプションフィールド"""
        _, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(
                medical_text="データ",
                additional_info="   ",
                current_prescription="\t",
            )
        )

        # 空白のみは strip() で空文字列になるため、セクションは追加されない
        assert "<現在の処方>" not in user_prompt
        assert "<追加情報>" not in user_prompt

    def test_create_summary_prompt_json_medical_text(self, mock_get_prompt):
        """プロンプト生成 - JSON形式のカルテ情報"""
        json_text = '{"記載日": "2026-07-01", "SOAP": "経過良好"}'
        system_prompt, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(medical_text=json_text)
        )

        assert KARTE_JSON_INSTRUCTION in system_prompt
        assert json_text in user_prompt

    def test_create_summary_prompt_non_json_medical_text(self, mock_get_prompt):
        """プロンプト生成 - 非JSON形式ではJSON指示を含まない"""
        system_prompt, _ = MockAPIClient().create_summary_prompt(
            SummaryRequest(medical_text="通常のカルテ文章")
        )

        assert KARTE_JSON_INSTRUCTION not in system_prompt

    def test_create_summary_prompt_refinement(self, mock_get_prompt):
        """プロンプト生成 - 評価結果を反映した再生成"""
        system_prompt, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(
                medical_text="データ",
                previous_summary="前回の文書",
                evaluation_feedback="指摘事項あり",
            )
        )

        assert REFINEMENT_INSTRUCTION in system_prompt
        assert "<前回の生成結果>" in user_prompt
        assert "前回の文書" in user_prompt
        assert "<評価結果>" in user_prompt
        assert "指摘事項あり" in user_prompt

    def test_create_summary_prompt_refinement_requires_both_fields(
        self, mock_get_prompt
    ):
        """プロンプト生成 - 前回出力のみでは再生成セクションを含まない"""
        system_prompt, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(medical_text="データ", previous_summary="前回の文書")
        )

        assert REFINEMENT_INSTRUCTION not in system_prompt
        assert "<前回の生成結果>" not in user_prompt

    def test_create_summary_prompt_with_custom_prompt(self, mock_get_prompt):
        """プロンプト生成 - カスタムプロンプト使用"""
        mock_prompt = MagicMock()
        mock_prompt.content = "カスタムプロンプトテンプレート"
        mock_get_prompt.return_value = mock_prompt

        system_prompt, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(
                medical_text="データ",
                department="眼科",
                document_type="他院への紹介",
                doctor="橋本義弘",
            )
        )

        assert "カスタムプロンプトテンプレート" in system_prompt
        assert "<カルテ情報>" in user_prompt
        assert "データ" in user_prompt

        # 第1引数はdbセッション、第2-4引数はdepartment, document_type, doctor
        call_args = mock_get_prompt.call_args[0]
        assert call_args[1:] == ("眼科", "他院への紹介", "橋本義弘")

    def test_create_summary_prompt_default_lookup_keys(self, mock_get_prompt):
        """プロンプト生成 - 未指定時はデフォルトの診療科・文書タイプ・医師で検索"""
        MockAPIClient().create_summary_prompt(SummaryRequest(medical_text="データ"))

        call_args = mock_get_prompt.call_args[0]
        assert call_args[1:] == ("default", DEFAULT_DOCUMENT_TYPE, "default")

    def test_create_summary_prompt_db_error_falls_back_to_default(self):
        """プロンプト生成 - DB取得失敗時はデフォルトプロンプトを使用"""
        with patch(
            "app.external.base_api.get_db_session", side_effect=Exception("DB error")
        ):
            system_prompt, _ = MockAPIClient().create_summary_prompt(
                SummaryRequest(medical_text="データ")
            )

        assert "以下のカルテ情報を要約してください" in system_prompt

    def test_create_summary_prompt_special_characters(self, mock_get_prompt):
        """プロンプト生成 - 特殊文字を含むテキスト"""
        special_text = "特殊文字: \n\t\r\n!@#$%^&*(){}[]<>?/\\|`~"
        _, user_prompt = MockAPIClient().create_summary_prompt(
            SummaryRequest(medical_text=special_text)
        )

        assert special_text in user_prompt


class TestGenerateSummary:
    """generate_summary メソッドのテスト"""

    def test_generate_summary_success(self, mock_get_prompt):
        """文書生成 - 構築したプロンプトと指定モデル名で generate を呼ぶ"""
        client = MockAPIClient()
        result = client.generate_summary(
            SummaryRequest(medical_text="患者情報", additional_info="追加情報"),
            "specified-model",
        )

        assert result == ("生成されたテキスト", 1000, 500)
        user_prompt, model_name, system_prompt = client.calls[0]
        assert "患者情報" in user_prompt
        assert "追加情報" in user_prompt
        assert model_name == "specified-model"
        assert GROUNDING_INSTRUCTION in system_prompt

    def test_generate_summary_api_error_propagation(self, mock_get_prompt):
        """文書生成 - generate の APIError はそのまま伝播する"""

        class APIErrorClient(MockAPIClient):
            def generate(
                self, prompt: str, model_name: str, system_prompt: str = ""
            ) -> tuple[str, int, int]:
                raise APIError("API呼び出しエラー")

        with pytest.raises(APIError, match="API呼び出しエラー"):
            APIErrorClient().generate_summary(
                SummaryRequest(medical_text="データ"), "model"
            )


class TestBaseAPIClientAbstractMethods:
    """BaseAPIClient 抽象メソッドのテスト"""

    def test_cannot_instantiate_base_class(self):
        """BaseAPIClient を直接インスタンス化できない"""
        with pytest.raises(TypeError):
            BaseAPIClient()  # type: ignore[abstract]

    def test_subclass_must_implement_generate(self):
        """サブクラスは generate を実装する必要がある"""

        class IncompleteClient(BaseAPIClient):
            pass

        with pytest.raises(TypeError):
            IncompleteClient()  # type: ignore[abstract]
