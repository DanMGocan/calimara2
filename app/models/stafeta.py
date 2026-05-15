from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class StafetaParticipant(Base):
    __tablename__ = "stafeta_participants"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_stafeta_participant_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="stafeta_participation")


class StafetaWork(Base):
    __tablename__ = "stafeta_works"
    __table_args__ = (
        CheckConstraint("category IN ('poezie', 'proza_scurta')", name="ck_stafeta_works_category"),
        CheckConstraint("status IN ('active', 'published', 'cancelled')", name="ck_stafeta_works_status"),
        CheckConstraint("deadline_days IN (1, 3, 7)", name="ck_stafeta_works_deadline_days"),
        CheckConstraint("max_characters BETWEEN 1 AND 10000", name="ck_stafeta_works_max_characters"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="poezie")
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    deadline_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_characters: Mapped[int] = mapped_column(Integer, default=400, nullable=False)
    current_assignment_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("stafeta_assignments.id", ondelete="SET NULL", use_alter=True, name="fk_stafeta_works_current_assignment"),
        nullable=True,
        index=True,
    )
    current_holder_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    published_post_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id], back_populates="created_stafeta_works")
    current_holder: Mapped[Optional["User"]] = relationship("User", foreign_keys=[current_holder_user_id])
    published_post: Mapped[Optional["Post"]] = relationship("Post", foreign_keys=[published_post_id])
    assignments: Mapped[List["StafetaAssignment"]] = relationship("StafetaAssignment", back_populates="work", cascade="all, delete-orphan", foreign_keys="StafetaAssignment.work_id")
    segments: Mapped[List["StafetaSegment"]] = relationship("StafetaSegment", back_populates="work", cascade="all, delete-orphan")


class StafetaAssignment(Base):
    __tablename__ = "stafeta_assignments"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'active', 'refused', 'completed', 'expired', 'cancelled')", name="ck_stafeta_assignments_status"),
        CheckConstraint("source IN ('creator', 'specific', 'random', 'previous', 'timeout', 'return')", name="ck_stafeta_assignments_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_id: Mapped[int] = mapped_column(Integer, ForeignKey("stafeta_works.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    work: Mapped["StafetaWork"] = relationship("StafetaWork", foreign_keys=[work_id], back_populates="assignments")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="stafeta_assignments")
    assigned_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_by_id])
    segments: Mapped[List["StafetaSegment"]] = relationship("StafetaSegment", back_populates="assignment")


class StafetaSegment(Base):
    __tablename__ = "stafeta_segments"
    __table_args__ = (
        CheckConstraint("moderation_status IN ('pending', 'approved', 'flagged', 'rejected')", name="ck_stafeta_segments_moderation_status"),
        CheckConstraint("next_target_mode IN ('random', 'creator', 'previous', 'specific')", name="ck_stafeta_segments_next_target_mode"),
        UniqueConstraint("work_id", "position", name="uq_stafeta_segment_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    work_id: Mapped[int] = mapped_column(Integer, ForeignKey("stafeta_works.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("stafeta_assignments.id", ondelete="SET NULL"), nullable=True, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    next_target_mode: Mapped[str] = mapped_column(String(20), default="random", nullable=False)
    next_target_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    work: Mapped["StafetaWork"] = relationship("StafetaWork", foreign_keys=[work_id], back_populates="segments")
    assignment: Mapped[Optional["StafetaAssignment"]] = relationship("StafetaAssignment", foreign_keys=[assignment_id], back_populates="segments")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id], back_populates="stafeta_segments")
    next_target_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[next_target_user_id])
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
