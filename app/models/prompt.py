from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class Prompt(Base):
    __tablename__ = "prompts"

    # NULL許可は型注釈から決まる (Mapped[X | None] が NULL 許可)
    id: Mapped[int] = mapped_column(primary_key=True)
    department: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(100))
    doctor: Mapped[str] = mapped_column(String(100))
    content: Mapped[str | None] = mapped_column(Text)
    selected_model: Mapped[str | None] = mapped_column(String(50))
    is_default: Mapped[bool | None] = mapped_column(default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("ix_prompts_lookup", "department", "document_type", "doctor"),
    )
