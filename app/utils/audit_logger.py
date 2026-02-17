import json
import logging
from datetime import UTC, datetime
from typing import Any


audit_logger = logging.getLogger("audit")


def log_audit_event(
    event_type: str,
    user_ip: str | None = None,
    document_type: str | None = None,
    model: str | None = None,
    success: bool = True,
    error_message: str | None = None,
    **kwargs: Any
) -> None:
    """
    監査ログを記録

    個人情報（PHI）を含む内容は記録しない
    カルテテキスト、生成結果、プロンプト内容は記録対象外
    """
    log_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event_type": event_type,
        "success": success,
    }

    if user_ip:
        log_data["user_ip"] = user_ip
    if document_type:
        log_data["document_type"] = document_type
    if model:
        log_data["model"] = model
    if error_message:
        log_data["error_message"] = error_message

    log_data.update(kwargs)

    audit_logger.info(json.dumps(log_data, ensure_ascii=False))
