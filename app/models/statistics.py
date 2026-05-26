from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class PageView(Base):
    __tablename__ = "page_views"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bot_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    referrer_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content_owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class AudioListenEvent(Base):
    __tablename__ = "audio_listen_events"
    __table_args__ = (
        CheckConstraint("seconds > 0 AND seconds <= 60", name="ck_audio_listen_events_seconds"),
        CheckConstraint("mode IN ('poezie', 'proza_scurta', 'toate')", name="ck_audio_listen_events_mode"),
        UniqueConstraint("event_id", name="uq_audio_listen_events_event_id"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    audio_id: Mapped[int] = mapped_column(Integer, ForeignKey("post_audio.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    content_owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    listener_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)




class DailyStat(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (
        UniqueConstraint("stat_date", "content_type", "content_key", name="unique_daily_stat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    stat_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)
    content_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_views: Mapped[int] = mapped_column(Integer, default=0)
    unique_views: Mapped[int] = mapped_column(Integer, default=0)
    bot_views: Mapped[int] = mapped_column(Integer, default=0)
    logged_in_views: Mapped[int] = mapped_column(Integer, default=0)
    anonymous_views: Mapped[int] = mapped_column(Integer, default=0)
    desktop_views: Mapped[int] = mapped_column(Integer, default=0)
    mobile_views: Mapped[int] = mapped_column(Integer, default=0)
    tablet_views: Mapped[int] = mapped_column(Integer, default=0)
