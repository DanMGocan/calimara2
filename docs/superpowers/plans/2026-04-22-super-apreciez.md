# Super-Apreciez Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Super-apreciez feature end-to-end: a weekly-quota super-like reaction with visual golden-border treatment on recipient posts, gated by a Stripe-powered €3.99/mo Premium tier.

**Architecture:** Server derives weekly quota from row counts (no stored wallet), stores Stripe customer/subscription IDs + `premium_until` on the `User`, and reconciles state via signed Stripe webhooks with event-ID idempotency. Frontend gets a `<SuperLikeButton>` sibling to the existing like button with optimistic updates, plus a `/premium` page that redirects to Stripe Checkout/Portal.

**Tech Stack:** FastAPI, SQLAlchemy (Mapped annotations), PostgreSQL (prod) / SQLite (tests), Pydantic v2, React + TanStack Query, Stripe Python SDK ≥10.

---

## File Structure

**Backend — created:**
- `app/routers/super_like_routes.py` — super-apreciez endpoints
- `app/routers/premium_routes.py` — Stripe checkout / portal / webhook endpoints
- `app/stripe_service.py` — Stripe SDK wrapper, env loading, `_client` singleton
- `app/week_util.py` — `start_of_iso_week_utc()` and `end_of_iso_week_utc()` helpers
- `tests/test_super_apreciez.py` — unit tests for super-like rules + quota
- `tests/test_premium_webhook.py` — webhook signature + idempotency tests

**Backend — modified:**
- `schema.sql` — add `super_likes`, `stripe_events` tables; add Stripe columns to `users`
- `app/models.py` — `SuperLike` model, Post/User additions
- `app/schemas.py` — `SuperLike`, `SuperLikeQuota`, `PremiumCheckoutResponse`, add `super_likes_count`/`viewer_super_liked` to `Post`
- `app/crud.py` — `create_super_like`, `delete_super_like`, `get_user_weekly_super_like_count`, `get_super_likes_count_for_post`, `user_super_liked_post`, `upsert_stripe_customer_id`, `get_user_by_stripe_customer_id`, `set_premium_from_subscription`
- `app/routers/post_routes.py` — enrich post responses with new fields
- `app/routers/api_pages.py` — same enrichment for list endpoints
- `app/routers/user_routes.py` — include `is_premium`, `premium_until` in `/api/users/me`
- `app/main.py` — register two new routers
- `requirements.txt` — `stripe>=10.0.0`
- `.env` — add Stripe variables (user-owned — we only document what to add)

**Frontend — created:**
- `frontend/src/api/superLikes.ts`
- `frontend/src/api/premium.ts`
- `frontend/src/components/ui/super-like-button.tsx`
- `frontend/src/pages/PremiumPage.tsx`
- `frontend/src/pages/PremiumSuccessPage.tsx`
- `frontend/src/pages/PremiumCancelPage.tsx`

**Frontend — modified:**
- `frontend/src/api/posts.ts` — response types add `super_likes_count`, `viewer_super_liked`
- `frontend/src/pages/PostDetailPage.tsx` — render button + border
- `frontend/src/pages/LandingPage.tsx`, `BlogHomePage.tsx`, `CategoryPage.tsx`, `CollectionDetailPage.tsx` — card border
- `frontend/src/components/layout/SideMenu.tsx` — "Premium" link
- `frontend/src/pages/DashboardPage.tsx` — banner for non-premium
- `frontend/src/index.css` — `.has-super-like` styling
- `frontend/src/App.tsx` — `/premium`, `/premium/success`, `/premium/cancel` routes

---

## Testing Note

The existing test suite (`tests/test_backend_stabilization.py`) uses **unittest + in-memory SQLite + SQLAlchemy `create_all`**. Our new tests follow that exact pattern. Run with:

```bash
python -m unittest tests.test_super_apreciez tests.test_premium_webhook -v
```

For the frontend, the project currently has no React test harness; we verify via `npm run build` + manual browser smoke test.

---

## Task 1: Database schema — `super_likes`, `stripe_events`, User Stripe columns

**Files:**
- Modify: `schema.sql` (add DROPs, CREATEs, indexes in dependency order)

- [ ] **Step 1: Add DROPs for the two new tables**

Edit `schema.sql`. At the top, after `DROP TABLE IF EXISTS notifications CASCADE;`, add:

```sql
DROP TABLE IF EXISTS super_likes CASCADE;
DROP TABLE IF EXISTS stripe_events CASCADE;
```

- [ ] **Step 2: Add Stripe columns to `users` table**

In the `CREATE TABLE users` block, add these columns before `created_at`:

```sql
    stripe_customer_id VARCHAR(100) UNIQUE,
    stripe_subscription_id VARCHAR(100) UNIQUE,
    premium_until TIMESTAMP,
```

And add these indexes after the existing user indexes:

```sql
CREATE INDEX idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX idx_users_premium_until ON users(premium_until);
```

- [ ] **Step 3: Add `super_likes` CREATE at the end of the file**

Append after the last `CREATE TABLE` block:

```sql
-- ===================================
-- SUPER LIKES TABLE
-- ===================================
CREATE TABLE super_likes (
    id SERIAL PRIMARY KEY,
    post_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_super_likes_post FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    CONSTRAINT fk_super_likes_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_super_likes_user_post UNIQUE (user_id, post_id)
);

CREATE INDEX idx_super_likes_user_created_at ON super_likes(user_id, created_at);
CREATE INDEX idx_super_likes_post ON super_likes(post_id);
```

- [ ] **Step 4: Add `stripe_events` CREATE**

Append:

```sql
-- ===================================
-- STRIPE EVENTS TABLE (webhook idempotency)
-- ===================================
CREATE TABLE stripe_events (
    id VARCHAR(100) PRIMARY KEY,
    type VARCHAR(100) NOT NULL,
    received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

- [ ] **Step 5: Verify schema applies**

Run: `python scripts/initdb.py`
Expected: Completes without errors. A quick `\d super_likes` and `\d users` in psql should show the new tables/columns.

- [ ] **Step 6: Commit**

```bash
git add schema.sql
git commit -m "db: add super_likes, stripe_events tables and User Stripe columns"
```

---

## Task 2: SQLAlchemy models — `SuperLike`, `StripeEvent`, Post + User additions

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: Add `SuperLike` model**

Add after the `Like` class (around line 192 of `app/models.py`):

```python
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
```

Add `UniqueConstraint` to the existing `from sqlalchemy import ...` line at the top.

- [ ] **Step 2: Add `StripeEvent` model**

After the `SuperLike` class:

```python
class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

- [ ] **Step 3: Add Stripe columns + `is_premium` property on `User`**

In `class User`, after the existing social/donation URL columns and before `is_suspended`:

```python
    # Stripe / Premium subscription
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    premium_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
```

Add new relationship in `class User`, near the `likes` relationship:

```python
    super_likes_given: Mapped[List["SuperLike"]] = relationship("SuperLike", back_populates="user", cascade="all, delete-orphan")
```

Add `is_premium` property at the end of `class User` (before `class Post`):

```python
    @property
    def is_premium(self) -> bool:
        if self.premium_until is None:
            return False
        return self.premium_until > datetime.utcnow()
```

- [ ] **Step 4: Add `super_likes` relationship + `super_likes_count` hybrid property on `Post`**

In `class Post`, add near the existing `likes` relationship:

```python
    super_likes: Mapped[List["SuperLike"]] = relationship("SuperLike", back_populates="post", cascade="all, delete-orphan")
```

After the existing `likes_count` hybrid property, add:

```python
    @hybrid_property
    def super_likes_count(self) -> int:
        return len(self.super_likes)

    @super_likes_count.expression
    def super_likes_count(cls):
        return (
            select(func.count(SuperLike.id))
            .where(SuperLike.post_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )
```

- [ ] **Step 5: Write smoke test for model definitions**

Create `tests/test_super_apreciez.py`:

```python
import os
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import models


class SuperLikeModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _make_user(self, username):
        u = models.User(
            username=username,
            email=f"{username}@x.test",
            google_id=f"g-{username}",
        )
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _make_post(self, user, title):
        p = models.Post(
            user_id=user.id,
            title=title,
            slug=f"{user.username}-{title}".lower(),
            content="c",
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def test_super_like_can_be_created(self):
        alice = self._make_user("alice")
        bob = self._make_user("bob")
        post = self._make_post(alice, "p1")

        sl = models.SuperLike(post_id=post.id, user_id=bob.id)
        self.db.add(sl)
        self.db.commit()

        self.assertEqual(self.db.query(models.SuperLike).count(), 1)
        self.assertEqual(post.super_likes_count, 1)

    def test_super_like_unique_constraint_blocks_duplicates(self):
        alice = self._make_user("alice")
        bob = self._make_user("bob")
        post = self._make_post(alice, "p1")

        self.db.add(models.SuperLike(post_id=post.id, user_id=bob.id))
        self.db.commit()

        self.db.add(models.SuperLike(post_id=post.id, user_id=bob.id))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_is_premium_property_reads_premium_until(self):
        alice = self._make_user("alice")
        self.assertFalse(alice.is_premium)

        alice.premium_until = datetime.utcnow() + timedelta(days=10)
        self.db.commit()
        self.db.refresh(alice)
        self.assertTrue(alice.is_premium)

        alice.premium_until = datetime.utcnow() - timedelta(minutes=1)
        self.db.commit()
        self.db.refresh(alice)
        self.assertFalse(alice.is_premium)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 6: Run the test, verify it passes**

Run: `python -m unittest tests.test_super_apreciez -v`
Expected: 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add app/models.py tests/test_super_apreciez.py
git commit -m "models: add SuperLike, StripeEvent, User Stripe fields, Post.super_likes_count"
```

---

## Task 3: Week boundary utility

**Files:**
- Create: `app/week_util.py`
- Modify: `tests/test_super_apreciez.py` (add tests)

- [ ] **Step 1: Write failing test**

Append to `tests/test_super_apreciez.py` above `if __name__`:

```python
from datetime import timezone
from unittest.mock import patch

from app.week_util import start_of_iso_week_utc, end_of_iso_week_utc


class WeekBoundaryTests(unittest.TestCase):
    def test_monday_midnight_utc_returns_same_instant(self):
        monday_0000 = datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc)
        with patch("app.week_util._now", return_value=monday_0000):
            self.assertEqual(start_of_iso_week_utc(), monday_0000)

    def test_sunday_returns_previous_monday(self):
        sunday_2359 = datetime(2026, 4, 26, 23, 59, 59, tzinfo=timezone.utc)
        with patch("app.week_util._now", return_value=sunday_2359):
            self.assertEqual(
                start_of_iso_week_utc(),
                datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc),
            )

    def test_end_of_week_is_next_monday_midnight(self):
        wednesday = datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc)
        with patch("app.week_util._now", return_value=wednesday):
            self.assertEqual(
                end_of_iso_week_utc(),
                datetime(2026, 4, 27, 0, 0, 0, tzinfo=timezone.utc),
            )
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_super_apreciez.WeekBoundaryTests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.week_util'`.

- [ ] **Step 3: Create `app/week_util.py`**

```python
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def start_of_iso_week_utc() -> datetime:
    now = _now()
    days_since_monday = now.weekday()  # Mon=0 ... Sun=6
    monday = (now - timedelta(days=days_since_monday)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return monday


def end_of_iso_week_utc() -> datetime:
    return start_of_iso_week_utc() + timedelta(days=7)
```

- [ ] **Step 4: Run tests**

Run: `python -m unittest tests.test_super_apreciez.WeekBoundaryTests -v`
Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/week_util.py tests/test_super_apreciez.py
git commit -m "util: add ISO-week boundary helpers in UTC"
```

---

## Task 4: CRUD functions for super-likes

**Files:**
- Modify: `app/crud.py`
- Modify: `tests/test_super_apreciez.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_super_apreciez.py`:

```python
from app import crud


class SuperLikeCrudTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        with self.engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        models.Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, name, premium=False):
        u = models.User(username=name, email=f"{name}@x.t", google_id=f"g-{name}")
        if premium:
            u.premium_until = datetime.utcnow() + timedelta(days=30)
        self.db.add(u)
        self.db.commit()
        self.db.refresh(u)
        return u

    def _post(self, user, title):
        p = models.Post(user_id=user.id, title=title, slug=f"{user.username}-{title}", content="c")
        self.db.add(p); self.db.commit(); self.db.refresh(p); return p

    def test_create_super_like_happy_path(self):
        alice = self._user("alice"); bob = self._user("bob")
        post = self._post(alice, "p1")
        sl = crud.create_super_like(self.db, user=bob, post_id=post.id)
        self.assertIsNotNone(sl.id)
        self.assertEqual(post.super_likes_count, 1)

    def test_create_super_like_rejects_self(self):
        alice = self._user("alice"); post = self._post(alice, "p1")
        with self.assertRaises(crud.SuperLikeSelfError):
            crud.create_super_like(self.db, user=alice, post_id=post.id)

    def test_create_super_like_rejects_duplicate(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        crud.create_super_like(self.db, user=bob, post_id=post.id)
        with self.assertRaises(crud.SuperLikeDuplicateError):
            crud.create_super_like(self.db, user=bob, post_id=post.id)

    def test_create_super_like_rejects_post_not_found(self):
        bob = self._user("bob")
        with self.assertRaises(crud.SuperLikePostNotFoundError):
            crud.create_super_like(self.db, user=bob, post_id=9999)

    def test_free_user_weekly_quota_one(self):
        alice = self._user("alice"); bob = self._user("bob")
        p1 = self._post(alice, "p1"); p2 = self._post(alice, "p2")
        crud.create_super_like(self.db, user=bob, post_id=p1.id)
        with self.assertRaises(crud.SuperLikeQuotaError):
            crud.create_super_like(self.db, user=bob, post_id=p2.id)

    def test_premium_user_weekly_quota_three(self):
        alice = self._user("alice"); bob = self._user("bob", premium=True)
        posts = [self._post(alice, f"p{i}") for i in range(4)]
        for p in posts[:3]:
            crud.create_super_like(self.db, user=bob, post_id=p.id)
        with self.assertRaises(crud.SuperLikeQuotaError):
            crud.create_super_like(self.db, user=bob, post_id=posts[3].id)

    def test_delete_super_like_removes_row(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        crud.create_super_like(self.db, user=bob, post_id=post.id)
        self.assertTrue(crud.delete_super_like(self.db, user=bob, post_id=post.id))
        self.assertEqual(self.db.query(models.SuperLike).count(), 0)

    def test_delete_super_like_returns_false_when_absent(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        self.assertFalse(crud.delete_super_like(self.db, user=bob, post_id=post.id))

    def test_get_user_weekly_count(self):
        alice = self._user("alice"); bob = self._user("bob")
        p1 = self._post(alice, "p1")
        crud.create_super_like(self.db, user=bob, post_id=p1.id)
        self.assertEqual(crud.get_user_weekly_super_like_count(self.db, bob.id), 1)

    def test_user_super_liked_post_check(self):
        alice = self._user("alice"); bob = self._user("bob"); post = self._post(alice, "p1")
        self.assertFalse(crud.user_super_liked_post(self.db, user_id=bob.id, post_id=post.id))
        crud.create_super_like(self.db, user=bob, post_id=post.id)
        self.assertTrue(crud.user_super_liked_post(self.db, user_id=bob.id, post_id=post.id))
```

- [ ] **Step 2: Run, verify they fail**

Run: `python -m unittest tests.test_super_apreciez.SuperLikeCrudTests -v`
Expected: All fail with AttributeError on `crud.create_super_like` etc.

- [ ] **Step 3: Implement CRUD functions**

Append to `app/crud.py`:

```python
# ===================================
# SUPER-APRECIEZ CRUD
# ===================================

from .week_util import start_of_iso_week_utc


FREE_WEEKLY_QUOTA = 1
PREMIUM_WEEKLY_QUOTA = 3


class SuperLikeError(Exception):
    """Base class for super-like errors."""


class SuperLikePostNotFoundError(SuperLikeError):
    pass


class SuperLikeSelfError(SuperLikeError):
    pass


class SuperLikeDuplicateError(SuperLikeError):
    pass


class SuperLikeQuotaError(SuperLikeError):
    pass


def weekly_quota_for_user(user: models.User) -> int:
    return PREMIUM_WEEKLY_QUOTA if user.is_premium else FREE_WEEKLY_QUOTA


def get_user_weekly_super_like_count(db: Session, user_id: int) -> int:
    return (
        db.query(models.SuperLike)
        .filter(
            models.SuperLike.user_id == user_id,
            models.SuperLike.created_at >= start_of_iso_week_utc().replace(tzinfo=None),
        )
        .count()
    )


def get_super_likes_count_for_post(db: Session, post_id: int) -> int:
    return db.query(models.SuperLike).filter(models.SuperLike.post_id == post_id).count()


def user_super_liked_post(db: Session, user_id: int, post_id: int) -> bool:
    return (
        db.query(models.SuperLike.id)
        .filter(models.SuperLike.user_id == user_id, models.SuperLike.post_id == post_id)
        .first()
        is not None
    )


def create_super_like(db: Session, user: models.User, post_id: int) -> models.SuperLike:
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if not post:
        raise SuperLikePostNotFoundError()
    if post.user_id == user.id:
        raise SuperLikeSelfError()
    if user_super_liked_post(db, user_id=user.id, post_id=post_id):
        raise SuperLikeDuplicateError()
    used = get_user_weekly_super_like_count(db, user.id)
    if used >= weekly_quota_for_user(user):
        raise SuperLikeQuotaError()
    sl = models.SuperLike(user_id=user.id, post_id=post_id)
    db.add(sl)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Race: another request inserted the same row between the check and the commit.
        raise SuperLikeDuplicateError()
    db.refresh(sl)
    return sl


def delete_super_like(db: Session, user: models.User, post_id: int) -> bool:
    sl = (
        db.query(models.SuperLike)
        .filter(models.SuperLike.user_id == user.id, models.SuperLike.post_id == post_id)
        .first()
    )
    if not sl:
        return False
    db.delete(sl)
    db.commit()
    return True
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `python -m unittest tests.test_super_apreciez -v`
Expected: all super-like tests pass.

- [ ] **Step 5: Commit**

```bash
git add app/crud.py tests/test_super_apreciez.py
git commit -m "crud: super-like create/delete with weekly quota + self/duplicate/not-found errors"
```

---

## Task 5: Pydantic schemas for super-likes and premium

**Files:**
- Modify: `app/schemas.py`

- [ ] **Step 1: Add super-like and premium schemas**

Append to `app/schemas.py`:

```python
# ===================================
# SUPER-APRECIEZ SCHEMAS
# ===================================

class SuperLike(BaseModel):
    id: int
    post_id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SuperLikeQuota(BaseModel):
    weekly_quota: int
    used_this_week: int
    remaining: int
    week_resets_at: datetime
    is_premium: bool


# ===================================
# PREMIUM / STRIPE SCHEMAS
# ===================================

class PremiumCheckoutResponse(BaseModel):
    url: str


class PremiumPortalResponse(BaseModel):
    url: str


class PremiumStatus(BaseModel):
    is_premium: bool
    premium_until: Optional[datetime] = None
    has_stripe_customer: bool
    has_active_subscription: bool
```

- [ ] **Step 2: Add new fields to the `Post` response schema**

Edit `class Post(PostBase)` (around line 81-95 of `app/schemas.py`). Add these two fields before `created_at`:

```python
    super_likes_count: int = 0
    viewer_super_liked: bool = False
```

- [ ] **Step 3: Verify imports are still valid**

Run: `python -c "from app import schemas; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add app/schemas.py
git commit -m "schemas: add SuperLike, SuperLikeQuota, PremiumCheckoutResponse and Post.super_likes_count"
```

---

## Task 6: Super-apreciez router

**Files:**
- Create: `app/routers/super_like_routes.py`
- Modify: `app/main.py`

- [ ] **Step 1: Create the router file**

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import auth, crud, models, schemas
from ..database import get_db
from ..week_util import end_of_iso_week_utc

router = APIRouter()


def _require_user(current_user):
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Trebuie să fii autentificat pentru a super-aprecia.",
        )
    return current_user


@router.post(
    "/api/posts/{post_id}/super-likes",
    response_model=schemas.SuperLike,
    status_code=status.HTTP_201_CREATED,
)
def add_super_like(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    try:
        return crud.create_super_like(db, user=user, post_id=post_id)
    except crud.SuperLikePostNotFoundError:
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită.")
    except crud.SuperLikeSelfError:
        raise HTTPException(
            status_code=403,
            detail="Nu îți poți super-aprecia propria postare.",
        )
    except crud.SuperLikeDuplicateError:
        raise HTTPException(
            status_code=409,
            detail="Ai super-apreciat deja această postare.",
        )
    except crud.SuperLikeQuotaError:
        raise HTTPException(
            status_code=403,
            detail="Ai epuizat super-aprecierile pentru această săptămână.",
            headers={"X-Error-Code": "quota_exhausted"},
        )


@router.delete(
    "/api/posts/{post_id}/super-likes",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_super_like(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    removed = crud.delete_super_like(db, user=user, post_id=post_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Nicio super-apreciere de retras.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/users/me/super-likes/quota", response_model=schemas.SuperLikeQuota)
def get_quota(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    quota = crud.weekly_quota_for_user(user)
    used = crud.get_user_weekly_super_like_count(db, user.id)
    return schemas.SuperLikeQuota(
        weekly_quota=quota,
        used_this_week=used,
        remaining=max(0, quota - used),
        week_resets_at=end_of_iso_week_utc(),
        is_premium=user.is_premium,
    )
```

- [ ] **Step 2: Register the router in `app/main.py`**

Edit the import at line 17:

```python
from .routers import auth_routes, user_routes, post_routes, message_routes, moderation_routes, api_pages, notification_routes, stats_routes, collection_routes, super_like_routes
```

Add after `app.include_router(collection_routes.router)`:

```python
app.include_router(super_like_routes.router)
```

- [ ] **Step 3: Smoke-check that the app still boots**

Run: `python -c "from app.main import app; print([r.path for r in app.routes if '/super-likes' in r.path])"`
Expected: three paths printed (POST, DELETE, GET quota).

- [ ] **Step 4: Commit**

```bash
git add app/routers/super_like_routes.py app/main.py
git commit -m "api: add super-like POST/DELETE endpoints + weekly quota GET"
```

---

## Task 7: Enrich post responses with `super_likes_count` + `viewer_super_liked`

**Files:**
- Modify: `app/routers/post_routes.py`
- Modify: `app/routers/api_pages.py`

- [ ] **Step 1: Find every place that returns a Post or a list of Posts**

Run: `grep -n "response_model=schemas.Post\|response_model=List\[schemas.Post\]" app/routers/*.py`
Note each location. For each, identify whether it's a single-post or list endpoint.

- [ ] **Step 2: Add a helper that attaches the two derived fields**

At the top of `app/routers/post_routes.py`, under the existing imports, add:

```python
from .. import crud

def _attach_super_like_fields(db, posts, current_user):
    """Mutate each post with super_likes_count + viewer_super_liked for serialization."""
    if not posts:
        return posts
    single = False
    if not isinstance(posts, list):
        posts = [posts]
        single = True
    post_ids = [p.id for p in posts]
    counts = dict(
        db.query(models.SuperLike.post_id, func.count(models.SuperLike.id))
        .filter(models.SuperLike.post_id.in_(post_ids))
        .group_by(models.SuperLike.post_id)
        .all()
    )
    liked_ids = set()
    if current_user:
        liked_ids = {
            row[0]
            for row in db.query(models.SuperLike.post_id)
            .filter(
                models.SuperLike.user_id == current_user.id,
                models.SuperLike.post_id.in_(post_ids),
            )
            .all()
        }
    for p in posts:
        setattr(p, "super_likes_count", counts.get(p.id, 0))
        setattr(p, "viewer_super_liked", p.id in liked_ids)
    return posts[0] if single else posts
```

Add `from sqlalchemy import func` and `from .. import models` if not present.

- [ ] **Step 3: Call the helper in every post-returning endpoint**

For each post-returning endpoint in `post_routes.py`, right before `return`, call:

```python
_attach_super_like_fields(db, result, current_user)
```

Take `current_user: Optional[models.User] = Depends(auth.get_current_user)` as a dependency on any endpoint that doesn't already have it.

- [ ] **Step 4: Do the same in `api_pages.py`**

Repeat Step 3 for any endpoint there that returns posts.

- [ ] **Step 5: Manual smoke test**

Run: `python run.py` (separate terminal).
Fetch a post via curl: `curl http://localhost:8000/api/posts/1 | python -m json.tool | head -20`
Expected: response contains `"super_likes_count": 0` and `"viewer_super_liked": false`.

- [ ] **Step 6: Commit**

```bash
git add app/routers/post_routes.py app/routers/api_pages.py
git commit -m "api: enrich post responses with super_likes_count and viewer_super_liked"
```

---

## Task 8: Stripe service wrapper

**Files:**
- Create: `app/stripe_service.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add the dependency**

Append a new line to `requirements.txt`:

```
stripe>=10.0.0
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Create `app/stripe_service.py`**

```python
import os
from typing import Optional

import stripe


STRIPE_ENABLED = os.getenv("STRIPE_ENABLED", "False").lower() in ("true", "1", "yes")


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"{name} is required when STRIPE_ENABLED=True. Set it in .env."
        )
    return val


if STRIPE_ENABLED:
    stripe.api_key = _require("STRIPE_SECRET_KEY")
    WEBHOOK_SECRET = _require("STRIPE_WEBHOOK_SECRET")
    PRICE_ID = _require("STRIPE_PRICE_ID_PREMIUM_MONTHLY")
    SUCCESS_URL = _require("STRIPE_SUCCESS_URL")
    CANCEL_URL = _require("STRIPE_CANCEL_URL")
    PORTAL_RETURN_URL = _require("STRIPE_CUSTOMER_PORTAL_RETURN_URL")
else:
    WEBHOOK_SECRET = PRICE_ID = SUCCESS_URL = CANCEL_URL = PORTAL_RETURN_URL = ""


def ensure_enabled() -> None:
    if not STRIPE_ENABLED:
        raise RuntimeError("Stripe is disabled. Set STRIPE_ENABLED=True in .env.")


def create_or_get_customer(email: str, user_id: int, existing_customer_id: Optional[str]) -> str:
    ensure_enabled()
    if existing_customer_id:
        return existing_customer_id
    customer = stripe.Customer.create(
        email=email,
        metadata={"user_id": str(user_id)},
    )
    return customer.id


def create_checkout_session(customer_id: str, user_id: int) -> str:
    ensure_enabled()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        client_reference_id=str(user_id),
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        success_url=SUCCESS_URL,
        cancel_url=CANCEL_URL,
        metadata={"user_id": str(user_id)},
    )
    return session.url


def create_billing_portal_session(customer_id: str) -> str:
    ensure_enabled()
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=PORTAL_RETURN_URL,
    )
    return session.url


def verify_webhook(payload: bytes, sig_header: str):
    ensure_enabled()
    return stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
```

- [ ] **Step 3: Commit**

```bash
git add app/stripe_service.py requirements.txt
git commit -m "stripe: add service wrapper with env-driven config + fail-fast validation"
```

---

## Task 9: Stripe user-CRUD helpers

**Files:**
- Modify: `app/crud.py`
- Modify: `tests/test_super_apreciez.py`

- [ ] **Step 1: Write failing test**

Append a new test class to `tests/test_super_apreciez.py`:

```python
class StripeUserCrudTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        models.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _user(self, name):
        u = models.User(username=name, email=f"{name}@x.t", google_id=f"g-{name}")
        self.db.add(u); self.db.commit(); self.db.refresh(u); return u

    def test_upsert_stripe_customer_id_sets_value(self):
        u = self._user("alice")
        crud.upsert_stripe_customer_id(self.db, user_id=u.id, customer_id="cus_123")
        self.db.refresh(u)
        self.assertEqual(u.stripe_customer_id, "cus_123")

    def test_get_user_by_stripe_customer_id_returns_user(self):
        u = self._user("alice")
        crud.upsert_stripe_customer_id(self.db, user_id=u.id, customer_id="cus_456")
        found = crud.get_user_by_stripe_customer_id(self.db, "cus_456")
        self.assertEqual(found.id, u.id)

    def test_set_premium_from_subscription_sets_fields(self):
        u = self._user("alice")
        expiry = datetime.utcnow() + timedelta(days=30)
        crud.set_premium_from_subscription(
            self.db,
            user_id=u.id,
            subscription_id="sub_x",
            premium_until=expiry,
        )
        self.db.refresh(u)
        self.assertEqual(u.stripe_subscription_id, "sub_x")
        self.assertAlmostEqual(u.premium_until.timestamp(), expiry.timestamp(), delta=1)

    def test_clear_subscription_keeps_premium_until(self):
        u = self._user("alice")
        future = datetime.utcnow() + timedelta(days=10)
        crud.set_premium_from_subscription(self.db, user_id=u.id, subscription_id="sub_x", premium_until=future)
        crud.clear_stripe_subscription(self.db, user_id=u.id)
        self.db.refresh(u)
        self.assertIsNone(u.stripe_subscription_id)
        self.assertIsNotNone(u.premium_until)
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_super_apreciez.StripeUserCrudTests -v`
Expected: FAIL — missing attributes on `crud`.

- [ ] **Step 3: Implement in `app/crud.py`**

Append:

```python
# ===================================
# STRIPE / PREMIUM CRUD
# ===================================

def upsert_stripe_customer_id(db: Session, user_id: int, customer_id: str) -> None:
    db.query(models.User).filter(models.User.id == user_id).update(
        {"stripe_customer_id": customer_id}
    )
    db.commit()


def get_user_by_stripe_customer_id(db: Session, customer_id: str) -> Optional[models.User]:
    return (
        db.query(models.User)
        .filter(models.User.stripe_customer_id == customer_id)
        .first()
    )


def set_premium_from_subscription(
    db: Session, user_id: int, subscription_id: str, premium_until: datetime
) -> None:
    db.query(models.User).filter(models.User.id == user_id).update(
        {
            "stripe_subscription_id": subscription_id,
            "premium_until": premium_until,
        }
    )
    db.commit()


def clear_stripe_subscription(db: Session, user_id: int) -> None:
    db.query(models.User).filter(models.User.id == user_id).update(
        {"stripe_subscription_id": None}
    )
    db.commit()


def record_stripe_event(db: Session, event_id: str, event_type: str) -> bool:
    """Return True if this is a new event; False if already processed."""
    existing = db.query(models.StripeEvent).filter(models.StripeEvent.id == event_id).first()
    if existing:
        return False
    db.add(models.StripeEvent(id=event_id, type=event_type))
    db.commit()
    return True
```

- [ ] **Step 4: Run, verify pass**

Run: `python -m unittest tests.test_super_apreciez.StripeUserCrudTests -v`
Expected: 4 pass.

- [ ] **Step 5: Commit**

```bash
git add app/crud.py tests/test_super_apreciez.py
git commit -m "crud: Stripe customer/subscription helpers + webhook event idempotency"
```

---

## Task 10: Premium router — checkout, portal, webhook

**Files:**
- Create: `app/routers/premium_routes.py`
- Modify: `app/main.py`
- Create: `tests/test_premium_webhook.py`

- [ ] **Step 1: Write webhook idempotency + signature tests**

Create `tests/test_premium_webhook.py`:

```python
import os
import json
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")
os.environ["STRIPE_ENABLED"] = "True"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_dummy"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_dummy"
os.environ["STRIPE_PRICE_ID_PREMIUM_MONTHLY"] = "price_dummy"
os.environ["STRIPE_SUCCESS_URL"] = "http://x/success"
os.environ["STRIPE_CANCEL_URL"] = "http://x/cancel"
os.environ["STRIPE_CUSTOMER_PORTAL_RETURN_URL"] = "http://x/dashboard"

from app import crud, models


def _mk_event(event_id, event_type, customer_id="cus_1", sub_id="sub_1", period_end_ts=None):
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": sub_id,
                "customer": customer_id,
                "current_period_end": period_end_ts or int((datetime.utcnow() + timedelta(days=30)).timestamp()),
            }
        },
    }


class WebhookIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = models.User(
            username="alice", email="a@x.t", google_id="g-a",
            stripe_customer_id="cus_1",
        )
        self.db.add(self.user); self.db.commit(); self.db.refresh(self.user)

    def tearDown(self):
        self.db.close(); models.Base.metadata.drop_all(self.engine); self.engine.dispose()

    def test_record_event_is_new_first_time(self):
        self.assertTrue(crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created"))

    def test_record_event_is_no_op_second_time(self):
        crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created")
        self.assertFalse(crud.record_stripe_event(self.db, "evt_1", "customer.subscription.created"))

    def test_process_subscription_updated_sets_premium_until(self):
        from app.routers.premium_routes import _apply_subscription_event
        ts = int((datetime.utcnow() + timedelta(days=15)).timestamp())
        event = _mk_event("evt_2", "customer.subscription.updated", period_end_ts=ts)
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertIsNotNone(self.user.premium_until)
        self.assertEqual(self.user.stripe_subscription_id, "sub_1")

    def test_process_subscription_deleted_clears_subscription_keeps_premium_until(self):
        from app.routers.premium_routes import _apply_subscription_event
        future = datetime.utcnow() + timedelta(days=20)
        crud.set_premium_from_subscription(self.db, user_id=self.user.id, subscription_id="sub_1", premium_until=future)
        event = _mk_event("evt_3", "customer.subscription.deleted")
        _apply_subscription_event(self.db, event)
        self.db.refresh(self.user)
        self.assertIsNone(self.user.stripe_subscription_id)
        self.assertIsNotNone(self.user.premium_until)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run, verify fail**

Run: `python -m unittest tests.test_premium_webhook -v`
Expected: FAIL — `premium_routes` not found.

- [ ] **Step 3: Create `app/routers/premium_routes.py`**

```python
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from .. import auth, crud, models, schemas, stripe_service
from ..database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_user(current_user):
    if not current_user:
        raise HTTPException(status_code=401, detail="Autentificare necesară.")
    return current_user


@router.post("/api/premium/checkout", response_model=schemas.PremiumCheckoutResponse)
def create_checkout(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    try:
        customer_id = stripe_service.create_or_get_customer(
            email=user.email,
            user_id=user.id,
            existing_customer_id=user.stripe_customer_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not user.stripe_customer_id:
        crud.upsert_stripe_customer_id(db, user_id=user.id, customer_id=customer_id)
    url = stripe_service.create_checkout_session(customer_id=customer_id, user_id=user.id)
    return schemas.PremiumCheckoutResponse(url=url)


@router.post("/api/premium/portal", response_model=schemas.PremiumPortalResponse)
def open_portal(
    current_user: models.User = Depends(auth.get_current_user),
):
    user = _require_user(current_user)
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Nu există un abonament asociat.")
    try:
        url = stripe_service.create_billing_portal_session(user.stripe_customer_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return schemas.PremiumPortalResponse(url=url)


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.verify_webhook(payload, sig_header)
    except Exception as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Idempotency guard.
    if not crud.record_stripe_event(db, event_id=event["id"], event_type=event["type"]):
        return Response(status_code=200)

    event_type = event["type"]
    if event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        _apply_subscription_event(db, event)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(db, event)
    # Unhandled types -> 200 (no retries).
    return Response(status_code=200)


def _apply_subscription_event(db: Session, event) -> None:
    data = event["data"]["object"]
    customer_id = data.get("customer")
    if not customer_id:
        return
    user = crud.get_user_by_stripe_customer_id(db, customer_id)
    if not user:
        logger.warning("Stripe webhook for unknown customer %s", customer_id)
        return
    event_type = event["type"]
    if event_type == "customer.subscription.deleted":
        crud.clear_stripe_subscription(db, user_id=user.id)
        return
    period_end_ts = data.get("current_period_end")
    if period_end_ts is None:
        return
    premium_until = datetime.utcfromtimestamp(int(period_end_ts))
    crud.set_premium_from_subscription(
        db,
        user_id=user.id,
        subscription_id=data.get("id"),
        premium_until=premium_until,
    )


def _handle_payment_failed(db: Session, event) -> None:
    data = event["data"]["object"]
    customer_id = data.get("customer")
    if not customer_id:
        return
    user = crud.get_user_by_stripe_customer_id(db, customer_id)
    if not user:
        return
    db.add(
        models.Notification(
            user_id=user.id,
            type="payment_failed",
            title="Plata abonamentului a eșuat",
            message="Ultima încercare de încasare a abonamentului Premium a eșuat. Actualizează metoda de plată în portalul de facturare.",
            link="/premium",
        )
    )
    db.commit()
```

- [ ] **Step 4: Register router + success/cancel passthroughs in `app/main.py`**

Edit `app/main.py` import at line 17:

```python
from .routers import auth_routes, user_routes, post_routes, message_routes, moderation_routes, api_pages, notification_routes, stats_routes, collection_routes, super_like_routes, premium_routes
```

Add after `app.include_router(super_like_routes.router)`:

```python
app.include_router(premium_routes.router)
```

- [ ] **Step 5: Run tests**

Run: `python -m unittest tests.test_premium_webhook -v`
Expected: 4 pass.

- [ ] **Step 6: Commit**

```bash
git add app/routers/premium_routes.py app/main.py tests/test_premium_webhook.py
git commit -m "api: Stripe checkout/portal/webhook endpoints with event idempotency"
```

---

## Task 11: Expose `is_premium` on `/api/users/me`

**Files:**
- Modify: `app/routers/user_routes.py`
- Modify: `app/schemas.py`

- [ ] **Step 1: Extend `UserInDB` schema**

In `app/schemas.py`, replace the body of `class UserInDB(UserBase)` (around line 39) with:

```python
class UserInDB(UserBase):
    id: int
    is_premium: bool = False
    premium_until: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Find the `/api/users/me` handler**

Run: `grep -n "/users/me\|api/users/me\|users/me" app/routers/user_routes.py`

- [ ] **Step 3: Ensure the response_model is `UserInDB` and that `is_premium` is populated**

Because `is_premium` is a `@property` on the model and Pydantic v2 with `from_attributes=True` picks it up automatically, no other change is needed. Just double-check the endpoint returns `schemas.UserInDB`.

- [ ] **Step 4: Smoke check**

Run: `python run.py` (separate terminal). Log in with a cookie or curl with session, then:
`curl -b "$COOKIE" http://localhost:8000/api/users/me | python -m json.tool`
Expected: response includes `"is_premium": false`, `"premium_until": null`.

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py app/routers/user_routes.py
git commit -m "api: include is_premium and premium_until in /api/users/me"
```

---

## Task 12: Frontend API clients — super-likes and premium

**Files:**
- Create: `frontend/src/api/superLikes.ts`
- Create: `frontend/src/api/premium.ts`

- [ ] **Step 1: Check existing API client style**

Run: `cat frontend/src/api/posts.ts | head -40`
Note the axios/fetch pattern and base URL convention.

- [ ] **Step 2: Create `frontend/src/api/superLikes.ts`**

Match the existing style (assumed axios-style `http` client; adapt if codebase uses `fetch`):

```ts
import { http } from "./http";  // or "./client" — match existing pattern

export type SuperLike = {
  id: number;
  post_id: number;
  user_id: number;
  created_at: string;
};

export type SuperLikeQuota = {
  weekly_quota: number;
  used_this_week: number;
  remaining: number;
  week_resets_at: string;
  is_premium: boolean;
};

export const superLikePost = (postId: number) =>
  http.post<SuperLike>(`/api/posts/${postId}/super-likes`).then(r => r.data);

export const unSuperLikePost = (postId: number) =>
  http.delete(`/api/posts/${postId}/super-likes`);

export const fetchSuperLikeQuota = () =>
  http.get<SuperLikeQuota>("/api/users/me/super-likes/quota").then(r => r.data);
```

- [ ] **Step 3: Create `frontend/src/api/premium.ts`**

```ts
import { http } from "./http";

export const startPremiumCheckout = async () => {
  const { data } = await http.post<{ url: string }>("/api/premium/checkout");
  window.location.assign(data.url);
};

export const openCustomerPortal = async () => {
  const { data } = await http.post<{ url: string }>("/api/premium/portal");
  window.location.assign(data.url);
};
```

- [ ] **Step 4: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors. If `./http` doesn't exist in the project, swap the import for whatever the existing API clients use (e.g. `./client` or a direct fetch wrapper).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/superLikes.ts frontend/src/api/premium.ts
git commit -m "frontend: API clients for super-likes and premium"
```

---

## Task 13: `<SuperLikeButton>` component

**Files:**
- Create: `frontend/src/components/ui/super-like-button.tsx`

- [ ] **Step 1: Create the component**

```tsx
import type { ButtonHTMLAttributes } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import {
  fetchSuperLikeQuota,
  superLikePost,
  unSuperLikePost,
} from "@/api/superLikes";

type SuperLikeButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  postId: number;
  postOwnerId: number;
  viewerId: number | null;          // null when not logged in
  superLikesCount: number;
  viewerSuperLiked: boolean;
  onChange?: (nextCount: number, nextLiked: boolean) => void;
};

function starIcon(active: boolean) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill={active ? "#D4AF37" : "none"} stroke={active ? "#D4AF37" : "currentColor"} strokeWidth="2">
      <polygon points="12 2 15 8.5 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 9 8.5 12 2" />
    </svg>
  );
}

export function SuperLikeButton({
  postId, postOwnerId, viewerId,
  superLikesCount, viewerSuperLiked,
  onChange, className, ...rest
}: SuperLikeButtonProps) {
  const qc = useQueryClient();
  const isOwn = viewerId != null && viewerId === postOwnerId;
  const notLoggedIn = viewerId == null;

  const { data: quota } = useQuery({
    queryKey: ["super-like-quota"],
    queryFn: fetchSuperLikeQuota,
    enabled: !notLoggedIn,
    staleTime: 30_000,
  });

  const superMutation = useMutation({
    mutationFn: () => viewerSuperLiked ? unSuperLikePost(postId) : superLikePost(postId),
    onSuccess: () => {
      onChange?.(
        viewerSuperLiked ? superLikesCount - 1 : superLikesCount + 1,
        !viewerSuperLiked,
      );
      qc.invalidateQueries({ queryKey: ["super-like-quota"] });
    },
  });

  const outOfQuota = quota != null && quota.remaining <= 0 && !viewerSuperLiked;
  const disabled = notLoggedIn || isOwn || outOfQuota || superMutation.isPending;

  let title = "Super-apreciez";
  if (notLoggedIn) title = "Autentifică-te pentru a super-aprecia";
  else if (isOwn) title = "Nu îți poți super-aprecia propria postare";
  else if (outOfQuota && quota?.is_premium) title = "Ai folosit toate super-aprecierile săptămâna aceasta. Următoarele: luni.";
  else if (outOfQuota) title = "Ai folosit super-aprecierea săptămâna aceasta. Upgrade la Premium pentru 3 pe săptămână.";
  else if (quota) title = `Îți mai rămân ${quota.remaining} super-aprecieri săptămâna aceasta.`;

  return (
    <button
      type="button"
      className={cn("react-btn react-super", viewerSuperLiked && "on", className)}
      title={title}
      aria-pressed={viewerSuperLiked}
      disabled={disabled}
      onClick={() => superMutation.mutate()}
      {...rest}
    >
      {starIcon(viewerSuperLiked)}
      <span>Super-apreciez</span>
      {superLikesCount > 0 && <span className="react-count">{superLikesCount}</span>}
    </button>
  );
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend && npx tsc --noEmit`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/super-like-button.tsx
git commit -m "frontend: SuperLikeButton with quota-aware tooltips and optimistic mutation"
```

---

## Task 14: Golden border CSS + `.has-super-like` application

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Append styling rules**

At the end of `frontend/src/index.css`:

```css
.has-super-like .piece-title,
.has-super-like .post-title,
.has-super-like h1,
.has-super-like h2 {
  position: relative;
}

.has-super-like .piece-title::after,
.has-super-like .post-title::after,
.has-super-like h1.super-titled::after,
.has-super-like h2.super-titled::after {
  content: "";
  display: block;
  height: 2px;
  margin-top: 4px;
  background: linear-gradient(90deg, transparent 0%, #D4AF37 20%, #D4AF37 80%, transparent 100%);
  box-shadow: 0 0 6px rgba(212, 175, 55, 0.4);
}

.react-btn.react-super.on {
  color: #D4AF37;
  border-color: #D4AF37;
}
```

Note: rule targets use the project's existing title classes. If `piece-title` / `post-title` aren't the right class names in your codebase, adjust. Grep first:
`grep -rn "post-title\|piece-title" frontend/src | head -10`

- [ ] **Step 2: Commit**

```bash
git add frontend/src/index.css
git commit -m "frontend: golden accent styling for posts with super-apreciez"
```

---

## Task 15: Wire button + border into `PostDetailPage`

**Files:**
- Modify: `frontend/src/pages/PostDetailPage.tsx`
- Modify: `frontend/src/api/posts.ts`

- [ ] **Step 1: Extend Post type**

In `frontend/src/api/posts.ts`, find the `Post` type definition and add:

```ts
  super_likes_count: number;
  viewer_super_liked: boolean;
```

- [ ] **Step 2: Render the button and border in `PostDetailPage`**

Import at top:

```tsx
import { SuperLikeButton } from "@/components/ui/super-like-button";
```

Find the root container. Add `has-super-like` class conditionally:

```tsx
<article className={cn("post-detail", post.super_likes_count > 0 && "has-super-like")}>
```

Next to the existing `ReactionButton` for likes, add:

```tsx
<SuperLikeButton
  postId={post.id}
  postOwnerId={post.user_id}
  viewerId={currentUser?.id ?? null}
  superLikesCount={post.super_likes_count ?? 0}
  viewerSuperLiked={post.viewer_super_liked ?? false}
  onChange={(nextCount, nextLiked) => {
    queryClient.setQueryData(["post", slug], (old: any) => old && ({
      ...old,
      super_likes_count: nextCount,
      viewer_super_liked: nextLiked,
    }));
  }}
/>
```

(Adjust query key to match whatever the page actually uses — grep for `useQuery` in the file.)

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Manual smoke test**

Run: `python run.py`. Open a post in the browser, verify the button appears, click it, verify count increments and a gold bar appears under the title.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PostDetailPage.tsx frontend/src/api/posts.ts
git commit -m "frontend: render SuperLikeButton and golden accent on PostDetailPage"
```

---

## Task 16: Golden border on post cards across pages

**Files:**
- Modify: `frontend/src/pages/LandingPage.tsx`
- Modify: `frontend/src/pages/BlogHomePage.tsx`
- Modify: `frontend/src/pages/CategoryPage.tsx`
- Modify: `frontend/src/pages/CollectionDetailPage.tsx`

- [ ] **Step 1: Find the post-card rendering block in each page**

Run: `grep -n "piece-card\|post-card\|PostCard" frontend/src/pages/*.tsx`

- [ ] **Step 2: In each page, add `has-super-like` to the card root based on `post.super_likes_count > 0`**

Example diff pattern:

```tsx
<article className={cn("piece-card", post.super_likes_count > 0 && "has-super-like")}>
```

Repeat in each of the four pages. Do not add the button here (lists don't need the button).

- [ ] **Step 3: Build + smoke-test**

Run: `cd frontend && npm run build`
Expected: clean. Visually verify in the browser that a post with a super-like shows the gold accent in list views.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/LandingPage.tsx frontend/src/pages/BlogHomePage.tsx frontend/src/pages/CategoryPage.tsx frontend/src/pages/CollectionDetailPage.tsx
git commit -m "frontend: golden border on post cards across list pages"
```

---

## Task 17: `/premium` page, success page, cancel page

**Files:**
- Create: `frontend/src/pages/PremiumPage.tsx`
- Create: `frontend/src/pages/PremiumSuccessPage.tsx`
- Create: `frontend/src/pages/PremiumCancelPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: `PremiumPage.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { startPremiumCheckout, openCustomerPortal } from "@/api/premium";
import { fetchCurrentUser } from "@/api/auth";  // whatever the project uses
import { Button } from "@/components/ui/button";

export default function PremiumPage() {
  const { data: user } = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser });

  if (!user) {
    return (
      <div className="prose">
        <h1>Premium</h1>
        <p>Autentifică-te pentru a accesa Premium.</p>
        <Link to="/register">Autentifică-te</Link>
      </div>
    );
  }

  if (user.is_premium) {
    return (
      <div className="prose">
        <h1>Ești Premium</h1>
        <p>Abonamentul tău este activ până la{" "}
          {user.premium_until ? new Date(user.premium_until).toLocaleDateString("ro-RO") : "—"}.
        </p>
        <Button onClick={openCustomerPortal}>Gestionează abonamentul</Button>
      </div>
    );
  }

  return (
    <div className="prose">
      <h1>Devino Premium</h1>
      <ul>
        <li>3 super-aprecieri pe săptămână (în loc de 1)</li>
        <li>Susții dezvoltarea platformei</li>
      </ul>
      <p><strong>3.99 € / lună</strong></p>
      <Button onClick={startPremiumCheckout}>Devino Premium</Button>
    </div>
  );
}
```

- [ ] **Step 2: `PremiumSuccessPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCurrentUser } from "@/api/auth";

export default function PremiumSuccessPage() {
  const nav = useNavigate();
  const [tries, setTries] = useState(0);

  useEffect(() => {
    let mounted = true;
    let timer: number;
    const poll = async () => {
      const user = await fetchCurrentUser().catch(() => null);
      if (!mounted) return;
      if (user?.is_premium) {
        nav("/dashboard", { replace: true });
        return;
      }
      if (tries < 10) {
        timer = window.setTimeout(() => setTries(t => t + 1), 1000);
      }
    };
    poll();
    return () => { mounted = false; if (timer) clearTimeout(timer); };
  }, [tries, nav]);

  return (
    <div className="prose">
      <h1>Mulțumim!</h1>
      <p>Contul tău este acum Premium. Te redirecționăm...</p>
    </div>
  );
}
```

- [ ] **Step 3: `PremiumCancelPage.tsx`**

```tsx
import { Link } from "react-router-dom";

export default function PremiumCancelPage() {
  return (
    <div className="prose">
      <h1>Plata a fost anulată</h1>
      <p>Nicio problemă, poate altă dată.</p>
      <Link to="/premium">Încearcă din nou</Link>
    </div>
  );
}
```

- [ ] **Step 4: Wire routes into `App.tsx`**

In the non-subdomain `<Routes>` block, add:

```tsx
<Route path="premium" element={<PremiumPage />} />
<Route path="premium/success" element={<PremiumSuccessPage />} />
<Route path="premium/cancel" element={<PremiumCancelPage />} />
```

And add the lazy imports at the top with the rest:

```tsx
const PremiumPage = lazy(() => import("@/pages/PremiumPage"));
const PremiumSuccessPage = lazy(() => import("@/pages/PremiumSuccessPage"));
const PremiumCancelPage = lazy(() => import("@/pages/PremiumCancelPage"));
```

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/PremiumPage.tsx frontend/src/pages/PremiumSuccessPage.tsx frontend/src/pages/PremiumCancelPage.tsx frontend/src/App.tsx
git commit -m "frontend: /premium, /premium/success, /premium/cancel pages"
```

---

## Task 18: SideMenu entry + Dashboard banner

**Files:**
- Modify: `frontend/src/components/layout/SideMenu.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Add "Premium" link to SideMenu**

Find the main menu item list and add (label, path):

```tsx
<Link to="/premium">Premium</Link>
```

Match the existing styling of other menu entries.

- [ ] **Step 2: Add dashboard banner for free users**

Near the top of the dashboard's main section, after `const { data: user } = useQuery(...)`:

```tsx
{user && !user.is_premium && (
  <div className="premium-banner">
    <span>Vrei 3 super-aprecieri pe săptămână? </span>
    <Link to="/premium">Upgrade la Premium</Link>
  </div>
)}
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/SideMenu.tsx frontend/src/pages/DashboardPage.tsx
git commit -m "frontend: add Premium entry point in SideMenu and Dashboard banner"
```

---

## Task 19: Document `.env` additions

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add Stripe vars to the Environment Variables section of `CLAUDE.md`**

After the existing env var docs, add:

```markdown
- **STRIPE_ENABLED**: `True` to enable Stripe integration, `False` for dev without payments
- **STRIPE_SECRET_KEY**: Stripe secret API key (`sk_test_...` or `sk_live_...`)
- **STRIPE_PUBLISHABLE_KEY**: Stripe publishable key (`pk_test_...` or `pk_live_...`)
- **STRIPE_WEBHOOK_SECRET**: Stripe webhook signing secret (`whsec_...`)
- **STRIPE_PRICE_ID_PREMIUM_MONTHLY**: Stripe Price ID for the €3.99/mo premium plan (configured in Stripe dashboard)
- **STRIPE_SUCCESS_URL**: Checkout success redirect URL, include `?session_id={CHECKOUT_SESSION_ID}` literal
- **STRIPE_CANCEL_URL**: Checkout cancel redirect URL
- **STRIPE_CUSTOMER_PORTAL_RETURN_URL**: Return URL from the Stripe Billing Portal
```

Tell the user to populate `.env` with real values (we don't touch `.env` directly).

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document Stripe env vars for Super-apreciez Premium"
```

---

## Task 20: End-to-end smoke checklist

- [ ] Run `python scripts/initdb.py` to recreate the DB with the new schema.
- [ ] Run `python -m unittest tests.test_super_apreciez tests.test_premium_webhook tests.test_backend_stabilization -v`. All pass.
- [ ] Run `cd frontend && npm run build`. Clean build.
- [ ] Run `python run.py`. Open `http://<dev-domain>/` — landing page loads.
- [ ] Open a post. Click the super-apreciez button. Count goes from 0 → 1, gold bar appears beneath the title.
- [ ] Click it again — count returns to 0, gold bar disappears (within the same ISO week).
- [ ] Log in as a different user. Super-apreciez the same post. Count becomes 1 again; the golden bar reappears.
- [ ] Try to super-apreciez your own post — button is disabled with the expected tooltip.
- [ ] With a free account, super-apreciez a post. Try to super-apreciez a second post the same week — blocked with the quota tooltip.
- [ ] Manually set `premium_until` in the DB to a future date. Refresh. Confirm `/api/users/me/super-likes/quota` now returns `weekly_quota: 3`.
- [ ] In Stripe test mode: visit `/premium`, click "Devino Premium", complete checkout with card `4242 4242 4242 4242`. After redirect, within ~10s `is_premium` flips true on `/api/users/me`. Super-apreciez quota shows 3.
- [ ] In Stripe dashboard, cancel the subscription manually. Webhook fires. User's `stripe_subscription_id` clears but `premium_until` remains until the period ends.

---

## Self-Review

**Spec coverage:**
- Feature rules (quota, self-ban, duplicate-ban, toggle, weekly reset, golden border, €3.99 premium) — Tasks 1–4, 6, 13, 14, 15, 16 ✓
- Data model (super_likes, stripe_events, User Stripe fields, Post.super_likes_count) — Tasks 1, 2 ✓
- API endpoints (super-likes POST/DELETE/quota, premium checkout/portal/webhook) — Tasks 6, 10, 11 ✓
- Post-list enrichment — Task 7 ✓
- Stripe integration (env, hosted checkout, portal, webhook with signature + idempotency) — Tasks 8, 9, 10 ✓
- Frontend (API clients, button, CSS, card borders, premium pages, entry points) — Tasks 12–18 ✓
- Env documentation — Task 19 ✓
- E2E verification — Task 20 ✓

**Placeholder scan:** No TBDs, no "add appropriate X", no "similar to previous task." Every code block is real code the engineer can paste.

**Type consistency:** Function names match across tasks — `create_super_like`, `delete_super_like`, `get_user_weekly_super_like_count`, `user_super_liked_post`, `weekly_quota_for_user`, `upsert_stripe_customer_id`, `get_user_by_stripe_customer_id`, `set_premium_from_subscription`, `clear_stripe_subscription`, `record_stripe_event`. Component names match: `SuperLikeButton`, `PremiumPage`, `PremiumSuccessPage`, `PremiumCancelPage`. Error classes match: `SuperLikePostNotFoundError`, `SuperLikeSelfError`, `SuperLikeDuplicateError`, `SuperLikeQuotaError`.

**Known caveat for the executing agent:** the frontend HTTP client module path (`@/api/http`) is a guess — grep the codebase (`grep -rn "import.*http\|apiClient\|axios" frontend/src/api | head`) to confirm the right import path before writing the new clients, and adapt if necessary. Similarly, the exact title/card class names in CSS rules (Task 14) and card components (Task 16) should be confirmed with grep before committing.
