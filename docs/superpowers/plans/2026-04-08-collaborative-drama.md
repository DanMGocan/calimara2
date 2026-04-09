# Collaborative Drama (Piese de Teatru) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add collaborative drama/play writing to Calimara, allowing users to create plays, invite participants as characters, write dialogue together async, and export as professional PDF.

**Architecture:** FastAPI monolith with Jinja2 server-side rendering. Subdomain-based multi-tenancy (SubdomainMiddleware). PostgreSQL with synchronous SQLAlchemy sessions. Modular routers in `app/routers/`. Centralized CRUD in `app/crud.py`. Session-based Google OAuth auth. All static assets in `/static/` (no inline CSS/JS per CLAUDE.md).

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy (Mapped annotations) / PostgreSQL / Jinja2 / Bootstrap 5 / WeasyPrint (new)

---

## Task 1: Database Schema

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/schema.sql`

- [ ] **Step 1.1** Add the new drama tables to the DROP cascade section at the top of `schema.sql`. Insert these lines BEFORE `DROP TABLE IF EXISTS moderation_logs CASCADE;` (since drama tables have no dependents among the existing tables, but they depend on `users`). The order must be children-first:

```sql
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS drama_invitations CASCADE;
DROP TABLE IF EXISTS drama_comments CASCADE;
DROP TABLE IF EXISTS drama_likes CASCADE;
DROP TABLE IF EXISTS drama_replies CASCADE;
DROP TABLE IF EXISTS drama_acts CASCADE;
DROP TABLE IF EXISTS drama_characters CASCADE;
DROP TABLE IF EXISTS dramas CASCADE;
```

- [ ] **Step 1.2** Add the `dramas` table after the `moderation_logs` section (and its indexes/triggers). Place a new section header comment `-- DRAMAS TABLE --` following the existing pattern:

```sql
-- ===================================
-- DRAMAS TABLE
-- ===================================
CREATE TABLE dramas (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    slug VARCHAR(300) UNIQUE NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'in_progress' NOT NULL
        CHECK (status IN ('in_progress', 'completed')),
    is_open_for_applications BOOLEAN DEFAULT TRUE,
    view_count INT DEFAULT 0 NOT NULL,
    moderation_status VARCHAR(20) DEFAULT 'approved' NOT NULL
        CHECK (moderation_status IN ('approved', 'pending', 'rejected', 'flagged')),
    moderation_reason TEXT,
    toxicity_score DECIMAL(3,2),
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dramas_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_dramas_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_dramas_slug ON dramas(slug);
CREATE INDEX idx_dramas_user_id ON dramas(user_id);
CREATE INDEX idx_dramas_status ON dramas(status);
CREATE INDEX idx_dramas_view_count ON dramas(view_count);
CREATE INDEX idx_dramas_created_at ON dramas(created_at);
```

- [ ] **Step 1.3** Add the `drama_characters` table:

```sql
-- ===================================
-- DRAMA CHARACTERS TABLE
-- ===================================
CREATE TABLE drama_characters (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    user_id INT NOT NULL,
    character_name VARCHAR(100) NOT NULL,
    character_description TEXT,
    is_creator BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_drama_user UNIQUE (drama_id, user_id),
    CONSTRAINT unique_drama_character_name UNIQUE (drama_id, character_name),
    CONSTRAINT fk_dc_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dc_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_dc_drama_id ON drama_characters(drama_id);
```

- [ ] **Step 1.4** Add the `drama_acts` table:

```sql
-- ===================================
-- DRAMA ACTS TABLE
-- ===================================
CREATE TABLE drama_acts (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    act_number INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    setting TEXT,
    status VARCHAR(20) DEFAULT 'active' NOT NULL
        CHECK (status IN ('active', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_drama_act_number UNIQUE (drama_id, act_number),
    CONSTRAINT fk_da_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE
);

CREATE INDEX idx_da_drama_id ON drama_acts(drama_id);
```

- [ ] **Step 1.5** Add the `drama_replies` table:

```sql
-- ===================================
-- DRAMA REPLIES TABLE
-- ===================================
CREATE TABLE drama_replies (
    id SERIAL PRIMARY KEY,
    act_id INT NOT NULL,
    character_id INT NOT NULL,
    content TEXT NOT NULL,
    stage_direction VARCHAR(500),
    position INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dr_act FOREIGN KEY (act_id) REFERENCES drama_acts(id) ON DELETE CASCADE,
    CONSTRAINT fk_dr_character FOREIGN KEY (character_id) REFERENCES drama_characters(id) ON DELETE CASCADE
);

CREATE INDEX idx_dr_act_position ON drama_replies(act_id, position);
```

- [ ] **Step 1.6** Add the `drama_likes` table:

```sql
-- ===================================
-- DRAMA LIKES TABLE
-- ===================================
CREATE TABLE drama_likes (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    user_id INT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT unique_drama_user_like UNIQUE (drama_id, user_id),
    CONSTRAINT unique_drama_ip_like UNIQUE (drama_id, ip_address),
    CONSTRAINT fk_dl_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dl_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_dl_drama_id ON drama_likes(drama_id);
```

- [ ] **Step 1.7** Add the `drama_comments` table:

```sql
-- ===================================
-- DRAMA COMMENTS TABLE
-- ===================================
CREATE TABLE drama_comments (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    user_id INT,
    author_name VARCHAR(255),
    content TEXT NOT NULL,
    moderation_status VARCHAR(20) DEFAULT 'approved' NOT NULL
        CHECK (moderation_status IN ('approved', 'pending', 'rejected', 'flagged')),
    moderation_reason TEXT,
    toxicity_score DECIMAL(3,2),
    moderated_by INT,
    moderated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_dco_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_dco_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT fk_dco_moderator FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_dco_drama_moderation ON drama_comments(drama_id, moderation_status);
```

- [ ] **Step 1.8** Add the `drama_invitations` table:

```sql
-- ===================================
-- DRAMA INVITATIONS TABLE
-- ===================================
CREATE TABLE drama_invitations (
    id SERIAL PRIMARY KEY,
    drama_id INT NOT NULL,
    from_user_id INT NOT NULL,
    to_user_id INT NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('invitation', 'application')),
    character_name VARCHAR(100),
    message TEXT,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL
        CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP,

    CONSTRAINT fk_di_drama FOREIGN KEY (drama_id) REFERENCES dramas(id) ON DELETE CASCADE,
    CONSTRAINT fk_di_from FOREIGN KEY (from_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_di_to FOREIGN KEY (to_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_di_drama_to_status ON drama_invitations(drama_id, to_user_id, status);
```

- [ ] **Step 1.9** Add the `notifications` table:

```sql
-- ===================================
-- NOTIFICATIONS TABLE
-- ===================================
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    link VARCHAR(500),
    is_read BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_notif_user_read_created ON notifications(user_id, is_read, created_at);
CREATE INDEX idx_notif_user_id ON notifications(user_id);
```

- [ ] **Step 1.10** Add update triggers for the new tables that have `updated_at`. Add these after the existing triggers section:

```sql
CREATE TRIGGER trg_dramas_updated_at BEFORE UPDATE ON dramas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_drama_replies_updated_at BEFORE UPDATE ON drama_replies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

- [ ] **Step 1.11** Commit: "Add drama, notification, and invitation tables to schema.sql"

---

## Task 2: Update initdb.py

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/scripts/initdb.py`

- [ ] **Step 2.1** Update the `tables` verification list (around line 126) to include all new tables. Change the list to:

```python
tables = ['users', 'posts', 'comments', 'likes', 'tags',
          'best_friends', 'featured_posts', 'user_awards',
          'conversations', 'messages', 'moderation_logs',
          'dramas', 'drama_characters', 'drama_acts',
          'drama_replies', 'drama_likes', 'drama_comments',
          'drama_invitations', 'notifications']
```

- [ ] **Step 2.2** Commit: "Update initdb.py to verify new drama and notification tables"

---

## Task 3: SQLAlchemy Models

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/app/models.py`

- [ ] **Step 3.1** Add the `Decimal` import at the top of the file. Change line 1 to:

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, select, Numeric
```

- [ ] **Step 3.2** Add the `Drama` model after the `ModerationLog` class (at the bottom of the file). Follow the exact Mapped annotation pattern used by `Post`:

```python
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
```

- [ ] **Step 3.3** Add `DramaCharacter` model:

```python
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
```

- [ ] **Step 3.4** Add `DramaAct` model:

```python
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
```

- [ ] **Step 3.5** Add `DramaReply` model:

```python
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
```

- [ ] **Step 3.6** Add `DramaLike`, `DramaComment`, `DramaInvitation` models:

```python
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
```

- [ ] **Step 3.7** Add `Notification` model:

```python
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship("User")
```

- [ ] **Step 3.8** Add drama-related relationships to the `User` model. After the `sent_messages` relationship (around line 86), add:

```python
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
```

- [ ] **Step 3.9** Commit: "Add SQLAlchemy models for drama, characters, acts, replies, likes, comments, invitations, and notifications"

---

## Task 4: Pydantic Schemas

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/app/schemas.py`

- [ ] **Step 4.1** Add all drama schemas at the end of `schemas.py`, after the existing moderation schemas. Add a section header:

```python
# ===================================
# DRAMA SCHEMAS
# ===================================

class DramaCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    character_name: str = Field(..., min_length=1, max_length=100)
    character_description: Optional[str] = None

class DramaUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    is_open_for_applications: Optional[bool] = None

class DramaCharacterResponse(BaseModel):
    id: int
    drama_id: int
    user_id: int
    character_name: str
    character_description: Optional[str] = None
    is_creator: bool
    joined_at: datetime
    username: Optional[str] = None
    avatar_seed: Optional[str] = None

    class Config:
        from_attributes = True

class DramaReplyResponse(BaseModel):
    id: int
    act_id: int
    character_id: int
    content: str
    stage_direction: Optional[str] = None
    position: int
    created_at: datetime
    character_name: Optional[str] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True

class DramaActResponse(BaseModel):
    id: int
    drama_id: int
    act_number: int
    title: str
    setting: Optional[str] = None
    status: str
    created_at: datetime
    replies: List[DramaReplyResponse] = []

    class Config:
        from_attributes = True

class DramaResponse(BaseModel):
    id: int
    user_id: int
    title: str
    slug: str
    description: Optional[str] = None
    status: str
    is_open_for_applications: bool
    view_count: int
    likes_count: int = 0
    created_at: datetime
    updated_at: datetime
    owner_username: Optional[str] = None
    owner_avatar_seed: Optional[str] = None
    characters: List[DramaCharacterResponse] = []
    acts: List[DramaActResponse] = []

    class Config:
        from_attributes = True

class ActCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    setting: Optional[str] = None

class ActUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    setting: Optional[str] = None

class ReplyCreate(BaseModel):
    content: str = Field(..., min_length=1)
    stage_direction: Optional[str] = Field(None, max_length=500)

class ReplyUpdate(BaseModel):
    content: Optional[str] = None
    stage_direction: Optional[str] = Field(None, max_length=500)

class ReplyReorder(BaseModel):
    reply_ids: List[int]

class InvitationCreate(BaseModel):
    to_username: str
    character_name: Optional[str] = Field(None, max_length=100)
    message: Optional[str] = None

class ApplicationCreate(BaseModel):
    character_name: str = Field(..., min_length=1, max_length=100)
    character_description: Optional[str] = None
    message: Optional[str] = None

class InvitationRespond(BaseModel):
    status: str = Field(..., pattern="^(accepted|rejected)$")

class DramaCommentCreate(BaseModel):
    content: str = Field(..., min_length=1)
    author_name: Optional[str] = None

# ===================================
# NOTIFICATION SCHEMAS
# ===================================

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    title: str
    message: Optional[str] = None
    link: Optional[str] = None
    is_read: bool
    metadata: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4.2** Commit: "Add Pydantic schemas for drama and notification features"

---

## Task 5: CRUD Functions - Drama Core

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/app/crud.py`

- [ ] **Step 5.1** Add a drama CRUD section at the end of `crud.py` (after the messages section). Add the following functions following the existing pattern (synchronous, `db: Session` first arg, direct model creation, `db.commit()` + `db.refresh()`):

```python
# ===================================
# DRAMA CRUD FUNCTIONS
# ===================================

def create_drama(db: Session, title: str, description: Optional[str], slug: str, user_id: int, character_name: str, character_description: Optional[str] = None) -> models.Drama:
    """Create a new drama and its first character (the creator)"""
    drama = models.Drama(
        user_id=user_id,
        title=title,
        slug=slug,
        description=description
    )
    db.add(drama)
    db.flush()  # Get the drama.id

    character = models.DramaCharacter(
        drama_id=drama.id,
        user_id=user_id,
        character_name=character_name,
        character_description=character_description,
        is_creator=True
    )
    db.add(character)
    db.commit()
    db.refresh(drama)
    return drama

def get_drama_by_slug(db: Session, slug: str) -> Optional[models.Drama]:
    """Get a drama by slug with all relationships eager-loaded"""
    return db.query(models.Drama).options(
        selectinload(models.Drama.characters).joinedload(models.DramaCharacter.user),
        selectinload(models.Drama.acts).selectinload(models.DramaAct.replies).joinedload(models.DramaReply.character),
        selectinload(models.Drama.likes),
        selectinload(models.Drama.comments).joinedload(models.DramaComment.commenter),
        joinedload(models.Drama.owner)
    ).filter(models.Drama.slug == slug).first()

def get_drama_by_id(db: Session, drama_id: int) -> Optional[models.Drama]:
    return db.query(models.Drama).filter(models.Drama.id == drama_id).first()

def get_dramas_by_user(db: Session, user_id: int, skip: int = 0, limit: int = 50) -> List[models.Drama]:
    return db.query(models.Drama).options(
        selectinload(models.Drama.characters),
        selectinload(models.Drama.likes),
        joinedload(models.Drama.owner)
    ).filter(models.Drama.user_id == user_id).order_by(models.Drama.created_at.desc()).offset(skip).limit(limit).all()

def get_all_dramas(db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 20) -> List[models.Drama]:
    """Get dramas across the platform for discovery page"""
    query = db.query(models.Drama).options(
        selectinload(models.Drama.characters),
        selectinload(models.Drama.likes),
        joinedload(models.Drama.owner)
    )
    if status_filter:
        query = query.filter(models.Drama.status == status_filter)
    return query.order_by(models.Drama.created_at.desc()).offset(skip).limit(limit).all()

def update_drama(db: Session, drama_id: int, update_data: dict) -> Optional[models.Drama]:
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        for key, value in update_data.items():
            if value is not None:
                setattr(drama, key, value)
        db.commit()
        db.refresh(drama)
    return drama

def delete_drama(db: Session, drama_id: int):
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        db.delete(drama)
        db.commit()
    return drama

def complete_drama(db: Session, drama_id: int) -> Optional[models.Drama]:
    """Mark drama as completed and close all active acts"""
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        drama.status = "completed"
        drama.is_open_for_applications = False
        # Complete any active acts
        for act in drama.acts:
            if act.status == "active":
                act.status = "completed"
        db.commit()
        db.refresh(drama)
    return drama

def increment_drama_view(db: Session, drama_id: int):
    drama = db.query(models.Drama).filter(models.Drama.id == drama_id).first()
    if drama:
        drama.view_count = drama.view_count + 1
        db.commit()

def ensure_unique_drama_slug(db: Session, base_slug: str, drama_id: Optional[int] = None) -> str:
    """Ensure the drama slug is unique"""
    slug = base_slug
    counter = 1
    while True:
        query = db.query(models.Drama).filter(models.Drama.slug == slug)
        if drama_id:
            query = query.filter(models.Drama.id != drama_id)
        if not query.first():
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1
        if counter > 100:
            slug = f"{base_slug}-{random.randint(1000, 9999)}"
            break
    return slug
```

- [ ] **Step 5.2** Add character CRUD:

```python
def get_drama_character(db: Session, character_id: int) -> Optional[models.DramaCharacter]:
    return db.query(models.DramaCharacter).filter(models.DramaCharacter.id == character_id).first()

def get_character_for_user_in_drama(db: Session, drama_id: int, user_id: int) -> Optional[models.DramaCharacter]:
    return db.query(models.DramaCharacter).filter(
        models.DramaCharacter.drama_id == drama_id,
        models.DramaCharacter.user_id == user_id
    ).first()

def create_drama_character(db: Session, drama_id: int, user_id: int, character_name: str, character_description: Optional[str] = None, is_creator: bool = False) -> models.DramaCharacter:
    character = models.DramaCharacter(
        drama_id=drama_id,
        user_id=user_id,
        character_name=character_name,
        character_description=character_description,
        is_creator=is_creator
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    return character

def delete_drama_character(db: Session, character_id: int):
    character = db.query(models.DramaCharacter).filter(models.DramaCharacter.id == character_id).first()
    if character:
        db.delete(character)
        db.commit()
    return character
```

- [ ] **Step 5.3** Add act CRUD:

```python
def create_drama_act(db: Session, drama_id: int, title: str, setting: Optional[str] = None) -> models.DramaAct:
    """Create a new act, auto-calculating act_number"""
    max_act = db.query(func.max(models.DramaAct.act_number)).filter(
        models.DramaAct.drama_id == drama_id
    ).scalar() or 0
    act = models.DramaAct(
        drama_id=drama_id,
        act_number=max_act + 1,
        title=title,
        setting=setting
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act

def get_drama_act(db: Session, drama_id: int, act_number: int) -> Optional[models.DramaAct]:
    return db.query(models.DramaAct).options(
        selectinload(models.DramaAct.replies).joinedload(models.DramaReply.character)
    ).filter(
        models.DramaAct.drama_id == drama_id,
        models.DramaAct.act_number == act_number
    ).first()

def update_drama_act(db: Session, act_id: int, update_data: dict) -> Optional[models.DramaAct]:
    act = db.query(models.DramaAct).filter(models.DramaAct.id == act_id).first()
    if act:
        for key, value in update_data.items():
            if value is not None:
                setattr(act, key, value)
        db.commit()
        db.refresh(act)
    return act

def complete_drama_act(db: Session, act_id: int) -> Optional[models.DramaAct]:
    act = db.query(models.DramaAct).filter(models.DramaAct.id == act_id).first()
    if act:
        act.status = "completed"
        db.commit()
        db.refresh(act)
    return act
```

- [ ] **Step 5.4** Commit: "Add drama core CRUD functions (drama, character, act)"

---

## Task 6: CRUD Functions - Replies & Interactions

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/app/crud.py`

- [ ] **Step 6.1** Add reply CRUD functions:

```python
def create_drama_reply(db: Session, act_id: int, character_id: int, content: str, stage_direction: Optional[str] = None) -> models.DramaReply:
    """Create a reply with auto-calculated position"""
    max_position = db.query(func.max(models.DramaReply.position)).filter(
        models.DramaReply.act_id == act_id
    ).scalar() or 0
    reply = models.DramaReply(
        act_id=act_id,
        character_id=character_id,
        content=content,
        stage_direction=stage_direction,
        position=max_position + 1
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply

def get_drama_reply(db: Session, reply_id: int) -> Optional[models.DramaReply]:
    return db.query(models.DramaReply).options(
        joinedload(models.DramaReply.character)
    ).filter(models.DramaReply.id == reply_id).first()

def update_drama_reply(db: Session, reply_id: int, update_data: dict) -> Optional[models.DramaReply]:
    reply = db.query(models.DramaReply).filter(models.DramaReply.id == reply_id).first()
    if reply:
        for key, value in update_data.items():
            if value is not None:
                setattr(reply, key, value)
        db.commit()
        db.refresh(reply)
    return reply

def delete_drama_reply(db: Session, reply_id: int):
    reply = db.query(models.DramaReply).filter(models.DramaReply.id == reply_id).first()
    if reply:
        db.delete(reply)
        db.commit()
    return reply

def reorder_drama_replies(db: Session, act_id: int, reply_ids: List[int]):
    """Reorder replies by updating position based on the order of reply_ids"""
    for index, reply_id in enumerate(reply_ids):
        reply = db.query(models.DramaReply).filter(
            models.DramaReply.id == reply_id,
            models.DramaReply.act_id == act_id
        ).first()
        if reply:
            reply.position = index + 1
    db.commit()
```

- [ ] **Step 6.2** Add drama like and comment CRUD:

```python
def create_drama_like(db: Session, drama_id: int, user_id: Optional[int] = None, ip_address: Optional[str] = None) -> Optional[models.DramaLike]:
    """Create a drama like (checking for duplicates)"""
    existing_like = None
    if user_id:
        existing_like = db.query(models.DramaLike).filter(
            models.DramaLike.drama_id == drama_id, models.DramaLike.user_id == user_id
        ).first()
    elif ip_address:
        existing_like = db.query(models.DramaLike).filter(
            models.DramaLike.drama_id == drama_id, models.DramaLike.ip_address == ip_address
        ).first()
    if existing_like:
        return None
    like = models.DramaLike(drama_id=drama_id, user_id=user_id, ip_address=ip_address)
    db.add(like)
    db.commit()
    db.refresh(like)
    return like

def create_drama_comment(db: Session, drama_id: int, content: str, user_id: Optional[int] = None, author_name: Optional[str] = None) -> models.DramaComment:
    comment = models.DramaComment(
        drama_id=drama_id,
        user_id=user_id,
        author_name=author_name,
        content=content
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment
```

- [ ] **Step 6.3** Add invitation/application CRUD:

```python
def create_drama_invitation(db: Session, drama_id: int, from_user_id: int, to_user_id: int, inv_type: str, character_name: Optional[str] = None, message: Optional[str] = None) -> models.DramaInvitation:
    invitation = models.DramaInvitation(
        drama_id=drama_id,
        from_user_id=from_user_id,
        to_user_id=to_user_id,
        type=inv_type,
        character_name=character_name,
        message=message
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return invitation

def get_drama_invitation(db: Session, invitation_id: int) -> Optional[models.DramaInvitation]:
    return db.query(models.DramaInvitation).options(
        joinedload(models.DramaInvitation.from_user),
        joinedload(models.DramaInvitation.to_user),
        joinedload(models.DramaInvitation.drama)
    ).filter(models.DramaInvitation.id == invitation_id).first()

def get_pending_invitations_for_drama(db: Session, drama_id: int) -> List[models.DramaInvitation]:
    return db.query(models.DramaInvitation).options(
        joinedload(models.DramaInvitation.from_user),
        joinedload(models.DramaInvitation.to_user)
    ).filter(
        models.DramaInvitation.drama_id == drama_id,
        models.DramaInvitation.status == "pending"
    ).all()

def respond_to_invitation(db: Session, invitation_id: int, status: str) -> Optional[models.DramaInvitation]:
    invitation = db.query(models.DramaInvitation).filter(models.DramaInvitation.id == invitation_id).first()
    if invitation:
        invitation.status = status
        invitation.responded_at = func.now()
        db.commit()
        db.refresh(invitation)
    return invitation

def get_user_dramas_as_participant(db: Session, user_id: int) -> List[models.Drama]:
    """Get all dramas where user is a participant (has a character)"""
    character_drama_ids = db.query(models.DramaCharacter.drama_id).filter(
        models.DramaCharacter.user_id == user_id
    ).subquery()
    return db.query(models.Drama).options(
        selectinload(models.Drama.characters),
        selectinload(models.Drama.likes),
        joinedload(models.Drama.owner)
    ).filter(models.Drama.id.in_(character_drama_ids)).order_by(models.Drama.updated_at.desc()).all()
```

- [ ] **Step 6.4** Commit: "Add CRUD functions for drama replies, likes, comments, and invitations"

---

## Task 7: CRUD Functions - Notifications

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/app/crud.py`

- [ ] **Step 7.1** Add notification CRUD section:

```python
# ===================================
# NOTIFICATION CRUD FUNCTIONS
# ===================================

def create_notification(db: Session, user_id: int, notif_type: str, title: str, message: Optional[str] = None, link: Optional[str] = None, metadata: Optional[dict] = None) -> models.Notification:
    notification = models.Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        message=message,
        link=link,
        metadata=metadata or {}
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

def get_notifications_for_user(db: Session, user_id: int, skip: int = 0, limit: int = 20) -> List[models.Notification]:
    return db.query(models.Notification).filter(
        models.Notification.user_id == user_id
    ).order_by(models.Notification.created_at.desc()).offset(skip).limit(limit).all()

def get_unread_notification_count(db: Session, user_id: int) -> int:
    return db.query(func.count(models.Notification.id)).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).scalar() or 0

def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Optional[models.Notification]:
    notification = db.query(models.Notification).filter(
        models.Notification.id == notification_id,
        models.Notification.user_id == user_id
    ).first()
    if notification:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return notification

def mark_all_notifications_read(db: Session, user_id: int):
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id,
        models.Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
```

- [ ] **Step 7.2** Commit: "Add notification CRUD functions"

---

## Task 8: Drama API Routes

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/app/routers/drama_routes.py`

- [ ] **Step 8.1** Create the drama routes file. Follow the exact pattern from `post_routes.py` and `message_routes.py` -- `APIRouter(tags=[...])`, `Depends(auth.get_required_user)` / `Depends(auth.get_current_user)`, `Depends(get_db)`. The full file includes drama CRUD, character endpoints, act endpoints, reply endpoints, like/comment, and PDF export. Key conventions:
  - Use `async def` for route handlers (existing pattern)
  - Return dict or raise HTTPException (existing pattern)
  - Romanian error messages in HTTPException detail (existing pattern, e.g. "Piesa nu a fost gasita")
  - Rate limiting on mutation endpoints via `@limiter.limit("20/minute")`
  - Authorization checks inline (not via decorator)

The file should contain these endpoint groups:
  - `POST /api/dramas/` - Create drama
  - `GET /api/dramas/{slug}` - Get drama detail
  - `PUT /api/dramas/{slug}` - Update drama
  - `DELETE /api/dramas/{slug}` - Delete drama
  - `POST /api/dramas/{slug}/complete` - Complete drama
  - `POST /api/dramas/{slug}/invite` - Send invitation
  - `POST /api/dramas/{slug}/apply` - Apply to join
  - `POST /api/dramas/{slug}/invitations/{id}/respond` - Respond to invitation
  - `DELETE /api/dramas/{slug}/characters/{id}` - Remove character
  - `POST /api/dramas/{slug}/acts` - Create act
  - `PUT /api/dramas/{slug}/acts/{act_number}` - Update act
  - `POST /api/dramas/{slug}/acts/{act_number}/complete` - Complete act
  - `POST /api/dramas/{slug}/acts/{act_number}/replies` - Add reply
  - `PUT /api/dramas/{slug}/replies/{id}` - Edit reply
  - `DELETE /api/dramas/{slug}/replies/{id}` - Delete reply
  - `PUT /api/dramas/{slug}/replies/reorder` - Reorder replies
  - `POST /api/dramas/{slug}/likes` - Like drama
  - `POST /api/dramas/{slug}/comments` - Comment on drama
  - `GET /api/dramas/{slug}/export/pdf` - PDF export

Every mutation endpoint should create appropriate notifications via `crud.create_notification()`. For example, when a reply is added, all other participants get notified. When an invitation is sent, the recipient gets notified.

- [ ] **Step 8.2** Commit: "Add drama API routes"

---

## Task 9: Notification API Routes

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/app/routers/notification_routes.py`

- [ ] **Step 9.1** Create the notification routes file following the existing router pattern:

```python
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, crud, auth
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


@router.get("/api/notifications")
async def get_notifications(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    notifications = crud.get_notifications_for_user(db, current_user.id, skip, limit)
    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "is_read": n.is_read,
                "metadata": n.metadata,
                "created_at": n.created_at.isoformat()
            }
            for n in notifications
        ]
    }


@router.get("/api/notifications/unread-count")
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    count = crud.get_unread_notification_count(db, current_user.id)
    return {"unread_count": count}


@router.put("/api/notifications/{notification_id}/read")
async def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    notification = crud.mark_notification_read(db, notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notificarea nu a fost gasita")
    return {"message": "Notificare marcata ca citita"}


@router.put("/api/notifications/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    crud.mark_all_notifications_read(db, current_user.id)
    return {"message": "Toate notificarile au fost marcate ca citite"}
```

- [ ] **Step 9.2** Commit: "Add notification API routes"

---

## Task 10: Page Routes

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/app/routers/pages.py`

- [ ] **Step 10.1** Add drama page routes to `pages.py`. These MUST be placed BEFORE the catch-all route `@router.get("/{path:path}")` (currently at line 267). Add them after the moderation panel route and before the catch-all section comment. The four new page routes:

```python
# ===================================
# DRAMA PAGE ROUTES (before catch-all)
# ===================================

@router.get("/piese", response_class=HTMLResponse)
async def drama_list_page(request: Request, status_filter: Optional[str] = None, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    """Drama listing page - on subdomain shows user's dramas, on main domain shows discovery"""
    if request.state.is_subdomain:
        username = request.state.username
        user = crud.get_user_by_username(db, username=username)
        if not user:
            raise HTTPException(status_code=404, detail="Blogul nu a fost gasit")
        dramas = crud.get_dramas_by_user(db, user.id)
        participating = []
        if current_user:
            participating = crud.get_user_dramas_as_participant(db, current_user.id)
        context = get_common_context(request, current_user)
        context.update({
            "blog_owner": user,
            "dramas": dramas,
            "participating_dramas": participating,
            "is_discovery": False
        })
    else:
        dramas = crud.get_all_dramas(db, status_filter=status_filter)
        context = get_common_context(request, current_user)
        context.update({
            "dramas": dramas,
            "status_filter": status_filter,
            "is_discovery": True
        })
    return templates.TemplateResponse(request, "drama/list.html", context)


@router.get("/piese/creeaza", response_class=HTMLResponse)
async def drama_create_page(request: Request, current_user: models.User = Depends(auth.get_required_user)):
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/piese/creeaza", status_code=status.HTTP_302_FOUND)
    context = get_common_context(request, current_user)
    return templates.TemplateResponse(request, "drama/create.html", context)


@router.get("/piese/{slug}/gestioneaza", response_class=HTMLResponse)
async def drama_manage_page(request: Request, slug: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/piese/{slug}/gestioneaza", status_code=status.HTTP_302_FOUND)
    drama = crud.get_drama_by_slug(db, slug)
    if not drama or drama.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Piesa nu a fost gasita sau nu va apartine")
    pending_invitations = crud.get_pending_invitations_for_drama(db, drama.id)
    context = get_common_context(request, current_user)
    context.update({
        "drama": drama,
        "pending_invitations": pending_invitations
    })
    return templates.TemplateResponse(request, "drama/manage.html", context)


@router.get("/piese/{slug}", response_class=HTMLResponse)
async def drama_detail_page(request: Request, slug: str, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(auth.get_current_user)):
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa nu a fost gasita")
    crud.increment_drama_view(db, drama.id)
    user_character = None
    if current_user:
        user_character = crud.get_character_for_user_in_drama(db, drama.id, current_user.id)
    context = get_common_context(request, current_user)
    context.update({
        "drama": drama,
        "blog_owner": drama.owner,
        "user_character": user_character
    })
    return templates.TemplateResponse(request, "drama/detail.html", context)


@router.get("/notificari", response_class=HTMLResponse)
async def notifications_page(request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_required_user)):
    if request.url.hostname == MAIN_DOMAIN:
        return RedirectResponse(url=f"//{current_user.username}{SUBDOMAIN_SUFFIX}/notificari", status_code=status.HTTP_302_FOUND)
    context = get_common_context(request, current_user)
    return templates.TemplateResponse(request, "notifications.html", context)
```

- [ ] **Step 10.2** Commit: "Add drama and notification page routes"

---

## Task 11: Router Registration

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/app/main.py`

- [ ] **Step 11.1** Add the new router imports. Change line 17 from:

```python
from .routers import auth_routes, user_routes, post_routes, message_routes, moderation_routes, api_pages
```

to:

```python
from .routers import auth_routes, user_routes, post_routes, message_routes, moderation_routes, api_pages, drama_routes, notification_routes
```

- [ ] **Step 11.2** Add the router registrations. After `app.include_router(api_pages.router)` (line 94), add:

```python
app.include_router(drama_routes.router)
app.include_router(notification_routes.router)
```

- [ ] **Step 11.3** Commit: "Wire drama and notification routers into main app"

---

## Task 12: Templates - Create & List

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/templates/drama/create.html`
- Create: `/home/danmgocan/Projects/calimara2/templates/drama/list.html`

- [ ] **Step 12.1** Create the `templates/drama/` directory.

- [ ] **Step 12.2** Create `create.html` following the `create_post.html` pattern -- extends `base.html`, uses `{% block content %}`, form with text inputs (no Quill editor -- drama creation is just title + description + character name/description). Form submission via JS fetch to `POST /api/dramas/`. On success, redirect to `/piese/{slug}/gestioneaza`.

- [ ] **Step 12.3** Create `list.html` following the `blog.html` card-based layout pattern. Show drama cards in a grid (Bootstrap `row g-4 col-md-6 col-lg-4`). Each card shows: title, creator username, status badge (`in_progress` = green, `completed` = gold), character count, likes count, view count. On subdomain, show the blog owner's dramas. On main domain (`is_discovery`), show all dramas with filter buttons for status. Include a "Creeaza piesa" button for authenticated users on subdomain view.

- [ ] **Step 12.4** Commit: "Add drama create and list templates"

---

## Task 13: Templates - Detail (Reading View)

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/templates/drama/detail.html`

- [ ] **Step 13.1** Create `detail.html` extending `base.html`. This is the main drama reading page with screenplay formatting. Structure:
  - **Header section**: drama title, creator avatar + username link, description, status badge, character list cards
  - **Acts section**: each act as an expandable section (`<details>` or Bootstrap accordion). Title + setting at top, replies in screenplay format below
  - **Screenplay dialogue formatting**: character name in bold uppercase, stage direction in italics parentheses, dialogue content below. Use the `.screenplay-*` CSS classes defined in Task 18
  - **Reply form** at bottom of active act (only visible if `user_character` is set and act status is "active"). Simple form with optional stage direction input and content textarea
  - **Apply button**: if drama is open for applications and user is logged in but not a participant, show "Aplica" button that opens a modal with character name/description/message fields
  - **Like/Comment section** at bottom, following the pattern from `post_detail.html`
  - **Curtain animation**: if drama status is "completed", show the `.drama-curtain` div (styled in Task 18)

- [ ] **Step 13.2** Commit: "Add drama detail template with screenplay formatting"

---

## Task 14: Templates - Manage (Owner Dashboard)

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/templates/drama/manage.html`

- [ ] **Step 14.1** Create `manage.html` extending `base.html`. This is the owner dashboard for managing a drama. Sections:
  - **Drama info** with edit form (title, description, open for applications toggle)
  - **Characters list** with remove buttons (cannot remove creator)
  - **Pending invitations/applications** list with accept/reject buttons
  - **Invite user** form (username input, optional character name, optional message)
  - **Act management**: create new act form (title, setting), list of acts with status badges, "End Act" button for active act
  - **Reply management**: list replies in current active act with delete buttons. Drag-and-drop reorder (handled by JS in Task 16)
  - **Complete drama** button with confirmation modal
  - **Export PDF** button
  - **Status indicators**: overall drama status, character count, reply count, view count

- [ ] **Step 14.2** Commit: "Add drama manage template (owner dashboard)"

---

## Task 15: Templates - Notifications

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/templates/includes/notification_dropdown.html`
- Create: `/home/danmgocan/Projects/calimara2/templates/notifications.html`
- Modify: `/home/danmgocan/Projects/calimara2/templates/base.html`

- [ ] **Step 15.1** Create `notification_dropdown.html` as an include partial for the navbar. It contains:
  - A bell icon (`bi-bell`) with a badge count (hidden when 0)
  - A Bootstrap dropdown menu that loads notifications via JS
  - A "See all" link to `/notificari`
  - A "Mark all read" button

- [ ] **Step 15.2** Create `notifications.html` extending `base.html`. Full-page notification list loaded via fetch to `/api/notifications`, showing notification type icon, title, message, timestamp, read/unread state. Click marks as read and navigates to link.

- [ ] **Step 15.3** Modify `base.html` to include the notification dropdown in the navbar. Add it inside the `{% if current_user %}` block, between the moderation link and the messages link (around line 69). Add:

```html
<!-- Notification bell -->
{% include 'includes/notification_dropdown.html' %}
```

- [ ] **Step 15.4** Also add a "Piese" nav link in `base.html`. Add it in the navbar after the messages link. For subdomain, link to `/piese`. For main domain, link to `//calimara.ro/piese`:

```html
<li class="nav-item">
    {% if current_domain == 'calimara.ro' %}
        <a class="nav-link text-white hover-accent" href="/piese">
            <i class="bi bi-mask me-1"></i>Piese
        </a>
    {% else %}
        <a class="nav-link text-white hover-accent" href="/piese">
            <i class="bi bi-mask me-1"></i>Piese
        </a>
    {% endif %}
</li>
```

- [ ] **Step 15.5** Commit: "Add notification dropdown, notifications page, update base.html navbar"

---

## Task 16: Templates - Integration

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/templates/blog.html`
- Modify: `/home/danmgocan/Projects/calimara2/templates/index.html`

- [ ] **Step 16.1** Add a drama section to `blog.html`. Insert it between the three-column layout and the posts table (around line 252). This section shows the blog owner's dramas in a compact list format, similar to the featured posts card. Include a link to `/piese` for full listing. The context data is already loaded from the page routes (need to update the `read_root` and `catch_all` page routes to also load dramas for the blog owner).

- [ ] **Step 16.2** Update the `read_root` function in `pages.py` to load drama data for the blog owner when rendering `blog.html`. Add to the subdomain branch (around line 56):

```python
user_dramas = crud.get_dramas_by_user(db, user.id, limit=5)
```

And add `"user_dramas": user_dramas` to the context update. Do the same in the `catch_all` function's subdomain branch.

- [ ] **Step 16.3** Add a featured dramas section to `index.html`. Insert it between the random content section and the social media section (around line 200). Show recent dramas in a compact horizontal card format with title, creator, status badge, and character count. Load this data in the `read_root` function's main domain branch:

```python
recent_dramas = crud.get_all_dramas(db, limit=6)
```

Add `"recent_dramas": recent_dramas` to the context.

- [ ] **Step 16.4** Commit: "Add drama sections to blog and index pages"

---

## Task 17: JavaScript - Drama

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/static/js/drama.js`

- [ ] **Step 17.1** Create `drama.js` following the patterns in `script.js` and `create-post.js`. Use `document.addEventListener('DOMContentLoaded', ...)`, Fetch API with JSON, and `showToast()` for feedback. Functions:

  - **Drama creation form handler**: POST to `/api/dramas/`, redirect on success
  - **Reply submission**: POST to `/api/dramas/{slug}/acts/{act_number}/replies`, append reply to DOM on success (or page reload since server-side preference)
  - **Invitation form handler**: POST to `/api/dramas/{slug}/invite`
  - **Application form handler**: POST to `/api/dramas/{slug}/apply`
  - **Invitation response**: POST to `/api/dramas/{slug}/invitations/{id}/respond`
  - **Act management**: POST to create act, POST to complete act
  - **Reply delete**: DELETE with confirmation
  - **Reply reorder**: Drag-and-drop using HTML5 Drag API (minimal JS per CLAUDE.md). On drop, PUT to `/api/dramas/{slug}/replies/reorder`
  - **Drama completion**: POST with confirmation modal
  - **Like handler**: POST to `/api/dramas/{slug}/likes`
  - **Comment handler**: POST to `/api/dramas/{slug}/comments`
  - **Drama edit form**: PUT to `/api/dramas/{slug}`

All handlers follow existing fetch pattern from `script.js`: try/catch, response.ok check, showToast on success/error.

- [ ] **Step 17.2** Commit: "Add drama JavaScript interactions"

---

## Task 18: JavaScript - Notifications

**Files:**
- Create: `/home/danmgocan/Projects/calimara2/static/js/notifications.js`

- [ ] **Step 18.1** Create `notifications.js` following existing patterns. Functions:

  - **fetchUnreadCount()**: GET `/api/notifications/unread-count`, update badge in navbar
  - **loadNotifications()**: GET `/api/notifications`, populate dropdown
  - **markAsRead(id)**: PUT `/api/notifications/{id}/read`
  - **markAllRead()**: PUT `/api/notifications/read-all`
  - **Polling**: setInterval to call `fetchUnreadCount()` every 30 seconds (track interval in `_activeIntervals` array like script.js does)
  - **Dropdown toggle handler**: on dropdown open, load notifications

This script should be included in `base.html` (in the `extra_scripts` block or directly before `</body>`), so it runs on every page for logged-in users.

- [ ] **Step 18.2** Add the notification JS include to `base.html`. After the custom JS script tag (line 168), add:

```html
{% if current_user %}
<script src="/static/js/notifications.js" defer></script>
{% endif %}
```

- [ ] **Step 18.3** Commit: "Add notification JavaScript with polling"

---

## Task 19: CSS Styling

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/static/css/style.css`

- [ ] **Step 19.1** Add a drama-specific section at the end of `style.css` (after the existing `.alert-sm` section). Include:

**Screenplay formatting:**
```css
/* ===================================
   DRAMA & SCREENPLAY STYLES
   ================================== */

.screenplay-character-name {
    font-family: var(--font-family-base);
    font-weight: var(--font-weight-bold);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.25rem;
}

.screenplay-stage-direction {
    font-family: var(--font-family-serif);
    font-style: italic;
    color: var(--color-muted);
    margin-bottom: 0.25rem;
}

.screenplay-dialogue {
    font-family: var(--font-family-serif);
    font-size: 1.05rem;
    line-height: 1.8;
    margin-bottom: 1.5rem;
    padding-left: 2rem;
}

.screenplay-reply {
    margin-bottom: 1.5rem;
    padding: 1rem;
    border-left: 3px solid transparent;
    transition: border-color var(--transition-normal);
}

.screenplay-reply:hover {
    border-left-color: var(--color-accent);
    background: rgba(0, 0, 0, 0.02);
}

.drama-act-section {
    margin-bottom: 2rem;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: var(--border-radius-lg);
    overflow: hidden;
}

.drama-act-header {
    background: var(--gradient-primary);
    color: white;
    padding: 1rem 1.5rem;
    cursor: pointer;
}

.drama-act-setting {
    font-family: var(--font-family-serif);
    font-style: italic;
    padding: 1rem 1.5rem;
    background: #f8f9fa;
    border-bottom: 1px solid rgba(0, 0, 0, 0.1);
}
```

**Character cards:**
```css
.drama-character-card {
    padding: 1rem;
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: var(--border-radius);
    transition: transform var(--transition-normal), box-shadow var(--transition-normal);
}

.drama-character-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow);
}

.drama-character-card.is-creator {
    border-color: var(--color-accent);
    border-width: 2px;
}
```

**Drama cards (list view):**
```css
.drama-card {
    border: 1px solid rgba(0, 0, 0, 0.1);
    border-radius: var(--border-radius-lg);
    padding: 1.5rem;
    transition: transform var(--transition-normal), box-shadow var(--transition-normal);
    background: var(--color-container-bg);
}

.drama-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
}

.drama-status-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 1rem;
    font-size: 0.8rem;
    font-weight: var(--font-weight-semibold);
}

.drama-status-badge.in-progress {
    background: #d4edda;
    color: #155724;
}

.drama-status-badge.completed {
    background: #fff3cd;
    color: #856404;
}
```

**Curtain animation:**
```css
.drama-curtain-container {
    position: relative;
    overflow: hidden;
    min-height: 300px;
}

.drama-curtain {
    position: absolute;
    top: 0;
    width: 50%;
    height: 100%;
    background: linear-gradient(180deg, #8B0000 0%, #DC143C 50%, #8B0000 100%);
    z-index: 10;
    transition: transform 2s ease-in-out;
}

.drama-curtain.left {
    left: 0;
    transform-origin: left;
    border-right: 3px solid #FFD700;
}

.drama-curtain.right {
    right: 0;
    transform-origin: right;
    border-left: 3px solid #FFD700;
}

.drama-curtain-container.open .drama-curtain.left {
    transform: translateX(-100%);
}

.drama-curtain-container.open .drama-curtain.right {
    transform: translateX(100%);
}

.drama-curtain-content {
    position: relative;
    z-index: 5;
    text-align: center;
    padding: 3rem;
}
```

**Notification styles:**
```css
/* ===================================
   NOTIFICATION STYLES
   ================================== */

.notification-dropdown {
    width: 350px;
    max-height: 400px;
    overflow-y: auto;
}

.notification-item {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    transition: background var(--transition-fast);
    cursor: pointer;
}

.notification-item:hover {
    background: rgba(0, 0, 0, 0.03);
}

.notification-item.unread {
    background: rgba(27, 94, 32, 0.05);
    border-left: 3px solid var(--color-accent);
}

.notification-badge {
    font-size: 0.65rem;
    min-width: 1.2rem;
    height: 1.2rem;
    display: flex;
    align-items: center;
    justify-content: center;
}
```

**Drag-and-drop reorder:**
```css
.reply-draggable {
    cursor: grab;
}

.reply-draggable:active {
    cursor: grabbing;
}

.reply-draggable.dragging {
    opacity: 0.5;
    background: #e3f2fd;
}

.reply-drop-zone {
    border: 2px dashed transparent;
    transition: border-color var(--transition-fast);
}

.reply-drop-zone.drag-over {
    border-color: var(--color-accent);
    background: rgba(27, 94, 32, 0.05);
}
```

- [ ] **Step 19.2** Commit: "Add drama, screenplay, curtain animation, and notification CSS styles"

---

## Task 20: PDF Export

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/requirements.txt`
- Create: `/home/danmgocan/Projects/calimara2/templates/drama/pdf_template.html`
- The export route is already in `drama_routes.py` (Task 8)

- [ ] **Step 20.1** Add WeasyPrint to `requirements.txt`:

```
weasyprint>=62.0
```

- [ ] **Step 20.2** Create `pdf_template.html` -- a standalone HTML template (NOT extending base.html) designed specifically for WeasyPrint rendering. This template uses inline CSS (exception to the CLAUDE.md rule since this is for PDF generation, not browser rendering) and includes:
  - **Cover page**: Calimara.ro logo text, drama title, "de [creator username]", description
  - **Character page**: list of all characters with descriptions
  - **Act pages**: each act with title, setting, and all replies in professional screenplay format
  - **Page numbers** via CSS `@page` rules
  - **Professional screenplay typography**: Courier/monospace font, proper margins

- [ ] **Step 20.3** The PDF export endpoint in `drama_routes.py` should render the template via Jinja2, convert to PDF with WeasyPrint, and return as a `StreamingResponse` with `Content-Disposition: attachment; filename={slug}.pdf`.

- [ ] **Step 20.4** Commit: "Add WeasyPrint PDF export with professional screenplay template"

---

## Task 21: Sample Data

**Files:**
- Modify: `/home/danmgocan/Projects/calimara2/schema.sql`

- [ ] **Step 21.1** Add sample drama data at the end of `schema.sql` (after the existing sample messages). This provides test data for development:

```sql
-- ===================================
-- SAMPLE DRAMA DATA
-- ===================================

-- Drama created by dangocan (user_id = 1)
INSERT INTO dramas (user_id, title, slug, description, status, is_open_for_applications) VALUES
(1, 'Ultima Noapte de Dragoste', 'ultima-noapte-de-dragoste', 'O piesa despre iubire, tradare si regasire intr-un Bucuresti interbelic. Doua personaje se intalnesc intr-o cafenea si isi spun povestile.', 'in_progress', TRUE);

-- Characters for the drama
INSERT INTO drama_characters (drama_id, user_id, character_name, character_description, is_creator) VALUES
(1, 1, 'Stefan', 'Un tanar scriitor idealist care crede in puterea cuvintelor', TRUE),
(1, 2, 'Elena', 'O poetesa misterioasa cu un trecut plin de secrete', FALSE);

-- Act 1
INSERT INTO drama_acts (drama_id, act_number, title, setting, status) VALUES
(1, 1, 'Intalnirea', 'O cafenea din centrul Bucurestiului, seara. Lumina slaba, muzica de jazz in fundal.', 'active');

-- Sample replies
INSERT INTO drama_replies (act_id, character_id, content, stage_direction, position) VALUES
(1, 1, 'Buna seara. Scuzati-ma, este liber locul acesta?', '(apropiindu-se de masa cu un zambet timid)', 1),
(1, 2, 'Liber ca versul alb. Va rog, luati loc.', '(ridicand privirea din carte)', 2),
(1, 1, 'Multumesc. Observ ca cititi poezie. Bacovia?', '(asezandu-se si privind coperta cartii)', 3),
(1, 2, 'Eminescu, de fapt. Dar apreciez ca ati recunoscut poezia de la distanta.', '(zambind enigmatic)', 4);

-- A completed drama
INSERT INTO dramas (user_id, title, slug, description, status, is_open_for_applications, view_count) VALUES
(3, 'Dialog la Marginea Lumii', 'dialog-la-marginea-lumii', 'Doi calatori se intalnesc la capatul pamantului si descopera ca au aceeasi destinatie.', 'completed', FALSE, 42);

INSERT INTO drama_characters (drama_id, user_id, character_name, character_description, is_creator) VALUES
(2, 3, 'Calator', 'Un filozof ratacitor in cautarea adevarului', TRUE),
(2, 4, 'Straina', 'O femeie care a vazut totul si nu se mai mira de nimic', FALSE);

INSERT INTO drama_acts (drama_id, act_number, title, setting, status) VALUES
(2, 1, 'La Capatul Drumului', 'O stanca deasupra oceanului. Vant puternic. Apus de soare.', 'completed');

INSERT INTO drama_replies (act_id, character_id, content, stage_direction, position) VALUES
(2, 3, 'Am ajuns. In sfarsit, am ajuns la marginea lumii.', '(privind in zare)', 1),
(2, 4, 'Nu exista margine. Doar un alt inceput.', '(aparand din ceata)', 2),
(2, 3, 'Cine esti?', '(intorcandu-se surprins)', 3),
(2, 4, 'Sunt cea care a fost mereu aici. Intrebarea este: de ce ai venit?', NULL, 4);

-- Sample drama likes
INSERT INTO drama_likes (drama_id, user_id) VALUES
(1, 2), (1, 3), (1, 4),
(2, 1), (2, 2);

-- Sample drama comments
INSERT INTO drama_comments (drama_id, user_id, content) VALUES
(1, 3, 'Ce dialog frumos! Abia astept sa vad cum continua povestea.'),
(1, 4, 'Atmosfera cafenelei este captivanta. Felicitari autorilor!'),
(2, 1, 'O piesa filosofica profunda. Finalul m-a emotionat.');
```

- [ ] **Step 21.2** Update the verification tables list in `initdb.py` if not already done in Task 2. Also ensure the drama tables appear in the verification output.

- [ ] **Step 21.3** Commit: "Add sample drama data to schema.sql"

---

## Dependency Graph / Execution Order

Tasks can be partially parallelized:

1. **Task 1 (Schema)** and **Task 3 (Models)** and **Task 4 (Schemas)** can be done in parallel (no runtime dependency, only conceptual)
2. **Task 2 (initdb)** depends on Task 1
3. **Task 5, 6, 7 (CRUD)** depend on Task 3 (Models) and Task 4 (Schemas)
4. **Task 8, 9 (API Routes)** depend on Tasks 5-7 (CRUD)
5. **Task 10 (Page Routes)** depends on Tasks 5-7 (CRUD)
6. **Task 11 (Router Registration)** depends on Tasks 8-10
7. **Tasks 12-16 (Templates)** depend on Task 10 (Page Routes) for context variables
8. **Tasks 17-18 (JavaScript)** depend on Tasks 8-9 (API Routes) for endpoint paths
9. **Task 19 (CSS)** can be done at any time
10. **Task 20 (PDF)** depends on Task 8 (drama routes)
11. **Task 21 (Sample Data)** depends on Task 1 (Schema)

Recommended sequential execution: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 10 -> 11 -> 12 -> 13 -> 14 -> 15 -> 16 -> 17 -> 18 -> 19 -> 20 -> 21

---

## Verification Checklist

After all tasks complete, run `python scripts/initdb.py` and verify:
1. All new tables created without errors
2. Sample drama data populated
3. Navigate to `localhost/piese` (main domain) to see drama discovery
4. Navigate to `{username}.localhost/piese` to see user's dramas
5. Create a drama via the form
6. Send an invitation, accept it
7. Create an act, add replies
8. Verify notification bell updates
9. Complete a drama, verify curtain animation
10. Export a drama to PDF

### Critical Files for Implementation

- `/home/danmgocan/Projects/calimara2/schema.sql`
- `/home/danmgocan/Projects/calimara2/app/models.py`
- `/home/danmgocan/Projects/calimara2/app/crud.py`
- `/home/danmgocan/Projects/calimara2/app/routers/drama_routes.py`
- `/home/danmgocan/Projects/calimara2/app/routers/pages.py`