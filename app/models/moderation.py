from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class ModerationLog(Base):
    __tablename__ = "moderation_logs"
    __table_args__ = (
        CheckConstraint(
            "content_type IN ('post', 'comment', 'audio', 'forum_thread', 'forum_reply', 'theatre_entry', 'stafeta_segment')",
            name="ck_moderation_logs_content_type",
        ),
        CheckConstraint("ai_decision IN ('approved', 'flagged', 'rejected')", name="ck_moderation_logs_ai_decision"),
        CheckConstraint("human_decision IN ('approved', 'rejected', 'pending')", name="ck_moderation_logs_human_decision"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # AI decision and scores
    ai_decision: Mapped[str] = mapped_column(String(20), nullable=False)  # 'approved', 'flagged', 'rejected'
    toxicity_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    harassment_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    hate_speech_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    sexually_explicit_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    dangerous_content_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    romanian_profanity_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    ai_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Human review
    human_decision: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 'approved', 'rejected', 'pending'
    human_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    content_author: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
    
    @property
    def content_preview(self) -> str:
        """Get a preview of the moderated content"""
        labels = {
            "post": "Post",
            "comment": "Comment",
            "audio": "Audio",
            "forum_thread": "Forum thread",
            "forum_reply": "Forum reply",
            "theatre_entry": "Theatre entry",
            "stafeta_segment": "Stafeta segment",
        }
        return f"{labels.get(self.content_type, 'Content')} ID {self.content_id}"
    
    @property
    def needs_human_review(self) -> bool:
        """Check if this content needs human review"""
        return self.ai_decision == "flagged" and (self.human_decision is None or self.human_decision == "pending")


class ModerationWord(Base):
    """Admin-editable word that sends content straight to manual review."""

    __tablename__ = "moderation_words"
    __table_args__ = (
        CheckConstraint("category IN ('profanity', 'hate_speech')", name="ck_moderation_words_category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    word: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(20), default="profanity", nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
