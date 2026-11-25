from __future__ import annotations

from datetime import datetime, date as date_type
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "premium_tier IN ('free', 'trubadur', 'cronicar', 'rapsod')",
            name="ck_users_premium_tier",
        ),
        CheckConstraint(
            "referred_by_user_id IS NULL OR referred_by_user_id <> id",
            name="ck_users_referral_not_self",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    google_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    facebook_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    password_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # User motto
    avatar_seed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # DiceBear avatar seed
    cover_seed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # DiceBear cover seed
    location: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    youtube_playlist_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    profile_photo_storage_backend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    profile_photo_storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    profile_photo_content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    profile_photo_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cover_photo_storage_backend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    cover_photo_storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cover_photo_content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cover_photo_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Admin and moderation privileges
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_moderator: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Social media links
    facebook_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    tiktok_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    instagram_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    x_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    bluesky_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    
    # Donation/support links
    patreon_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    paypal_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    buymeacoffee_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    
    # Suspension fields
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspension_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    suspended_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Stripe / Premium subscription
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    premium_tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    premium_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    gologani_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    referral_code: Mapped[Optional[str]] = mapped_column(String(24), unique=True, index=True, nullable=True)
    referred_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    referral_rewarded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    referral_reward_premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    referral_reward_qualified_gologani: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seconds_listened: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    email_comment_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_mention_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_analytics_digest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_admin_announcements: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    posts: Mapped[List["Post"]] = relationship("Post", foreign_keys="Post.user_id", back_populates="owner", cascade="save-update, merge, delete", passive_deletes=True)
    post_drafts: Mapped[List["PostDraft"]] = relationship("PostDraft", foreign_keys="PostDraft.user_id", back_populates="owner", cascade="all, delete-orphan")
    comments: Mapped[List["Comment"]] = relationship("Comment", foreign_keys="Comment.user_id", back_populates="commenter")
    comment_reactions: Mapped[List["CommentReaction"]] = relationship("CommentReaction", back_populates="user", cascade="all, delete-orphan")
    likes: Mapped[List["Like"]] = relationship("Like", back_populates="liker")
    super_likes_given: Mapped[List["SuperLike"]] = relationship("SuperLike", back_populates="user", cascade="all, delete-orphan")
    
    # Best friends relationships
    best_friends: Mapped[List["BestFriend"]] = relationship(
        "BestFriend", 
        foreign_keys="BestFriend.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Users who have this user as a best friend
    friend_of: Mapped[List["BestFriend"]] = relationship(
        "BestFriend",
        foreign_keys="BestFriend.friend_user_id", 
        back_populates="friend",
        cascade="save-update, merge, delete", passive_deletes=True
    )

    # One-way follow relationships
    following_relations: Mapped[List["UserFollow"]] = relationship(
        "UserFollow",
        foreign_keys="UserFollow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan",
    )
    follower_relations: Mapped[List["UserFollow"]] = relationship(
        "UserFollow",
        foreign_keys="UserFollow.followed_id",
        back_populates="followed",
        cascade="all, delete-orphan",
    )
    
    # Featured posts by this user
    featured_posts: Mapped[List["FeaturedPost"]] = relationship(
        "FeaturedPost",
        foreign_keys="FeaturedPost.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Series owned by this user
    owned_series: Mapped[List["Series"]] = relationship(
        "Series",
        foreign_keys="Series.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    audio_playlists: Mapped[List["AudioPlaylist"]] = relationship(
        "AudioPlaylist",
        foreign_keys="AudioPlaylist.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    # Clubs owned by this user
    owned_clubs: Mapped[List["Club"]] = relationship(
        "Club",
        foreign_keys="Club.owner_id",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    # Club memberships of this user
    club_memberships: Mapped[List["ClubMember"]] = relationship(
        "ClubMember",
        foreign_keys="ClubMember.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Theatre plays created by this user
    created_theatre_plays: Mapped[List["TheatrePlay"]] = relationship(
        "TheatrePlay",
        foreign_keys="TheatrePlay.creator_id",
        back_populates="creator",
        cascade="all, delete-orphan",
    )

    # Theatre play memberships for this user
    theatre_memberships: Mapped[List["TheatreMember"]] = relationship(
        "TheatreMember",
        foreign_keys="TheatreMember.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    created_stafeta_works: Mapped[List["StafetaWork"]] = relationship(
        "StafetaWork",
        foreign_keys="StafetaWork.creator_id",
        back_populates="creator",
        cascade="all, delete-orphan",
    )
    stafeta_assignments: Mapped[List["StafetaAssignment"]] = relationship(
        "StafetaAssignment",
        foreign_keys="StafetaAssignment.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    stafeta_segments: Mapped[List["StafetaSegment"]] = relationship(
        "StafetaSegment",
        foreign_keys="StafetaSegment.author_id",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    stafeta_participation: Mapped[Optional["StafetaParticipant"]] = relationship(
        "StafetaParticipant",
        foreign_keys="StafetaParticipant.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # User awards
    awards: Mapped[List["UserAward"]] = relationship(
        "UserAward",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Messages relationships
    sent_messages: Mapped[List["Message"]] = relationship(
        "Message",
        foreign_keys="Message.sender_id",
        cascade="all, delete-orphan"
    )

    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    email_outbox_items: Mapped[List["EmailOutbox"]] = relationship(
        "EmailOutbox",
        foreign_keys="EmailOutbox.recipient_user_id",
        back_populates="recipient_user",
    )
    forum_threads: Mapped[List["ForumThread"]] = relationship(
        "ForumThread",
        foreign_keys="ForumThread.author_id",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    forum_replies: Mapped[List["ForumReply"]] = relationship(
        "ForumReply",
        foreign_keys="ForumReply.author_id",
        back_populates="author",
        cascade="all, delete-orphan",
    )
    gologani_transactions: Mapped[List["GologaniTransaction"]] = relationship(
        "GologaniTransaction",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    inventory_items: Mapped[List["UserInventoryItem"]] = relationship(
        "UserInventoryItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    equipped_items: Mapped[List["UserEquippedItem"]] = relationship(
        "UserEquippedItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    referred_by: Mapped[Optional["User"]] = relationship(
        "User",
        remote_side="User.id",
        foreign_keys=[referred_by_user_id],
        back_populates="referred_users",
    )
    referred_users: Mapped[List["User"]] = relationship(
        "User",
        foreign_keys=[referred_by_user_id],
        back_populates="referred_by",
    )

    @property
    def is_premium(self) -> bool:
        if self.premium_until is None:
            return False
        from ..week_util import utcnow_naive
        return self.premium_until > utcnow_naive()

    @property
    def has_audio_access(self) -> bool:
        return self.is_premium and self.premium_tier in {"cronicar", "rapsod"}

    @property
    def has_author_audio_access(self) -> bool:
        return self.is_premium and self.premium_tier == "rapsod"
