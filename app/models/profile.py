from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class BestFriend(Base):
    __tablename__ = "best_friends"
    __table_args__ = (
        UniqueConstraint("user_id", "position", name="unique_bf_user_position"),
        UniqueConstraint("user_id", "friend_user_id", name="unique_bf_user_friend"),
        CheckConstraint("position BETWEEN 1 AND 2", name="chk_bf_position"),
        CheckConstraint("user_id != friend_user_id", name="chk_bf_no_self_friend"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="best_friends")
    friend: Mapped["User"] = relationship("User", foreign_keys=[friend_user_id], back_populates="friend_of")



class FeaturedPost(Base):
    __tablename__ = "featured_posts"
    __table_args__ = (
        UniqueConstraint("user_id", "position", name="unique_fp_user_position"),
        UniqueConstraint("user_id", "post_id", name="unique_fp_user_post"),
        CheckConstraint("position BETWEEN 1 AND 6", name="chk_fp_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="featured_posts")
    post: Mapped["Post"] = relationship("Post", foreign_keys=[post_id], back_populates="featured_by")



class UserAward(Base):
    __tablename__ = "user_awards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    award_title: Mapped[str] = mapped_column(String(255), nullable=False)
    award_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    award_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    award_type: Mapped[str] = mapped_column(String(20), nullable=False, default="writing")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", back_populates="awards")

