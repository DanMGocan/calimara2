from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models
from ..repositories.notifications import create_notification
from ..week_util import utcnow_naive

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AchievementEvent:
    event_type: str
    occurred_at: datetime
    actor_user_id: Optional[int] = None
    source_type: Optional[str] = None
    source_id: Optional[int] = None
    context: dict[str, Any] = field(default_factory=dict)


Condition = Callable[[Session, AchievementEvent], bool]
UserSelector = Callable[[Session, AchievementEvent], Optional[int]]
StringSelector = Callable[[Session, AchievementEvent], str]
OptionalStringSelector = Callable[[Session, AchievementEvent], Optional[str]]
OptionalIntSelector = Callable[[Session, AchievementEvent], Optional[int]]
MetadataBuilder = Callable[[Session, AchievementEvent], dict[str, Any]]


@dataclass(frozen=True)
class AchievementDefinition:
    key: str
    title: str
    description: str
    award_type: str
    event_type: str
    awardee_user_id: UserSelector
    condition: Condition
    dedupe_key: StringSelector
    source_type: OptionalStringSelector = lambda _db, event: event.source_type
    source_id: OptionalIntSelector = lambda _db, event: event.source_id
    metadata: MetadataBuilder = lambda _db, _event: {}
    notification_link: OptionalStringSelector = lambda _db, _event: None


def _naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    if not value:
        return None
    if value.tzinfo:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _is_within_window(event_at: datetime, starts_at: Optional[datetime], window: timedelta) -> bool:
    start = _naive_utc(starts_at)
    event_time = _naive_utc(event_at)
    if not start or not event_time:
        return False
    return start <= event_time <= start + window


def _post_from_event(db: Session, event: AchievementEvent) -> Optional[models.Post]:
    post = event.context.get("post")
    if post is not None:
        return post
    post_id = event.context.get("post_id")
    if not post_id:
        return None
    return db.query(models.Post).filter(models.Post.id == post_id).first()


def _hermes_awardee(db: Session, event: AchievementEvent) -> Optional[int]:
    post = _post_from_event(db, event)
    return post.user_id if post else None


def _hermes_condition(db: Session, event: AchievementEvent) -> bool:
    post = _post_from_event(db, event)
    if not post or post.moderation_status != "approved":
        return False
    return _is_within_window(event.occurred_at, post.moderated_at, timedelta(hours=1))


def _hermes_metadata(db: Session, event: AchievementEvent) -> dict[str, Any]:
    post = _post_from_event(db, event)
    if not post:
        return {}
    return {
        "post_id": post.id,
        "post_title": post.title,
        "post_slug": post.slug,
        "public_at": post.moderated_at.isoformat() if post.moderated_at else None,
    }


def _post_link(db: Session, event: AchievementEvent) -> Optional[str]:
    post = _post_from_event(db, event)
    return f"/{post.slug}" if post and post.slug else None


ACHIEVEMENTS: tuple[AchievementDefinition, ...] = (
    AchievementDefinition(
        key="piciorul-lui-hermes",
        title="Piciorul lui Hermes",
        description="Ai primit o Super-apreciere în prima oră după publicarea unui text.",
        award_type="special",
        event_type="super_like_created",
        awardee_user_id=_hermes_awardee,
        condition=_hermes_condition,
        dedupe_key=lambda _db, _event: "once",
        source_type=lambda _db, _event: "super_like",
        source_id=lambda _db, event: event.source_id,
        metadata=_hermes_metadata,
        notification_link=_post_link,
    ),
)


def grant_achievement(
    db: Session,
    definition: AchievementDefinition,
    *,
    user_id: int,
    dedupe_key: str,
    source_type: Optional[str] = None,
    source_id: Optional[int] = None,
    occurred_at: Optional[datetime] = None,
    metadata: Optional[dict[str, Any]] = None,
    notification_link: Optional[str] = None,
) -> tuple[models.UserAward, bool]:
    awarded_at = _naive_utc(occurred_at) or utcnow_naive()
    existing = (
        db.query(models.UserAward)
        .filter(
            models.UserAward.user_id == user_id,
            models.UserAward.achievement_key == definition.key,
            models.UserAward.dedupe_key == dedupe_key,
        )
        .first()
    )
    if existing:
        return existing, False

    award = models.UserAward(
        user_id=user_id,
        achievement_key=definition.key,
        dedupe_key=dedupe_key,
        award_title=definition.title,
        award_description=definition.description,
        award_date=awarded_at.date(),
        award_type=definition.award_type,
        source_type=source_type,
        source_id=source_id,
        awarded_at=awarded_at,
        extra_data=metadata or {},
    )
    db.add(award)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(models.UserAward)
            .filter(
                models.UserAward.user_id == user_id,
                models.UserAward.achievement_key == definition.key,
                models.UserAward.dedupe_key == dedupe_key,
            )
            .first()
        )
        if existing:
            return existing, False
        raise

    db.refresh(award)
    try:
        create_notification(
            db=db,
            user_id=user_id,
            notif_type="achievement_unlocked",
            title=f"Distincție deblocată: {definition.title}",
            message=definition.description,
            link=notification_link,
            extra_data={
                "achievement_key": definition.key,
                "award_id": award.id,
                "source_type": source_type,
                "source_id": source_id,
            },
        )
    except Exception:
        db.rollback()
        logger.exception("Could not create achievement notification for %s user=%s", definition.key, user_id)
    return award, True


def evaluate_achievements(
    db: Session,
    event: AchievementEvent,
    definitions: Iterable[AchievementDefinition] = ACHIEVEMENTS,
) -> list[models.UserAward]:
    awarded: list[models.UserAward] = []
    for definition in definitions:
        if definition.event_type != event.event_type:
            continue
        try:
            if not definition.condition(db, event):
                continue
            user_id = definition.awardee_user_id(db, event)
            if not user_id:
                continue
            award, created = grant_achievement(
                db,
                definition,
                user_id=user_id,
                dedupe_key=definition.dedupe_key(db, event),
                source_type=definition.source_type(db, event),
                source_id=definition.source_id(db, event),
                occurred_at=event.occurred_at,
                metadata=definition.metadata(db, event),
                notification_link=definition.notification_link(db, event),
            )
            if created:
                awarded.append(award)
        except Exception:
            db.rollback()
            logger.exception("Achievement evaluation failed for %s on %s", definition.key, event.event_type)
    return awarded


def emit_post_approved(db: Session, post: models.Post) -> list[models.UserAward]:
    occurred_at = _naive_utc(post.moderated_at) or utcnow_naive()
    return evaluate_achievements(
        db,
        AchievementEvent(
            event_type="post_approved",
            occurred_at=occurred_at,
            actor_user_id=post.user_id,
            source_type="post",
            source_id=post.id,
            context={"post": post, "post_id": post.id},
        ),
    )


def emit_super_like_created(db: Session, super_like: models.SuperLike) -> list[models.UserAward]:
    post = super_like.post or db.query(models.Post).filter(models.Post.id == super_like.post_id).first()
    return evaluate_achievements(
        db,
        AchievementEvent(
            event_type="super_like_created",
            occurred_at=_naive_utc(super_like.created_at) or utcnow_naive(),
            actor_user_id=super_like.user_id,
            source_type="super_like",
            source_id=super_like.id,
            context={
                "post": post,
                "post_id": super_like.post_id,
                "super_like": super_like,
                "super_like_id": super_like.id,
            },
        ),
    )
