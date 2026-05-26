from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)

    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_user_id])




class AdminDailyMetric(Base):
    __tablename__ = "admin_daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stat_date: Mapped[date_type] = mapped_column(Date, unique=True, nullable=False, index=True)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class PlatformAccessSetting(Base):
    __tablename__ = "platform_access_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_platform_access_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class PlatformAllowedEmail(Base):
    __tablename__ = "platform_allowed_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class PlatformInvitation(Base):
    __tablename__ = "platform_invitations"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'accepted', 'revoked')", name="ck_platform_invitations_status"),
        CheckConstraint(
            "premium_tier IN ('free', 'trubadur', 'cronicar', 'rapsod')",
            name="ck_platform_invitations_premium_tier",
        ),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    temporary_password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    premium_tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    premium_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    accepted_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    accepted_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[accepted_user_id])


class SiteFeedback(Base):
    __tablename__ = "site_feedback"
    __table_args__ = (
        CheckConstraint("kind IN ('feedback', 'bug')", name="ck_site_feedback_kind"),
        CheckConstraint("status IN ('open', 'closed')", name="ck_site_feedback_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    page_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    support_conversation_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    support_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    resolver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[resolved_by])
    support_conversation: Mapped[Optional["Conversation"]] = relationship("Conversation", foreign_keys=[support_conversation_id])
