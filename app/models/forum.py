from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class ForumThread(Base):
    __tablename__ = "forum_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id], back_populates="forum_threads")
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
    replies: Mapped[List["ForumReply"]] = relationship(
        "ForumReply",
        back_populates="thread",
        cascade="all, delete-orphan",
    )

    @hybrid_property
    def approved_reply_count(self) -> int:
        return len([reply for reply in self.replies if reply.moderation_status == "approved"])

    @approved_reply_count.expression
    def approved_reply_count(cls):
        return (
            select(func.count(ForumReply.id))
            .where(
                ForumReply.thread_id == cls.id,
                ForumReply.moderation_status == "approved",
            )
            .correlate(cls)
            .scalar_subquery()
        )




class ForumReply(Base):
    __tablename__ = "forum_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(Integer, ForeignKey("forum_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    thread: Mapped["ForumThread"] = relationship("ForumThread", foreign_keys=[thread_id], back_populates="replies")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id], back_populates="forum_replies")
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])


