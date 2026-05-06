from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'post' or 'comment'
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
        if self.content_type == "post":
            return f"Post ID {self.content_id}"
        else:
            return f"Comment ID {self.content_id}"
    
    @property
    def needs_human_review(self) -> bool:
        """Check if this content needs human review"""
        return self.ai_decision == "flagged" and (self.human_decision is None or self.human_decision == "pending")


