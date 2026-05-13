from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class PostDraft(Base):
    __tablename__ = "post_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    explanatory_note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    category: Mapped[str] = mapped_column(String(100), default="poezie", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="post_drafts")




class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True, nullable=False) # SEO-friendly URL slug
    content: Mapped[str] = mapped_column(Text, nullable=False)
    explanatory_note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Category key
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Genre key
    ai_critic_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False) # Track post views
    seconds_listened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    # Moderation fields
    moderation_status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Theme analysis fields
    themes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    feelings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    theme_analysis_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="posts")
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="post")
    likes: Mapped[List["Like"]] = relationship("Like", back_populates="post")
    super_likes: Mapped[List["SuperLike"]] = relationship("SuperLike", back_populates="post", cascade="all, delete-orphan")
    featured_by: Mapped[List["FeaturedPost"]] = relationship("FeaturedPost", back_populates="post")
    series_entry: Mapped[Optional["SeriesPost"]] = relationship(
        "SeriesPost", back_populates="post", cascade="all, delete-orphan", uselist=False
    )
    audio_versions: Mapped[List["PostAudio"]] = relationship(
        "PostAudio", back_populates="post", cascade="all, delete-orphan"
    )
    reports: Mapped[List["PostReport"]] = relationship("PostReport", back_populates="post")

    @hybrid_property
    def likes_count(self) -> int:
        """Return the number of likes for this post"""
        return len(self.likes)

    @likes_count.expression
    def likes_count(cls):
        return (
            select(func.count(Like.id))
            .where(Like.post_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

    @hybrid_property
    def super_likes_count(self) -> int:
        """Return the number of super-apreciez for this post"""
        return len(self.super_likes)

    @super_likes_count.expression
    def super_likes_count(cls):
        return (
            select(func.count(SuperLike.id))
            .where(SuperLike.post_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

    @property
    def approved_comments(self):
        """Return only approved comments from the eager-loaded comments relationship"""
        return [c for c in self.comments if c.approved]




class PostAudio(Base):
    __tablename__ = "post_audio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    requester_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "tts" | "author"
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    tts_character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    quota_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    storage_backend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    voice_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transcript_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderation_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    post: Mapped["Post"] = relationship("Post", foreign_keys=[post_id], back_populates="audio_versions")
    requester: Mapped[Optional["User"]] = relationship("User", foreign_keys=[requester_user_id])


class PostReport(Base):
    __tablename__ = "post_reports"
    __table_args__ = (
        CheckConstraint("reason_type IN ('offensive', 'plagiarism')", name="ck_post_reports_reason_type"),
        CheckConstraint("status IN ('open', 'resolved', 'dismissed')", name="ck_post_reports_status"),
        UniqueConstraint("post_id", "reporter_user_id", "reason_type", name="uq_post_reports_post_reporter_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True)
    reporter_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reason_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    post_title_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    post_slug_snapshot: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    post_author_username_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    post: Mapped[Optional["Post"]] = relationship("Post", back_populates="reports")
    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_user_id])
    reviewer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by])



class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_robot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Moderation fields
    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    commenter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], back_populates="comments")
    comment_moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])



class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="likes")
    liker: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], back_populates="likes")




class SuperLike(Base):
    __tablename__ = "super_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="super_likes")
    user: Mapped["User"] = relationship("User", back_populates="super_likes_given")

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_super_likes_user_post"),
    )
