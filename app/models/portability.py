from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class UserDataImport(Base):
    __tablename__ = "user_data_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_export_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    profile_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    media_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ImportedPostSnapshot(Base):
    __tablename__ = "imported_post_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", "source_stable_id", name="uq_imported_post_snapshot_user_stable"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    import_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user_data_imports.id", ondelete="SET NULL"), nullable=True, index=True)
    source_export_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_stable_id: Mapped[str] = mapped_column(String(500), nullable=False)
    source_post_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_slug: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    source_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    imported_view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_super_likes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    public_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    audio_playback_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    audio_download_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    extra_data: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
