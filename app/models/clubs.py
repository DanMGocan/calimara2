from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    motto: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    avatar_seed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    theme: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    speciality: Mapped[str] = mapped_column(String(20), nullable=False)
    featured_post_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("posts.id", ondelete="SET NULL"), nullable=True)
    featured_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id], back_populates="owned_clubs")
    memberships: Mapped[List["ClubMember"]] = relationship(
        "ClubMember", back_populates="club", cascade="all, delete-orphan"
    )
    join_requests: Mapped[List["ClubJoinRequest"]] = relationship(
        "ClubJoinRequest", back_populates="club", cascade="all, delete-orphan"
    )
    board_messages: Mapped[List["ClubBoardMessage"]] = relationship(
        "ClubBoardMessage", back_populates="club", cascade="all, delete-orphan"
    )
    featured_post: Mapped[Optional["Post"]] = relationship("Post", foreign_keys=[featured_post_id])




class ClubMember(Base):
    __tablename__ = "club_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    club_id: Mapped[int] = mapped_column(Integer, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id], back_populates="memberships")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="club_memberships")

    __table_args__ = (
        UniqueConstraint("club_id", "user_id", name="uq_club_member"),
    )




class ClubJoinRequest(Base):
    __tablename__ = "club_join_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    club_id: Mapped[int] = mapped_column(Integer, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # "application" | "invitation"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    initiator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    responded_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id], back_populates="join_requests")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    initiator: Mapped["User"] = relationship("User", foreign_keys=[initiator_id])
    responder: Mapped[Optional["User"]] = relationship("User", foreign_keys=[responded_by])




class ClubBoardMessage(Base):
    __tablename__ = "club_board_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    club_id: Mapped[int] = mapped_column(Integer, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("club_board_messages.id", ondelete="CASCADE"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    club: Mapped["Club"] = relationship("Club", foreign_keys=[club_id], back_populates="board_messages")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
    parent: Mapped[Optional["ClubBoardMessage"]] = relationship(
        "ClubBoardMessage",
        remote_side="ClubBoardMessage.id",
        back_populates="replies",
    )
    replies: Mapped[List["ClubBoardMessage"]] = relationship(
        "ClubBoardMessage",
        back_populates="parent",
        cascade="all, delete-orphan",
    )


