from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Date, Boolean, ForeignKey, JSON, Numeric, UniqueConstraint, select, Float
from sqlalchemy.orm import relationship, Mapped, mapped_column, registry
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from datetime import datetime, date as date_type
from typing import List, Optional

mapper_registry = registry()
Base = mapper_registry.generate_base()

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    google_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(Text, nullable=True) # User motto
    avatar_seed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # DiceBear avatar seed
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
    suspended_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Stripe / Premium subscription
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    premium_tier: Mapped[str] = mapped_column(String(20), default="free", nullable=False)
    premium_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    gologani_balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    posts: Mapped[List["Post"]] = relationship("Post", foreign_keys="Post.user_id", back_populates="owner")
    post_drafts: Mapped[List["PostDraft"]] = relationship("PostDraft", foreign_keys="PostDraft.user_id", back_populates="owner", cascade="all, delete-orphan")
    comments: Mapped[List["Comment"]] = relationship("Comment", foreign_keys="Comment.user_id", back_populates="commenter")
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
        back_populates="friend"
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

    @property
    def is_premium(self) -> bool:
        if self.premium_until is None:
            return False
        from .week_util import utcnow_naive
        return self.premium_until > utcnow_naive()

    @property
    def has_audio_access(self) -> bool:
        return self.is_premium and self.premium_tier in {"audio", "author_audio"}

    @property
    def has_author_audio_access(self) -> bool:
        return self.is_premium and self.premium_tier == "author_audio"


class PostDraft(Base):
    __tablename__ = "post_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="poezie", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="post_drafts")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True, nullable=False) # SEO-friendly URL slug
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Category key
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Genre key
    ai_critic_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False) # Track post views
    
    # Moderation fields
    moderation_status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Theme analysis fields
    themes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    feelings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    theme_analysis_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="posts")
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
    comments: Mapped[List["Comment"]] = relationship("Comment", back_populates="post")
    likes: Mapped[List["Like"]] = relationship("Like", back_populates="post")
    super_likes: Mapped[List["SuperLike"]] = relationship("SuperLike", back_populates="post", cascade="all, delete-orphan")
    featured_by: Mapped[List["FeaturedPost"]] = relationship("FeaturedPost", back_populates="post")
    series_entry: Mapped[Optional["SeriesPost"]] = relationship(
        "SeriesPost", back_populates="post", cascade="all, delete-orphan", uselist=False
    )
    audio_versions: Mapped[List["PostAudio"]] = relationship(
        "PostAudio", back_populates="post", cascade="all, delete-orphan"
    )

    @hybrid_property
    def likes_count(self) -> int:
        """Return the number of likes for this post"""
        return len(self.likes)

    @likes_count.expression
    def likes_count(cls):
        return (
            select(func.count(Like.id))
            .where(Like.post_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

    @hybrid_property
    def super_likes_count(self) -> int:
        """Return the number of super-apreciez for this post"""
        return len(self.super_likes)

    @super_likes_count.expression
    def super_likes_count(cls):
        return (
            select(func.count(SuperLike.id))
            .where(SuperLike.post_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

    @property
    def approved_comments(self):
        """Return only approved comments from the eager-loaded comments relationship"""
        return [c for c in self.comments if c.approved]


class PostAudio(Base):
    __tablename__ = "post_audio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    requester_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "tts" | "author"
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    tts_character_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    quota_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    storage_backend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    voice_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    transcript_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    transcript_match_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderation_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    post: Mapped["Post"] = relationship("Post", foreign_keys=[post_id], back_populates="audio_versions")
    requester: Mapped[Optional["User"]] = relationship("User", foreign_keys=[requester_user_id])

class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_robot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Moderation fields
    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    commenter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], back_populates="comments")
    comment_moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])

class Like(Base):
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="likes")
    liker: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id], back_populates="likes")


class SuperLike(Base):
    __tablename__ = "super_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="super_likes")
    user: Mapped["User"] = relationship("User", back_populates="super_likes_given")

    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_super_likes_user_post"),
    )


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    run_after: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class BestFriend(Base):
    __tablename__ = "best_friends"

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="featured_posts")
    post: Mapped["Post"] = relationship("Post", foreign_keys=[post_id], back_populates="featured_by")

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


class ForumThread(Base):
    __tablename__ = "forum_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    section: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id], back_populates="forum_threads")
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
    replies: Mapped[List["ForumReply"]] = relationship(
        "ForumReply",
        back_populates="thread",
        cascade="all, delete-orphan",
    )

    @hybrid_property
    def approved_reply_count(self) -> int:
        return len([reply for reply in self.replies if reply.moderation_status == "approved"])

    @approved_reply_count.expression
    def approved_reply_count(cls):
        return (
            select(func.count(ForumReply.id))
            .where(
                ForumReply.thread_id == cls.id,
                ForumReply.moderation_status == "approved",
            )
            .correlate(cls)
            .scalar_subquery()
        )


class ForumReply(Base):
    __tablename__ = "forum_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(Integer, ForeignKey("forum_threads.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    moderation_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    thread: Mapped["ForumThread"] = relationship("ForumThread", foreign_keys=[thread_id], back_populates="replies")
    author: Mapped["User"] = relationship("User", foreign_keys=[author_id], back_populates="forum_replies")
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user1_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    user2_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    user1: Mapped["User"] = relationship("User", foreign_keys=[user1_id])
    user2: Mapped["User"] = relationship("User", foreign_keys=[user2_id])
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

    def get_other_user(self, current_user_id: int) -> "User":
        """Get the other participant in the conversation"""
        return self.user2 if self.user1_id == current_user_id else self.user1
    
    def get_latest_message(self) -> Optional["Message"]:
        """Get the most recent message in the conversation"""
        if self.messages:
            return sorted(
                self.messages,
                key=lambda m: (m.created_at, m.id),
                reverse=True,
            )[0]
        return None

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id], overlaps="sent_messages")

class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'post' or 'comment'
    content_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # AI decision and scores
    ai_decision: Mapped[str] = mapped_column(String(20), nullable=False)  # 'approved', 'flagged', 'rejected'
    toxicity_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    harassment_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    hate_speech_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    sexually_explicit_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    dangerous_content_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    romanian_profanity_score: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    ai_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Human review
    human_decision: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 'approved', 'rejected', 'pending'
    human_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relationships
    content_author: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
    
    @property
    def content_preview(self) -> str:
        """Get a preview of the moderated content"""
        if self.content_type == "post":
            return f"Post ID {self.content_id}"
        else:
            return f"Comment ID {self.content_id}"
    
    @property
    def needs_human_review(self) -> bool:
        """Check if this content needs human review"""
        return self.ai_decision == "flagged" and (self.human_decision is None or self.human_decision == "pending")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="notifications")


class PageView(Base):
    __tablename__ = "page_views"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
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


class DailyStat(Base):
    __tablename__ = "daily_stats"

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
