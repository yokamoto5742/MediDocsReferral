import json
from abc import ABC, abstractmethod
from typing import Generator, Optional, Tuple, Union

from app.core.constants import (
    DEFAULT_DOCUMENT_TYPE,
    DEFAULT_SUMMARY_PROMPT,
    GROUNDING_INSTRUCTION,
    KARTE_JSON_INSTRUCTION,
    MESSAGES,
    REFINEMENT_INSTRUCTION,
)
from app.core.database import get_db_session
from app.services.prompt_service import get_prompt, get_selected_model
from app.utils.exceptions import APIError


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
    def __init__(self, api_key: str | None, default_model: str | None):
        self.api_key: str | None = api_key
        self.default_model: str | None = default_model

    @abstractmethod
    def initialize(self) -> bool:
        """APIクライアントを初期化"""
        pass

    @abstractmethod
    def _generate_content(
        self, prompt: str, model_name: str, system_prompt: str = ""
    ) -> Tuple[str, int, int]:
        """
        プロンプトから要約を生成
        Args:
            prompt: 生成用プロンプト
            model_name: 使用モデル名
            system_prompt: システムプロンプト(空の場合は指定しない)
        Returns:
            Tuple[str, int, int]: (生成された要約, 入力トークン数, 出力トークン数)
        Raises:
            APIError: API呼び出しに失敗した場合
        """
        pass

    def create_summary_prompt(
        self,
        medical_text: str,
        additional_info: str = "",
        current_prescription: str = "",
        department: str = "default",
        document_type: str = DEFAULT_DOCUMENT_TYPE,
        doctor: str = "default",
        referral_purpose: str = "",
        previous_summary: str = "",
        evaluation_feedback: str = "",
    ) -> Tuple[str, str]:
        """(システムプロンプト, ユーザープロンプト) を構築"""
        try:
            with get_db_session() as db:
                prompt_data = get_prompt(db, department, document_type, doctor)
                if prompt_data:
                    prompt_template = prompt_data.content
                else:
                    prompt_template = DEFAULT_SUMMARY_PROMPT
        except Exception:
            prompt_template = DEFAULT_SUMMARY_PROMPT

        system_parts = [str(prompt_template).strip(), GROUNDING_INSTRUCTION]
        if _is_json_text(medical_text):
            system_parts.append(KARTE_JSON_INSTRUCTION)

        user_parts = [f"<カルテ情報>\n{medical_text}\n</カルテ情報>"]

        if referral_purpose.strip():
            user_parts.append(f"<紹介目的>\n{referral_purpose}\n</紹介目的>")

        if current_prescription.strip():
            user_parts.append(f"<現在の処方>\n{current_prescription}\n</現在の処方>")

        if additional_info.strip():
            user_parts.append(f"<追加情報>\n{additional_info}\n</追加情報>")

        # 評価結果を反映した再生成の場合、前回の出力と評価結果を含める
        if previous_summary.strip() and evaluation_feedback.strip():
            user_parts.append(f"<前回の生成結果>\n{previous_summary}\n</前回の生成結果>")
            user_parts.append(f"<評価結果>\n{evaluation_feedback}\n</評価結果>")
            system_parts.append(REFINEMENT_INSTRUCTION)

        return "\n\n".join(system_parts), "\n\n".join(user_parts)

    def get_model_name(
        self,
        department: str,
        document_type: str,
        doctor: str
    ) -> str | None:
        """プロンプトから選択されたモデル名を取得"""
        try:
            with get_db_session() as db:
                selected = get_selected_model(db, department, document_type, doctor)
                if selected is not None:
                    return selected
        except Exception:
            pass
        return self.default_model

    def generate_summary(
        self,
        medical_text: str,
        additional_info: str = "",
        current_prescription: str = "",
        department: str = "default",
        document_type: str = DEFAULT_DOCUMENT_TYPE,
        doctor: str = "default",
        model_name: Optional[str] = None,
        referral_purpose: str = "",
        previous_summary: str = "",
        evaluation_feedback: str = "",
    ) -> Tuple[str, int, int]:
        try:
            self.initialize()

            if not model_name:
                model_name = self.get_model_name(department, document_type, doctor)

            if not model_name:
                raise APIError(MESSAGES["ERROR"]["MODEL_NAME_NOT_SPECIFIED"])

            system_prompt, user_prompt = self.create_summary_prompt(
                medical_text,
                additional_info,
                current_prescription,
                department,
                document_type,
                doctor,
                referral_purpose,
                previous_summary,
                evaluation_feedback,
            )

            return self._generate_content(user_prompt, model_name, system_prompt)

        except APIError as e:
            raise e
        except Exception as e:
            raise APIError(
                f"{self.__class__.__name__}でエラーが発生しました: {str(e)}"
            )

    def _generate_content_stream(
        self, prompt: str, model_name: str, system_prompt: str = ""
    ) -> Generator[Union[str, dict], None, None]:
        """ストリーミングのデフォルト実装"""
        text, input_tokens, output_tokens = self._generate_content(
            prompt, model_name, system_prompt
        )
        yield text
        yield {"input_tokens": input_tokens, "output_tokens": output_tokens}

    def generate_summary_stream(
        self,
        medical_text: str,
        additional_info: str = "",
        current_prescription: str = "",
        department: str = "default",
        document_type: str = DEFAULT_DOCUMENT_TYPE,
        doctor: str = "default",
        model_name: Optional[str] = None,
        referral_purpose: str = "",
        previous_summary: str = "",
        evaluation_feedback: str = "",
    ) -> Generator[Union[str, dict], None, None]:
        """ストリーミングで要約を生成"""
        try:
            self.initialize()

            if not model_name:
                model_name = self.get_model_name(department, document_type, doctor)

            if not model_name:
                raise APIError(MESSAGES["ERROR"]["MODEL_NAME_NOT_SPECIFIED"])

            system_prompt, user_prompt = self.create_summary_prompt(
                medical_text,
                additional_info,
                current_prescription,
                department,
                document_type,
                doctor,
                referral_purpose,
                previous_summary,
                evaluation_feedback,
            )

            yield from self._generate_content_stream(
                user_prompt, model_name, system_prompt
            )

        except APIError:
            raise
        except Exception as e:
            raise APIError(
                f"{self.__class__.__name__}でエラーが発生しました: {str(e)}"
            )
