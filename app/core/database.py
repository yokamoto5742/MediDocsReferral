import json
import time
from contextlib import contextmanager
from typing import Iterator

import boto3
import psycopg2
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

settings = get_settings()

engine = create_engine(
    settings.get_database_url(),
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class _RotatingCredentials:
    """Secrets Manager の DB 認証情報を短TTLでキャッシュする"""

    def __init__(self, secret_name: str, ttl_seconds: int, region_name: str) -> None:
        self._secret_name = secret_name
        self._ttl_seconds = ttl_seconds
        self._client = boto3.client("secretsmanager", region_name=region_name)
        self._cache: tuple[str, str] | None = None
        self._fetched_at: float = 0.0

    def _fetch(self) -> tuple[str, str]:
        response = self._client.get_secret_value(SecretId=self._secret_name)
        data = json.loads(response["SecretString"])
        return data["username"], data["password"]

    def get(self, force_refresh: bool = False) -> tuple[str, str]:
        now = time.monotonic()
        expired = now - self._fetched_at >= self._ttl_seconds
        if force_refresh or self._cache is None or expired:
            self._cache = self._fetch()
            self._fetched_at = now
        return self._cache


if settings.db_secret_name:
    _credentials = _RotatingCredentials(
        settings.db_secret_name,
        settings.db_secret_ttl_seconds,
        settings.aws_region,
    )

    @event.listens_for(engine, "do_connect")
    def _inject_rotating_credentials(dialect, conn_rec, cargs, cparams):
        """接続確立直前に最新の認証情報を注入し、ローテーション直後の認証失敗時は1回だけ再取得して再接続する"""
        user, password = _credentials.get()
        cparams["user"] = user
        cparams["password"] = password
        try:
            return dialect.connect(*cargs, **cparams)
        except psycopg2.OperationalError:
            user, password = _credentials.get(force_refresh=True)
            cparams["user"] = user
            cparams["password"] = password
            return dialect.connect(*cargs, **cparams)


def get_db() -> Iterator[Session]:
    """FastAPI Depends 用"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session() -> Iterator[Session]:
    """サービス層用コンテキストマネージャ"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
