from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class GologaniTransaction(Base):
    __tablename__ = "gologani_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="gologani_transactions")




class ShopItem(Base):
    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    slot: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    asset_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    inventory_entries: Mapped[List["UserInventoryItem"]] = relationship(
        "UserInventoryItem",
        back_populates="item",
        cascade="all, delete-orphan",
    )
    equipped_entries: Mapped[List["UserEquippedItem"]] = relationship(
        "UserEquippedItem",
        back_populates="item",
        cascade="all, delete-orphan",
    )




class UserInventoryItem(Base):
    __tablename__ = "user_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_items.id", ondelete="CASCADE"), nullable=False, index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="inventory_items")
    item: Mapped["ShopItem"] = relationship("ShopItem", back_populates="inventory_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "item_id", name="uq_user_inventory_item"),
    )




class UserEquippedItem(Base):
    __tablename__ = "user_equipped_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_items.id", ondelete="CASCADE"), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String(40), nullable=False)
    equipped_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="equipped_items")
    item: Mapped["ShopItem"] = relationship("ShopItem", back_populates="equipped_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "slot", name="uq_user_equipped_slot"),
    )


