import json
from abc import ABC, abstractmethod

from app.core.constants import (
    DEFAULT_SUMMARY_PROMPT,
    GROUNDING_INSTRUCTION,
    KARTE_JSON_INSTRUCTION,
    REFINEMENT_INSTRUCTION,
)
from app.core.database import get_db_session
from app.schemas.summary import SummaryRequest
from app.services.prompt_service import get_prompt


def _is_json_text(text: str) -> bool:
    """テキストがJSON形式かどうかを判定"""
    stripped = text.strip()
    if not stripped.startswith(("{", "[")):
        return False
    try:
        json.loads(stripped)
        return True
    except json.JSONDecodeError:
        return False


class BaseAPIClient(ABC):
    @abstractmethod
    def generate(
        self, prompt: str, model_name: str, system_prompt: str = ""
    ) -> tuple[str, int, int]:
        """
        プロンプトからテキストを生成
        Args:
            prompt: 生成用プロンプト
            model_name: 使用モデル名
            system_prompt: システムプロンプト(空の場合は指定しない)
        Returns:
            (生成されたテキスト, 入力トークン数, 出力トークン数)
        Raises:
            APIError: API呼び出しに失敗した場合
        """
        pass

    def create_summary_prompt(self, request: SummaryRequest) -> tuple[str, str]:
        """(システムプロンプト, ユーザープロンプト) を構築"""
        # プロンプト未登録・内容が空・DB取得失敗のいずれもデフォルトプロンプトで生成を続ける
        prompt_template = DEFAULT_SUMMARY_PROMPT
        try:
            with get_db_session() as db:
                prompt_data = get_prompt(
                    db, request.department, request.document_type, request.doctor
                )
                if prompt_data and prompt_data.content:
                    prompt_template = prompt_data.content
        except Exception:
            pass

        system_parts = [prompt_template.strip(), GROUNDING_INSTRUCTION]
        if _is_json_text(request.medical_text):
            system_parts.append(KARTE_JSON_INSTRUCTION)

        user_parts = [f"<カルテ情報>\n{request.medical_text}\n</カルテ情報>"]

        if request.referral_purpose.strip():
            user_parts.append(f"<紹介目的>\n{request.referral_purpose}\n</紹介目的>")

        if request.current_prescription.strip():
            user_parts.append(
                f"<現在の処方>\n{request.current_prescription}\n</現在の処方>"
            )

        if request.additional_info.strip():
            user_parts.append(f"<追加情報>\n{request.additional_info}\n</追加情報>")

        # 評価結果を反映した再生成の場合、前回の出力と評価結果を含める
        if request.previous_summary.strip() and request.evaluation_feedback.strip():
            user_parts.append(
                f"<前回の生成結果>\n{request.previous_summary}\n</前回の生成結果>"
            )
            user_parts.append(f"<評価結果>\n{request.evaluation_feedback}\n</評価結果>")
            system_parts.append(REFINEMENT_INSTRUCTION)

        return "\n\n".join(system_parts), "\n\n".join(user_parts)

    def generate_summary(
        self, request: SummaryRequest, model_name: str
    ) -> tuple[str, int, int]:
        """リクエスト内容から文書を生成"""
        system_prompt, user_prompt = self.create_summary_prompt(request)
        return self.generate(user_prompt, model_name, system_prompt)
