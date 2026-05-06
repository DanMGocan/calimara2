from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
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
