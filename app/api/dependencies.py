from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """リクエスト元のIPアドレスを取得（監査ログ用）"""
    return request.client.host if request.client else None
