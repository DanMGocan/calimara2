from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class TheatrePlay(Base):
    __tablename__ = "theatre_plays"
    __table_args__ = (
        CheckConstraint("status IN ('setup', 'active', 'completed')", name="ck_theatre_plays_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="setup", nullable=False)
    current_scene_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("theatre_scenes.id", ondelete="SET NULL", use_alter=True, name="fk_theatre_plays_current_scene"),
        nullable=True,
        index=True,
    )
    current_character_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("theatre_characters.id", ondelete="SET NULL", use_alter=True, name="fk_theatre_plays_current_character"),
        nullable=True,
        index=True,
    )
    current_actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id], back_populates="created_theatre_plays")
    members: Mapped[List["TheatreMember"]] = relationship("TheatreMember", back_populates="play", cascade="all, delete-orphan")
    characters: Mapped[List["TheatreCharacter"]] = relationship("TheatreCharacter", back_populates="play", cascade="all, delete-orphan", foreign_keys="TheatreCharacter.play_id")
    join_requests: Mapped[List["TheatreJoinRequest"]] = relationship("TheatreJoinRequest", back_populates="play", cascade="all, delete-orphan")
    scenes: Mapped[List["TheatreScene"]] = relationship("TheatreScene", back_populates="play", cascade="all, delete-orphan", foreign_keys="TheatreScene.play_id")
    entries: Mapped[List["TheatreEntry"]] = relationship("TheatreEntry", back_populates="play", cascade="all, delete-orphan")


class TheatreMember(Base):
    __tablename__ = "theatre_members"
    __table_args__ = (
        CheckConstraint("role IN ('creator', 'actor')", name="ck_theatre_members_role"),
        UniqueConstraint("play_id", "user_id", name="uq_theatre_member"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    play_id: Mapped[int] = mapped_column(Integer, ForeignKey("theatre_plays.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), default="actor", nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    play: Mapped["TheatrePlay"] = relationship("TheatrePlay", foreign_keys=[play_id], back_populates="members")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="theatre_memberships")


class TheatreCharacter(Base):
    __tablename__ = "theatre_characters"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_theatre_characters_status"),
        UniqueConstraint("play_id", "name", name="uq_theatre_character_name"),
        Index(
            "uq_theatre_character_assigned_user",
            "play_id",
            "assigned_user_id",
            unique=True,
            postgresql_where=text("assigned_user_id IS NOT NULL"),
            sqlite_where=text("assigned_user_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    play_id: Mapped[int] = mapped_column(Integer, ForeignKey("theatre_plays.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    proposed_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    play: Mapped["TheatrePlay"] = relationship("TheatrePlay", foreign_keys=[play_id], back_populates="characters")
    proposer: Mapped[Optional["User"]] = relationship("User", foreign_keys=[proposed_by])
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approved_by])
    assigned_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_user_id])


class TheatreJoinRequest(Base):
    __tablename__ = "theatre_join_requests"
    __table_args__ = (
        CheckConstraint("direction IN ('application', 'invitation')", name="ck_theatre_join_requests_direction"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_theatre_join_requests_status"),
        Index(
            "uq_theatre_join_requests_pending_character",
            "play_id",
            "character_id",
            unique=True,
            postgresql_where=text("status = 'pending' AND character_id IS NOT NULL"),
            sqlite_where=text("status = 'pending' AND character_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    play_id: Mapped[int] = mapped_column(Integer, ForeignKey("theatre_plays.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    initiator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    character_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("theatre_characters.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    responded_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    play: Mapped["TheatrePlay"] = relationship("TheatrePlay", foreign_keys=[play_id], back_populates="join_requests")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    initiator: Mapped["User"] = relationship("User", foreign_keys=[initiator_id])
    character: Mapped[Optional["TheatreCharacter"]] = relationship("TheatreCharacter", foreign_keys=[character_id])
    responder: Mapped[Optional["User"]] = relationship("User", foreign_keys=[responded_by])


class TheatreScene(Base):
    __tablename__ = "theatre_scenes"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'ended')", name="ck_theatre_scenes_status"),
        UniqueConstraint("play_id", "scene_number", name="uq_theatre_scene_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    play_id: Mapped[int] = mapped_column(Integer, ForeignKey("theatre_plays.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    opened_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ended_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    play: Mapped["TheatrePlay"] = relationship("TheatrePlay", foreign_keys=[play_id], back_populates="scenes")
    opener: Mapped[Optional["User"]] = relationship("User", foreign_keys=[opened_by])
    ender: Mapped[Optional["User"]] = relationship("User", foreign_keys=[ended_by])
    entries: Mapped[List["TheatreEntry"]] = relationship("TheatreEntry", back_populates="scene", cascade="all, delete-orphan")


class TheatreEntry(Base):
    __tablename__ = "theatre_entries"
    __table_args__ = (
        CheckConstraint("entry_type IN ('scene_opening', 'line', 'stage_direction', 'scene_end')", name="ck_theatre_entries_type"),
        CheckConstraint("moderation_status IN ('pending', 'approved', 'flagged', 'rejected')", name="ck_theatre_entries_moderation_status"),
        UniqueConstraint("scene_id", "position", name="uq_theatre_entry_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    play_id: Mapped[int] = mapped_column(Integer, ForeignKey("theatre_plays.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id: Mapped[int] = mapped_column(Integer, ForeignKey("theatre_scenes.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("theatre_characters.id", ondelete="SET NULL"), nullable=True, index=True)
    next_character_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("theatre_characters.id", ondelete="SET NULL"), nullable=True, index=True)
    entry_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    play: Mapped["TheatrePlay"] = relationship("TheatrePlay", foreign_keys=[play_id], back_populates="entries")
    scene: Mapped["TheatreScene"] = relationship("TheatreScene", foreign_keys=[scene_id], back_populates="entries")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
    character: Mapped[Optional["TheatreCharacter"]] = relationship("TheatreCharacter", foreign_keys=[character_id])
    next_character: Mapped[Optional["TheatreCharacter"]] = relationship("TheatreCharacter", foreign_keys=[next_character_id])
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
