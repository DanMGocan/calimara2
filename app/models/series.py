from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id], back_populates="owned_series")
    entries: Mapped[List["SeriesPost"]] = relationship(
        "SeriesPost", back_populates="series", cascade="all, delete-orphan"
    )



class SeriesPost(Base):
    __tablename__ = "series_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    series_id: Mapped[int] = mapped_column(Integer, ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    series: Mapped["Series"] = relationship("Series", foreign_keys=[series_id], back_populates="entries")
    post: Mapped["Post"] = relationship("Post", foreign_keys=[post_id], back_populates="series_entry")

    __table_args__ = (
        UniqueConstraint("series_id", "post_id", name="uq_series_post"),
        UniqueConstraint("post_id", name="uq_series_posts_post"),
        UniqueConstraint("series_id", "position", name="uq_series_position"),
    )


