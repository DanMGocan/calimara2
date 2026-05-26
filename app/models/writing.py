from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class DiacriticsUsageEvent(Base):
    __tablename__ = "diacritics_usage_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'succeeded', 'failed')",
            name="ck_diacritics_usage_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # Historical DB column name kept for preserved databases; it now stores charged characters.
    character_count: Mapped[int] = mapped_column("word_count", Integer, default=0, nullable=False)
    quota_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    quota_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    @property
    def word_count(self) -> int:
        return self.character_count

    @word_count.setter
    def word_count(self, value: int) -> None:
        self.character_count = value
