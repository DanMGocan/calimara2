from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Boolean, ForeignKey, JSON, Numeric, select
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
    subtitle: Mapped[Optional[str]] = mapped_column(String(500), nullable=True) # User motto
    avatar_seed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # DiceBear avatar seed
    
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
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    posts: Mapped[List["Post"]] = relationship("Post", foreign_keys="Post.user_id", back_populates="owner")
    comments: Mapped[List["Comment"]] = relationship("Comment", foreign_keys="Comment.user_id", back_populates="commenter")
    likes: Mapped[List["Like"]] = relationship("Like", back_populates="liker")
    
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

    # Drama relationships
    dramas: Mapped[List["Drama"]] = relationship(
        "Drama",
        foreign_keys="Drama.user_id",
        cascade="all, delete-orphan"
    )
    drama_characters: Mapped[List["DramaCharacter"]] = relationship(
        "DramaCharacter",
        cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        cascade="all, delete-orphan"
    )

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True, nullable=False) # SEO-friendly URL slug
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Category key
    genre: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Genre key
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
    tags: Mapped[List["Tag"]] = relationship("Tag", back_populates="post")
    featured_by: Mapped[List["FeaturedPost"]] = relationship("FeaturedPost", back_populates="post")

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

    @property
    def approved_comments(self):
        """Return only approved comments from the eager-loaded comments relationship"""
        return [c for c in self.comments if c.approved]

class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    
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

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_name: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    post: Mapped["Post"] = relationship("Post", back_populates="tags")

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
            return sorted(self.messages, key=lambda m: m.created_at, reverse=True)[0]
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


class Drama(Base):
    __tablename__ = "dramas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    is_open_for_applications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    moderation_status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])
    characters: Mapped[List["DramaCharacter"]] = relationship("DramaCharacter", back_populates="drama", cascade="all, delete-orphan")
    acts: Mapped[List["DramaAct"]] = relationship("DramaAct", back_populates="drama", cascade="all, delete-orphan")
    likes: Mapped[List["DramaLike"]] = relationship("DramaLike", back_populates="drama", cascade="all, delete-orphan")
    comments: Mapped[List["DramaComment"]] = relationship("DramaComment", back_populates="drama", cascade="all, delete-orphan")
    invitations: Mapped[List["DramaInvitation"]] = relationship("DramaInvitation", back_populates="drama", cascade="all, delete-orphan")

    @hybrid_property
    def likes_count(self) -> int:
        return len(self.likes)

    @likes_count.expression
    def likes_count(cls):
        return (
            select(func.count(DramaLike.id))
            .where(DramaLike.drama_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

    @property
    def active_act(self) -> Optional["DramaAct"]:
        for act in self.acts:
            if act.status == "active":
                return act
        return None

    @property
    def approved_comments(self):
        return [c for c in self.comments if c.moderation_status == "approved"]


class DramaCharacter(Base):
    __tablename__ = "drama_characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    drama_id: Mapped[int] = mapped_column(Integer, ForeignKey("dramas.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    character_name: Mapped[str] = mapped_column(String(100), nullable=False)
    character_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    drama: Mapped["Drama"] = relationship("Drama", back_populates="characters")
    user: Mapped["User"] = relationship("User")
    replies: Mapped[List["DramaReply"]] = relationship("DramaReply", back_populates="character")

    @property
    def reply_count(self) -> int:
        return len(self.replies)


class DramaAct(Base):
    __tablename__ = "drama_acts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    drama_id: Mapped[int] = mapped_column(Integer, ForeignKey("dramas.id", ondelete="CASCADE"), nullable=False)
    act_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    setting: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    drama: Mapped["Drama"] = relationship("Drama", back_populates="acts")
    replies: Mapped[List["DramaReply"]] = relationship("DramaReply", back_populates="act", cascade="all, delete-orphan")

    @property
    def replies_ordered(self) -> List["DramaReply"]:
        return sorted(self.replies, key=lambda r: r.position)


class DramaReply(Base):
    __tablename__ = "drama_replies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    act_id: Mapped[int] = mapped_column(Integer, ForeignKey("drama_acts.id", ondelete="CASCADE"), nullable=False)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("drama_characters.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    stage_direction: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    act: Mapped["DramaAct"] = relationship("DramaAct", back_populates="replies")
    character: Mapped["DramaCharacter"] = relationship("DramaCharacter", back_populates="replies")


class DramaLike(Base):
    __tablename__ = "drama_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    drama_id: Mapped[int] = mapped_column(Integer, ForeignKey("dramas.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    drama: Mapped["Drama"] = relationship("Drama", back_populates="likes")
    liker: Mapped[Optional["User"]] = relationship("User")


class DramaComment(Base):
    __tablename__ = "drama_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    drama_id: Mapped[int] = mapped_column(Integer, ForeignKey("dramas.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    moderation_status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    moderation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    toxicity_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    moderated_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    drama: Mapped["Drama"] = relationship("Drama", back_populates="comments")
    commenter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    comment_moderator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[moderated_by])


class DramaInvitation(Base):
    __tablename__ = "drama_invitations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    drama_id: Mapped[int] = mapped_column(Integer, ForeignKey("dramas.id", ondelete="CASCADE"), nullable=False)
    from_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    to_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    character_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    drama: Mapped["Drama"] = relationship("Drama", back_populates="invitations")
    from_user: Mapped["User"] = relationship("User", foreign_keys=[from_user_id])
    to_user: Mapped["User"] = relationship("User", foreign_keys=[to_user_id])


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

    user: Mapped["User"] = relationship("User")
