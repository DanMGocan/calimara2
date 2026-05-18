from __future__ import annotations

from html import escape
from typing import Iterable, Optional

from pydantic import ValidationError

from ._shared import *
from .jobs import enqueue_ai_job
from .notifications import create_notification
from .posts import create_user_post
from .slugs import generate_slug
from .users import get_user_by_username
from ..schemas.common import _validate_post_content_limit


JOB_STAFETA_SEGMENT_MODERATION = "stafeta_segment_moderation"
JOB_STAFETA_TURN_TIMEOUT = "stafeta_turn_timeout"
STAFETA_OPEN_ASSIGNMENT_STATUSES = ("pending", "active")
STAFETA_SLOT_CAPS = {
    "free": 3,
    "trubadur": 3,
    "cronicar": 6,
    "rapsod": 10,
}


def _generate_stafeta_slug(title: str) -> str:
    return generate_slug(title, fallback="stafeta")


def _ensure_unique_stafeta_slug(db: Session, base_slug: str) -> str:
    slug = base_slug or "stafeta"
    counter = 1
    while db.query(models.StafetaWork).filter(models.StafetaWork.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _stafeta_link(work: models.StafetaWork) -> str:
    return f"/stafeta/{work.slug}"


def _deadline_for_assignment(work: models.StafetaWork, user_id: int) -> Optional[datetime]:
    if user_id == work.creator_id:
        return None
    return utcnow_naive() + timedelta(days=int(work.deadline_days or 1))


def _user_ref(user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
    }


def stafeta_max_slots_for_user(user: models.User) -> int:
    if not getattr(user, "is_premium", False):
        return STAFETA_SLOT_CAPS["free"]
    tier = getattr(user, "premium_tier", "free") or "free"
    return STAFETA_SLOT_CAPS.get(tier, STAFETA_SLOT_CAPS["free"])


def _normalize_stafeta_desired_slots(
    user: models.User,
    participates: bool,
    desired_slots: Optional[int],
    existing_slots: Optional[int] = None,
) -> int:
    if not participates:
        return 0
    max_slots = stafeta_max_slots_for_user(user)
    raw_slots = desired_slots
    if raw_slots is None:
        raw_slots = existing_slots if existing_slots and existing_slots > 0 else max_slots
    return max(1, min(int(raw_slots or max_slots), max_slots))


def count_user_open_stafeta_assignments(
    db: Session,
    user_id: int,
    *,
    ignore_assignment_id: Optional[int] = None,
) -> int:
    query = (
        db.query(func.count(models.StafetaAssignment.id))
        .join(models.StafetaWork, models.StafetaWork.id == models.StafetaAssignment.work_id)
        .filter(
            models.StafetaAssignment.user_id == user_id,
            models.StafetaAssignment.status.in_(STAFETA_OPEN_ASSIGNMENT_STATUSES),
            models.StafetaWork.status == "active",
        )
    )
    if ignore_assignment_id:
        query = query.filter(models.StafetaAssignment.id != ignore_assignment_id)
    return int(query.scalar() or 0)


def get_stafeta_participation_state(db: Session, user: models.User) -> dict:
    participant = (
        db.query(models.StafetaParticipant)
        .filter(models.StafetaParticipant.user_id == user.id)
        .first()
    )
    max_slots = stafeta_max_slots_for_user(user)
    participates = bool(participant and participant.is_active)
    desired_slots = 0
    if participates:
        desired_slots = _normalize_stafeta_desired_slots(
            user,
            True,
            getattr(participant, "desired_slots", 0) or None,
            getattr(participant, "desired_slots", 0) or None,
        )
    return {
        "participates": participates,
        "desired_slots": desired_slots,
        "max_slots": max_slots,
        "open_assignments": count_user_open_stafeta_assignments(db, user.id),
    }


def set_stafeta_participation(
    db: Session,
    user: models.User,
    participates: bool,
    desired_slots: Optional[int] = None,
) -> models.StafetaParticipant:
    participant = (
        db.query(models.StafetaParticipant)
        .filter(models.StafetaParticipant.user_id == user.id)
        .first()
    )
    normalized_slots = _normalize_stafeta_desired_slots(
        user,
        bool(participates),
        desired_slots,
        getattr(participant, "desired_slots", None) if participant else None,
    )
    if participant:
        participant.is_active = bool(participates)
        participant.desired_slots = normalized_slots
    else:
        participant = models.StafetaParticipant(
            user_id=user.id,
            is_active=bool(participates),
            desired_slots=normalized_slots,
        )
        db.add(participant)
    db.commit()
    db.refresh(participant)
    if participant.is_active and participant.desired_slots > 0:
        match_stafeta_pool(db)
        db.refresh(participant)
    return participant


def get_stafeta_participation(db: Session, user_id: int) -> bool:
    return (
        db.query(models.StafetaParticipant.id)
        .filter(
            models.StafetaParticipant.user_id == user_id,
            models.StafetaParticipant.is_active == True,
        )
        .first()
        is not None
    )


def enqueue_stafeta_segment_moderation_job(db: Session, segment: models.StafetaSegment) -> models.AIJob:
    return enqueue_ai_job(
        db,
        job_type=JOB_STAFETA_SEGMENT_MODERATION,
        target_type="stafeta_segment",
        target_id=segment.id,
        payload={"content_hash": _content_hash(segment.content)},
        max_attempts=3,
    )


def enqueue_stafeta_turn_timeout_job(db: Session, assignment: models.StafetaAssignment) -> Optional[models.AIJob]:
    if not assignment.due_at or assignment.status != "active":
        return None
    return enqueue_ai_job(
        db,
        job_type=JOB_STAFETA_TURN_TIMEOUT,
        target_type="stafeta_assignment",
        target_id=assignment.id,
        payload={"work_id": assignment.work_id, "due_at": assignment.due_at.isoformat()},
        max_attempts=1,
        dedupe=False,
        run_after=assignment.due_at,
    )


def _content_hash(content: str | None) -> str:
    import hashlib

    digest = hashlib.sha256()
    digest.update((content or "").encode("utf-8"))
    digest.update(b"\0")
    return digest.hexdigest()


def get_stafeta_work(db: Session, work_id: int) -> Optional[models.StafetaWork]:
    return (
        db.query(models.StafetaWork)
        .options(
            joinedload(models.StafetaWork.creator),
            joinedload(models.StafetaWork.current_holder),
            joinedload(models.StafetaWork.published_post),
        )
        .filter(models.StafetaWork.id == work_id)
        .first()
    )


def get_stafeta_work_by_slug(db: Session, slug: str) -> Optional[models.StafetaWork]:
    return (
        db.query(models.StafetaWork)
        .options(
            joinedload(models.StafetaWork.creator),
            joinedload(models.StafetaWork.current_holder),
            joinedload(models.StafetaWork.published_post),
            joinedload(models.StafetaWork.assignments).joinedload(models.StafetaAssignment.user),
            joinedload(models.StafetaWork.assignments).joinedload(models.StafetaAssignment.assigned_by),
            joinedload(models.StafetaWork.segments).joinedload(models.StafetaSegment.author),
            joinedload(models.StafetaWork.segments).joinedload(models.StafetaSegment.next_target_user),
        )
        .filter(models.StafetaWork.slug == slug)
        .first()
    )


def get_stafeta_assignment(db: Session, assignment_id: int) -> Optional[models.StafetaAssignment]:
    return (
        db.query(models.StafetaAssignment)
        .options(
            joinedload(models.StafetaAssignment.work),
            joinedload(models.StafetaAssignment.user),
            joinedload(models.StafetaAssignment.assigned_by),
        )
        .filter(models.StafetaAssignment.id == assignment_id)
        .first()
    )


def get_stafeta_segment(db: Session, segment_id: int) -> Optional[models.StafetaSegment]:
    return (
        db.query(models.StafetaSegment)
        .options(
            joinedload(models.StafetaSegment.work),
            joinedload(models.StafetaSegment.assignment),
            joinedload(models.StafetaSegment.author),
            joinedload(models.StafetaSegment.next_target_user),
        )
        .filter(models.StafetaSegment.id == segment_id)
        .first()
    )


def list_stafeta_segments(db: Session, work_id: int) -> list[models.StafetaSegment]:
    return (
        db.query(models.StafetaSegment)
        .options(
            joinedload(models.StafetaSegment.author),
            joinedload(models.StafetaSegment.next_target_user),
        )
        .filter(models.StafetaSegment.work_id == work_id)
        .order_by(models.StafetaSegment.position.asc(), models.StafetaSegment.id.asc())
        .all()
    )


def list_stafeta_assignments(db: Session, work_id: int) -> list[models.StafetaAssignment]:
    return (
        db.query(models.StafetaAssignment)
        .options(
            joinedload(models.StafetaAssignment.user),
            joinedload(models.StafetaAssignment.assigned_by),
        )
        .filter(models.StafetaAssignment.work_id == work_id)
        .order_by(models.StafetaAssignment.created_at.asc(), models.StafetaAssignment.id.asc())
        .all()
    )


def get_current_stafeta_assignment(db: Session, work: models.StafetaWork) -> Optional[models.StafetaAssignment]:
    if not work.current_assignment_id:
        return None
    return get_stafeta_assignment(db, work.current_assignment_id)


def _next_segment_position(db: Session, work_id: int) -> int:
    current = db.query(func.coalesce(func.max(models.StafetaSegment.position), 0)).filter(
        models.StafetaSegment.work_id == work_id
    ).scalar()
    return int(current or 0) + 1


def _participant_user_ids(db: Session, work_id: int) -> set[int]:
    segment_user_ids = {
        row[0]
        for row in db.query(models.StafetaSegment.author_id)
        .filter(models.StafetaSegment.work_id == work_id)
        .distinct()
        .all()
    }
    assignment_user_ids = {
        row[0]
        for row in db.query(models.StafetaAssignment.user_id)
        .filter(models.StafetaAssignment.work_id == work_id)
        .distinct()
        .all()
    }
    return segment_user_ids | assignment_user_ids


def list_previous_stafeta_participants(
    db: Session,
    work: models.StafetaWork,
    *,
    exclude_user_id: Optional[int] = None,
) -> list[models.User]:
    ids = _participant_user_ids(db, work.id)
    ids.discard(work.creator_id)
    if exclude_user_id:
        ids.discard(exclude_user_id)
    if not ids:
        return []
    return (
        db.query(models.User)
        .filter(models.User.id.in_(ids), models.User.is_suspended == False)
        .order_by(func.lower(models.User.username).asc(), models.User.id.asc())
        .all()
    )


def _user_open_stafeta_counts(
    db: Session,
    user_ids: Iterable[int],
    *,
    ignore_assignment_id: Optional[int] = None,
) -> dict[int, int]:
    ids = {item for item in user_ids if item}
    if not ids:
        return {}
    query = (
        db.query(models.StafetaAssignment.user_id, func.count(models.StafetaAssignment.id))
        .join(models.StafetaWork, models.StafetaWork.id == models.StafetaAssignment.work_id)
        .filter(
            models.StafetaAssignment.user_id.in_(ids),
            models.StafetaAssignment.status.in_(STAFETA_OPEN_ASSIGNMENT_STATUSES),
            models.StafetaWork.status == "active",
        )
        .group_by(models.StafetaAssignment.user_id)
    )
    if ignore_assignment_id:
        query = query.filter(models.StafetaAssignment.id != ignore_assignment_id)
    return {int(user_id): int(count or 0) for user_id, count in query.all()}


def _participant_effective_slots(user: models.User, participant: models.StafetaParticipant) -> int:
    return _normalize_stafeta_desired_slots(
        user,
        True,
        getattr(participant, "desired_slots", 0) or None,
        getattr(participant, "desired_slots", 0) or None,
    )


def _eligible_random_stafeta_recipients(
    db: Session,
    *,
    excluded_ids: Iterable[int],
) -> list[tuple[int, datetime, int, models.User]]:
    excluded = {item for item in excluded_ids if item}
    rows = (
        db.query(models.User, models.StafetaParticipant)
        .join(models.StafetaParticipant, models.StafetaParticipant.user_id == models.User.id)
        .filter(
            models.StafetaParticipant.is_active == True,
            models.User.is_suspended == False,
        )
        .all()
    )
    rows = [(user, participant) for user, participant in rows if user.id not in excluded]
    counts = _user_open_stafeta_counts(db, [user.id for user, _participant in rows])
    candidates: list[tuple[int, datetime, int, models.User]] = []
    far_past = datetime(1970, 1, 1)
    for user, participant in rows:
        desired_slots = _participant_effective_slots(user, participant)
        open_count = counts.get(user.id, 0)
        if desired_slots <= 0 or open_count >= desired_slots:
            continue
        last_assigned_at = participant.last_assigned_at or participant.created_at or far_past
        candidates.append((open_count, last_assigned_at, user.id, user))
    return sorted(candidates, key=lambda item: (item[0], item[1], item[2]))


def stafeta_assignment_limit_for_user(db: Session, user: models.User) -> int:
    participant = (
        db.query(models.StafetaParticipant)
        .filter(models.StafetaParticipant.user_id == user.id)
        .first()
    )
    if participant and participant.is_active:
        return _participant_effective_slots(user, participant)
    return stafeta_max_slots_for_user(user)


def user_has_stafeta_assignment_capacity(
    db: Session,
    user: models.User,
    *,
    ignore_assignment_id: Optional[int] = None,
) -> bool:
    return count_user_open_stafeta_assignments(
        db,
        user.id,
        ignore_assignment_id=ignore_assignment_id,
    ) < stafeta_assignment_limit_for_user(db, user)


def _touch_stafeta_participant_assignment(db: Session, user_id: int, when: Optional[datetime] = None) -> None:
    participant = (
        db.query(models.StafetaParticipant)
        .filter(models.StafetaParticipant.user_id == user_id)
        .first()
    )
    if participant:
        participant.last_assigned_at = when or utcnow_naive()


def _clear_stafeta_current_turn(db: Session, work: models.StafetaWork, *, commit: bool = False) -> None:
    work.current_assignment_id = None
    work.current_holder_user_id = None
    work.updated_at = utcnow_naive()
    if commit:
        db.commit()
        db.refresh(work)


def choose_random_stafeta_recipient(
    db: Session,
    work: models.StafetaWork,
    *,
    exclude_user_ids: Optional[Iterable[int]] = None,
) -> Optional[models.User]:
    excluded = set(exclude_user_ids or [])
    excluded.add(work.creator_id)
    if work.current_holder_user_id:
        excluded.add(work.current_holder_user_id)

    prior_ids = _participant_user_ids(db, work.id)
    fresh_candidates = _eligible_random_stafeta_recipients(db, excluded_ids=excluded | prior_ids)
    if fresh_candidates:
        return fresh_candidates[0][3]
    candidates = _eligible_random_stafeta_recipients(db, excluded_ids=excluded)
    return candidates[0][3] if candidates else None


def _create_assignment(
    db: Session,
    work: models.StafetaWork,
    target: models.User,
    *,
    assigned_by: Optional[models.User],
    source: str,
    status: str,
) -> models.StafetaAssignment:
    assignment = models.StafetaAssignment(
        work_id=work.id,
        user_id=target.id,
        assigned_by_id=assigned_by.id if assigned_by else None,
        source=source,
        status=status,
        due_at=_deadline_for_assignment(work, target.id) if status == "active" else None,
    )
    db.add(assignment)
    db.flush()
    _touch_stafeta_participant_assignment(db, target.id, assignment.created_at or utcnow_naive())
    work.current_assignment_id = assignment.id
    work.current_holder_user_id = target.id
    work.updated_at = utcnow_naive()
    return assignment


def match_stafeta_pool(db: Session) -> list[models.StafetaAssignment]:
    assignments: list[models.StafetaAssignment] = []
    works = (
        db.query(models.StafetaWork)
        .options(joinedload(models.StafetaWork.creator))
        .filter(
            models.StafetaWork.status == "active",
            models.StafetaWork.current_assignment_id.is_(None),
            models.StafetaWork.current_holder_user_id.is_(None),
        )
        .order_by(models.StafetaWork.updated_at.asc(), models.StafetaWork.id.asc())
        .all()
    )
    for work in works:
        target = choose_random_stafeta_recipient(db, work)
        if not target:
            continue
        assignment = _create_assignment(db, work, target, assigned_by=work.creator, source="random", status="active")
        db.commit()
        db.refresh(assignment)
        assignments.append(assignment)
        _notify_assignment(db, work, assignment)
        enqueue_stafeta_turn_timeout_job(db, assignment)
    return assignments


def _notify_assignment(db: Session, work: models.StafetaWork, assignment: models.StafetaAssignment) -> None:
    if assignment.status == "pending":
        create_notification(
            db=db,
            user_id=assignment.user_id,
            notif_type="stafeta_invitation",
            title="Ștafetă primită",
            message=f"Ai primit ștafeta „{work.title}\". O poți accepta sau refuza.",
            link=_stafeta_link(work),
            extra_data={"work_id": work.id, "work_slug": work.slug, "assignment_id": assignment.id},
        )
        return
    create_notification(
        db=db,
        user_id=assignment.user_id,
        notif_type="stafeta_turn_assigned",
        title="Este rândul tău în Ștafeta",
        message=f"Continuă „{work.title}\" în cel mult {work.deadline_days} zile.",
        link=_stafeta_link(work),
        extra_data={"work_id": work.id, "work_slug": work.slug, "assignment_id": assignment.id},
    )


def assign_stafeta_to_random(
    db: Session,
    work: models.StafetaWork,
    *,
    assigned_by: Optional[models.User],
    source: str = "random",
    exclude_user_ids: Optional[Iterable[int]] = None,
) -> tuple[Optional[models.StafetaAssignment], Optional[str]]:
    target = choose_random_stafeta_recipient(db, work, exclude_user_ids=exclude_user_ids)
    if not target:
        _clear_stafeta_current_turn(db, work, commit=True)
        return None, None
    assignment = _create_assignment(db, work, target, assigned_by=assigned_by, source=source, status="active")
    db.commit()
    db.refresh(assignment)
    _notify_assignment(db, work, assignment)
    enqueue_stafeta_turn_timeout_job(db, assignment)
    return assignment, None


def create_stafeta_work(
    db: Session,
    creator: models.User,
    data: schemas.StafetaCreate,
) -> tuple[Optional[models.StafetaWork], Optional[str]]:
    if creator.is_suspended:
        return None, "suspended"

    work = models.StafetaWork(
        creator_id=creator.id,
        title=data.title.strip(),
        slug=_ensure_unique_stafeta_slug(db, _generate_stafeta_slug(data.title)),
        category=data.category,
        status="active",
        deadline_days=data.deadline_days,
        max_characters=data.max_characters,
    )
    db.add(work)
    db.flush()
    segment = models.StafetaSegment(
        work_id=work.id,
        author_id=creator.id,
        content=data.initial_content,
        position=1,
        next_target_mode=data.first_target_mode,
        moderation_status="approved",
        moderated_by=creator.id,
        moderated_at=utcnow_naive(),
    )
    db.add(segment)
    db.flush()

    if data.first_target_mode == "specific":
        target = get_user_by_username(db, data.assigned_username or "")
        if not target:
            db.rollback()
            return None, "user_not_found"
        if target.is_suspended:
            db.rollback()
            return None, "target_suspended"
        if not user_has_stafeta_assignment_capacity(db, target):
            db.rollback()
            return None, "target_at_capacity"
        assignment = _create_assignment(db, work, target, assigned_by=creator, source="specific", status="pending")
        db.commit()
        db.refresh(work)
        _notify_assignment(db, work, assignment)
        return work, None

    db.commit()
    db.refresh(work)
    match_stafeta_pool(db)
    db.refresh(work)
    return work, None


def actor_can_view_stafeta(db: Session, work: models.StafetaWork, actor: Optional[models.User]) -> bool:
    if not actor:
        return False
    if work.creator_id == actor.id or work.current_holder_user_id == actor.id:
        return True
    participant = (
        db.query(models.StafetaAssignment.id)
        .filter(models.StafetaAssignment.work_id == work.id, models.StafetaAssignment.user_id == actor.id)
        .first()
    )
    if participant:
        return True
    return (
        db.query(models.StafetaSegment.id)
        .filter(models.StafetaSegment.work_id == work.id, models.StafetaSegment.author_id == actor.id)
        .first()
        is not None
    )


def list_stafeta_works(
    db: Session,
    user: models.User,
    *,
    filter_value: str = "all",
    limit: int = 50,
    offset: int = 0,
) -> list[models.StafetaWork]:
    assignment_work_ids = db.query(models.StafetaAssignment.work_id).filter(models.StafetaAssignment.user_id == user.id)
    segment_work_ids = db.query(models.StafetaSegment.work_id).filter(models.StafetaSegment.author_id == user.id)
    query = db.query(models.StafetaWork).options(
        joinedload(models.StafetaWork.creator),
        joinedload(models.StafetaWork.current_holder),
        joinedload(models.StafetaWork.published_post),
    )
    if filter_value == "created":
        query = query.filter(models.StafetaWork.creator_id == user.id)
    elif filter_value == "turn":
        query = query.join(models.StafetaAssignment, models.StafetaAssignment.id == models.StafetaWork.current_assignment_id).filter(
            models.StafetaAssignment.user_id == user.id,
            models.StafetaAssignment.status.in_(("pending", "active")),
        )
    elif filter_value == "published":
        query = query.filter(
            models.StafetaWork.status == "published",
            or_(
                models.StafetaWork.creator_id == user.id,
                models.StafetaWork.id.in_(assignment_work_ids),
                models.StafetaWork.id.in_(segment_work_ids),
            ),
        )
    elif filter_value == "mine":
        query = query.filter(
            or_(
                models.StafetaWork.creator_id == user.id,
                models.StafetaWork.id.in_(assignment_work_ids),
                models.StafetaWork.id.in_(segment_work_ids),
            )
        )
    else:
        query = query.filter(
            or_(
                models.StafetaWork.creator_id == user.id,
                models.StafetaWork.id.in_(assignment_work_ids),
                models.StafetaWork.id.in_(segment_work_ids),
            )
        )
    return (
        query.distinct()
        .order_by(models.StafetaWork.updated_at.desc(), models.StafetaWork.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )


def respond_to_stafeta_assignment(
    db: Session,
    assignment: models.StafetaAssignment,
    actor: models.User,
    action: str,
) -> tuple[Optional[models.StafetaAssignment], Optional[str]]:
    if assignment.user_id != actor.id:
        return None, "not_allowed"
    if assignment.status != "pending":
        return None, "not_pending"
    work = assignment.work
    if not work or work.status != "active":
        return None, "work_not_active"
    now = utcnow_naive()
    assignment.responded_at = now
    if action == "accept":
        assignment.status = "active"
        assignment.due_at = _deadline_for_assignment(work, actor.id)
        work.current_assignment_id = assignment.id
        work.current_holder_user_id = actor.id
        work.updated_at = now
        db.commit()
        db.refresh(assignment)
        enqueue_stafeta_turn_timeout_job(db, assignment)
        return assignment, None
    if action == "refuse":
        assignment.status = "refused"
        assignment.completed_at = now
        creator = work.creator or db.query(models.User).filter(models.User.id == work.creator_id).first()
        creator_assignment = None
        if creator and user_has_stafeta_assignment_capacity(db, creator):
            creator_assignment = _create_assignment(db, work, creator, assigned_by=actor, source="return", status="active")
        else:
            _clear_stafeta_current_turn(db, work)
        db.commit()
        db.refresh(assignment)
        create_notification(
            db=db,
            user_id=work.creator_id,
            notif_type="stafeta_refused",
            title="Ștafetă refuzată",
            message=f"{actor.username} a refuzat ștafeta „{work.title}\".",
            link=_stafeta_link(work),
            extra_data={"work_id": work.id, "work_slug": work.slug, "assignment_id": assignment.id},
        )
        if creator_assignment:
            _notify_assignment(db, work, creator_assignment)
        return assignment, None
    return None, "bad_action"


def _has_open_segment_for_assignment(db: Session, assignment_id: int) -> bool:
    return (
        db.query(models.StafetaSegment.id)
        .filter(
            models.StafetaSegment.assignment_id == assignment_id,
            models.StafetaSegment.moderation_status.in_(("pending", "flagged")),
        )
        .first()
        is not None
    )


def _validate_stafeta_destination(
    db: Session,
    work: models.StafetaWork,
    actor: models.User,
    data: schemas.StafetaSend,
) -> Optional[str]:
    if data.target_mode == "creator":
        return None
    if data.target_mode == "random":
        return None
    if data.target_mode == "previous":
        previous_ids = {user.id for user in list_previous_stafeta_participants(db, work, exclude_user_id=actor.id)}
        if data.target_user_id not in previous_ids:
            return "target_not_previous"
        target = db.query(models.User).filter(models.User.id == data.target_user_id).first()
        if target and not user_has_stafeta_assignment_capacity(db, target):
            return "target_at_capacity"
        return None
    if data.target_mode == "specific":
        if data.target_user_id == actor.id:
            return "target_is_current"
        target = db.query(models.User).filter(models.User.id == data.target_user_id).first()
        if not target or target.is_suspended:
            return "target_not_found"
        if not user_has_stafeta_assignment_capacity(db, target):
            return "target_at_capacity"
        return None
    return "bad_target"


def send_stafeta_forward(
    db: Session,
    work: models.StafetaWork,
    actor: models.User,
    data: schemas.StafetaSend,
) -> tuple[Optional[models.StafetaSegment | models.StafetaAssignment], Optional[str]]:
    if work.status != "active":
        return None, "work_not_active"
    assignment = get_current_stafeta_assignment(db, work)
    if not assignment or assignment.user_id != actor.id or assignment.status != "active":
        return None, "not_your_turn"
    if _has_open_segment_for_assignment(db, assignment.id):
        return None, "segment_pending"

    plain = rich_text.rich_text_to_plain_text(data.content)
    if plain:
        if len(plain) > int(work.max_characters or 400):
            return None, "content_too_long"
        destination_error = _validate_stafeta_destination(db, work, actor, data)
        if destination_error:
            return None, destination_error
        segment = models.StafetaSegment(
            work_id=work.id,
            assignment_id=assignment.id,
            author_id=actor.id,
            content=data.content,
            position=_next_segment_position(db, work.id),
            next_target_mode=data.target_mode,
            next_target_user_id=data.target_user_id if data.target_mode in {"previous", "specific"} else None,
            moderation_status="pending",
        )
        db.add(segment)
        db.commit()
        db.refresh(segment)
        enqueue_stafeta_segment_moderation_job(db, segment)
        create_notification(
            db=db,
            user_id=work.creator_id,
            notif_type="stafeta_segment_pending",
            title="Contribuție nouă în Ștafeta",
            message=f"{actor.username} a trimis o continuare pentru „{work.title}\".",
            link=_stafeta_link(work),
            extra_data={"work_id": work.id, "work_slug": work.slug, "segment_id": segment.id},
        )
        return segment, None

    target = choose_random_stafeta_recipient(db, work, exclude_user_ids={actor.id})
    now = utcnow_naive()
    assignment.status = "completed"
    assignment.completed_at = now
    if not target:
        _clear_stafeta_current_turn(db, work)
        db.commit()
        db.refresh(assignment)
        return None, None
    next_assignment = _create_assignment(db, work, target, assigned_by=actor, source="random", status="active")
    db.commit()
    db.refresh(next_assignment)
    _notify_assignment(db, work, next_assignment)
    enqueue_stafeta_turn_timeout_job(db, next_assignment)
    return next_assignment, None


def creator_assign_stafeta_user(
    db: Session,
    work: models.StafetaWork,
    creator: models.User,
    target: models.User,
) -> tuple[Optional[models.StafetaAssignment], Optional[str]]:
    if work.creator_id != creator.id:
        return None, "not_allowed"
    if work.status != "active":
        return None, "work_not_active"
    if target.is_suspended:
        return None, "target_suspended"
    current = get_current_stafeta_assignment(db, work)
    ignore_assignment_id = current.id if current and current.user_id == target.id else None
    if not user_has_stafeta_assignment_capacity(db, target, ignore_assignment_id=ignore_assignment_id):
        return None, "target_at_capacity"
    if current and current.status in {"pending", "active"}:
        current.status = "cancelled"
        current.completed_at = utcnow_naive()
    assignment = _create_assignment(db, work, target, assigned_by=creator, source="specific", status="pending")
    db.commit()
    db.refresh(assignment)
    _notify_assignment(db, work, assignment)
    return assignment, None


def creator_assign_stafeta_random(
    db: Session,
    work: models.StafetaWork,
    creator: models.User,
) -> tuple[Optional[models.StafetaAssignment], Optional[str]]:
    if work.creator_id != creator.id:
        return None, "not_allowed"
    if work.status != "active":
        return None, "work_not_active"
    current = get_current_stafeta_assignment(db, work)
    if current and current.status in {"pending", "active"}:
        current.status = "cancelled"
        current.completed_at = utcnow_naive()
        work.current_assignment_id = None
        work.current_holder_user_id = None
        db.flush()
    return assign_stafeta_to_random(db, work, assigned_by=creator, source="random")


def _assign_after_approved_segment(
    db: Session,
    segment: models.StafetaSegment,
) -> None:
    work = segment.work or get_stafeta_work(db, segment.work_id)
    if not work or work.status != "active":
        return
    assignment = segment.assignment
    if assignment and assignment.status == "active":
        assignment.status = "completed"
        assignment.completed_at = utcnow_naive()

    if segment.next_target_mode == "creator":
        target = work.creator or db.query(models.User).filter(models.User.id == work.creator_id).first()
        if target and user_has_stafeta_assignment_capacity(db, target):
            next_assignment = _create_assignment(db, work, target, assigned_by=segment.author, source="return", status="active")
            db.commit()
            db.refresh(next_assignment)
            _notify_assignment(db, work, next_assignment)
        else:
            _clear_stafeta_current_turn(db, work, commit=True)
        return

    if segment.next_target_mode in {"previous", "specific"} and segment.next_target_user_id:
        target = db.query(models.User).filter(
            models.User.id == segment.next_target_user_id,
            models.User.is_suspended == False,
        ).first()
        if target and user_has_stafeta_assignment_capacity(db, target):
            next_assignment = _create_assignment(db, work, target, assigned_by=segment.author, source="previous", status="active")
            db.commit()
            db.refresh(next_assignment)
            _notify_assignment(db, work, next_assignment)
            enqueue_stafeta_turn_timeout_job(db, next_assignment)
            return

    target = choose_random_stafeta_recipient(db, work, exclude_user_ids={segment.author_id})
    if target:
        next_assignment = _create_assignment(db, work, target, assigned_by=segment.author, source="random", status="active")
        db.commit()
        db.refresh(next_assignment)
        _notify_assignment(db, work, next_assignment)
        enqueue_stafeta_turn_timeout_job(db, next_assignment)
        return

    _clear_stafeta_current_turn(db, work, commit=True)


def apply_stafeta_segment_moderation_result(
    db: Session,
    segment: models.StafetaSegment,
    moderation_result,
    *,
    moderator_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> models.StafetaSegment:
    was_approved = segment.moderation_status == "approved"
    status = getattr(moderation_result, "status", "approved")
    segment.moderation_status = getattr(status, "value", status)
    segment.toxicity_score = getattr(moderation_result, "toxicity_score", None)
    segment.moderation_reason = reason or getattr(moderation_result, "reason", None)
    if moderator_id is not None:
        segment.moderated_by = moderator_id
        segment.moderated_at = utcnow_naive()
    db.commit()
    db.refresh(segment)
    if segment.moderation_status == "approved" and not was_approved:
        _assign_after_approved_segment(db, segment)
    elif segment.moderation_status in {"flagged", "rejected"}:
        title = "Contribuție în revizie" if segment.moderation_status == "flagged" else "Contribuție respinsă"
        create_notification(
            db=db,
            user_id=segment.author_id,
            notif_type=f"stafeta_segment_{segment.moderation_status}",
            title=title,
            message=segment.moderation_reason,
            link=_stafeta_link(segment.work) if segment.work else None,
            extra_data={"work_id": segment.work_id, "segment_id": segment.id},
        )
    return segment


def process_stafeta_turn_timeout(
    db: Session,
    assignment: models.StafetaAssignment,
) -> tuple[Optional[models.StafetaAssignment], Optional[str]]:
    work = assignment.work
    if not work or work.status != "active":
        return None, "work_not_active"
    if assignment.status != "active":
        return assignment, None
    if not assignment.due_at or assignment.due_at > utcnow_naive():
        return assignment, None
    if (
        db.query(models.StafetaSegment.id)
        .filter(models.StafetaSegment.assignment_id == assignment.id)
        .first()
    ):
        return assignment, None
    assignment.status = "expired"
    assignment.completed_at = utcnow_naive()
    target = choose_random_stafeta_recipient(db, work, exclude_user_ids={assignment.user_id})
    if not target:
        _clear_stafeta_current_turn(db, work)
        db.commit()
        db.refresh(assignment)
        create_notification(
            db=db,
            user_id=assignment.user_id,
            notif_type="stafeta_turn_expired",
            title="Ștafeta a mers mai departe",
            message=f"Termenul pentru „{work.title}\" a expirat.",
            link=_stafeta_link(work),
            extra_data={"work_id": work.id, "work_slug": work.slug, "assignment_id": assignment.id},
        )
        return None, None
    next_assignment = _create_assignment(db, work, target, assigned_by=assignment.user, source="timeout", status="active")
    db.commit()
    db.refresh(next_assignment)
    _notify_assignment(db, work, next_assignment)
    enqueue_stafeta_turn_timeout_job(db, next_assignment)
    create_notification(
        db=db,
        user_id=assignment.user_id,
        notif_type="stafeta_turn_expired",
        title="Ștafeta a mers mai departe",
        message=f"Termenul pentru „{work.title}\" a expirat.",
        link=_stafeta_link(work),
        extra_data={"work_id": work.id, "work_slug": work.slug, "assignment_id": assignment.id},
    )
    return next_assignment, None


def _published_stafeta_content(segments: list[models.StafetaSegment]) -> str:
    parts = []
    for segment in segments:
        author = segment.author.username if segment.author else "Autor"
        parts.append(f"<p><strong>{escape(author)}</strong></p>\n{segment.content}")
    return "\n\n".join(parts)


def publish_stafeta_work(
    db: Session,
    work: models.StafetaWork,
    creator: models.User,
) -> tuple[Optional[models.Post], Optional[str]]:
    if work.creator_id != creator.id:
        return None, "not_allowed"
    if work.status != "active":
        return None, "work_not_active"
    segments = (
        db.query(models.StafetaSegment)
        .options(joinedload(models.StafetaSegment.author))
        .filter(
            models.StafetaSegment.work_id == work.id,
            models.StafetaSegment.moderation_status == "approved",
        )
        .order_by(models.StafetaSegment.position.asc(), models.StafetaSegment.id.asc())
        .all()
    )
    if not segments:
        return None, "no_content"
    content = _published_stafeta_content(segments)
    try:
        _validate_post_content_limit(work.category, content)
        post_data = schemas.PostCreate(
            title=work.title,
            content=content,
            category=work.category,
            explanatory_note="Text creat prin Ștafeta.",
            ai_critic=False,
        )
    except (ValidationError, ValueError):
        return None, "content_too_long"
    post = create_user_post(db, post_data, creator.id, category=work.category)
    work.status = "published"
    work.published_post_id = post.id
    work.published_at = utcnow_naive()
    work.current_assignment_id = None
    work.current_holder_user_id = None
    db.query(models.StafetaAssignment).filter(
        models.StafetaAssignment.work_id == work.id,
        models.StafetaAssignment.status.in_(("pending", "active")),
    ).update({"status": "cancelled", "completed_at": utcnow_naive()})
    db.commit()
    db.refresh(post)
    contributors = {
        segment.author_id for segment in segments if segment.author_id and segment.author_id != work.creator_id
    }
    for user_id in contributors:
        create_notification(
            db=db,
            user_id=user_id,
            notif_type="stafeta_published",
            title="Ștafetă publicată",
            message=f"„{work.title}\" a fost închisă și trimisă la publicare.",
            link=f"/{post.slug}",
            extra_data={"work_id": work.id, "work_slug": work.slug, "post_id": post.id},
        )
    return post, None


def cancel_stafeta_work(
    db: Session,
    work: models.StafetaWork,
    actor: models.User,
) -> tuple[bool, Optional[str]]:
    if work.creator_id != actor.id:
        return False, "not_allowed"
    if work.status == "published":
        return False, "already_published"
    work.status = "cancelled"
    work.current_assignment_id = None
    work.current_holder_user_id = None
    db.query(models.StafetaAssignment).filter(
        models.StafetaAssignment.work_id == work.id,
        models.StafetaAssignment.status.in_(("pending", "active")),
    ).update({"status": "cancelled", "completed_at": utcnow_naive()})
    db.commit()
    return True, None


def count_stafeta_segments(db: Session, work_id: int, *, approved_only: bool = True) -> int:
    query = db.query(func.count(models.StafetaSegment.id)).filter(models.StafetaSegment.work_id == work_id)
    if approved_only:
        query = query.filter(models.StafetaSegment.moderation_status == "approved")
    return query.scalar() or 0


def count_stafeta_participants(db: Session, work_id: int) -> int:
    ids = _participant_user_ids(db, work_id)
    return len(ids)


def list_stafeta_segments_for_moderation(
    db: Session,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[models.StafetaSegment]:
    query = db.query(models.StafetaSegment).options(
        joinedload(models.StafetaSegment.author),
        joinedload(models.StafetaSegment.work),
    )
    if status_filter:
        query = query.filter(models.StafetaSegment.moderation_status == status_filter)
    return (
        query.order_by(models.StafetaSegment.created_at.desc(), models.StafetaSegment.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
