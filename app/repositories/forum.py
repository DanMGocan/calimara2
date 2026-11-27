from ._shared import *
from .economy import award_content_approved
from .mentions import notify_mentions_for_forum_reply, notify_mentions_for_forum_thread
from .notifications import create_notification
from .slugs import generate_slug
from .users import get_user_by_id

DEFAULT_FORUM_SECTIONS = (
    {
        "slug": "anunturi",
        "name": "Anunțuri",
        "description": "Noutăți și anunțuri de la echipa Călimara.",
        "staff_only": True,
        "is_featured": True,
    },
    {"slug": "general", "name": "Discuții generale", "description": "Întrebări și conversații libere între autori."},
    {"slug": "poezie", "name": "Poezie", "description": "Despre scrisul și cititul poeziei."},
    {"slug": "proza_scurta", "name": "Proză scurtă", "description": "Despre proză scurtă: tehnică, lecturi, ateliere."},
)
# Slugs of the sections every install starts with (kept for older imports).
FORUM_SECTIONS = tuple(item["slug"] for item in DEFAULT_FORUM_SECTIONS)
PUBLIC_FORUM_STATUSES = ("approved", "pending", "flagged")
FORUM_THREAD_SORTS = ("activity", "newest", "replies")


class ForumSectionError(ValueError):
    """Raised when a thread cannot be created in the requested section."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


# ===================================
# SECTIONS
# ===================================

def ensure_default_forum_sections(db: Session) -> None:
    """Seed the default sections when the table is empty (fresh installs and test databases)."""
    if db.query(models.ForumSection.id).first() is not None:
        return
    for position, item in enumerate(DEFAULT_FORUM_SECTIONS):
        db.add(models.ForumSection(position=position, **item))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def list_forum_sections(db: Session, include_archived: bool = True) -> List[models.ForumSection]:
    ensure_default_forum_sections(db)
    query = db.query(models.ForumSection)
    if not include_archived:
        query = query.filter(models.ForumSection.is_archived == False)
    return query.order_by(models.ForumSection.position.asc(), models.ForumSection.id.asc()).all()


def get_forum_section_by_slug(db: Session, slug: Optional[str]) -> Optional[models.ForumSection]:
    if not slug:
        return None
    ensure_default_forum_sections(db)
    return db.query(models.ForumSection).filter(models.ForumSection.slug == slug).first()


def get_forum_section(db: Session, section_id: int) -> Optional[models.ForumSection]:
    return db.query(models.ForumSection).filter(models.ForumSection.id == section_id).first()


def is_forum_section(db: Session, slug: Optional[str]) -> bool:
    return get_forum_section_by_slug(db, slug) is not None


def forum_section_labels(db: Session) -> Dict[str, str]:
    return {section.slug: section.name for section in list_forum_sections(db)}


def section_posting_error(
    user: Optional[models.User], section: Optional[models.ForumSection], *, reply: bool = False
) -> Optional[str]:
    """Why `user` may not start a thread (or reply, when `reply=True`) in `section`, or None."""
    if section is None:
        return None if reply else "invalid_section"
    if user is not None and can_moderate_forum(user):
        return None
    if section.is_archived:
        return "archived"
    if section.staff_only and not reply:
        return "staff_only"
    return None


def _unique_section_slug(db: Session, base_slug: str, exclude_id: Optional[int] = None) -> str:
    base = (base_slug or "sectiune")[:56]
    slug = base
    counter = 2
    while _section_slug_taken(db, slug, exclude_id=exclude_id):
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def _section_slug_taken(db: Session, slug: str, exclude_id: Optional[int] = None) -> bool:
    query = db.query(models.ForumSection.id).filter(models.ForumSection.slug == slug)
    if exclude_id is not None:
        query = query.filter(models.ForumSection.id != exclude_id)
    return query.first() is not None


def create_forum_section(
    db: Session, actor: models.User, data: schemas.ForumSectionCreate
) -> tuple[Optional[models.ForumSection], Optional[str]]:
    ensure_default_forum_sections(db)
    if data.slug:
        if _section_slug_taken(db, data.slug):
            return None, "slug_taken"
        slug = data.slug
    else:
        slug = _unique_section_slug(db, generate_slug(data.name, fallback="sectiune"))
    max_position = db.query(func.max(models.ForumSection.position)).scalar()
    section = models.ForumSection(
        slug=slug,
        name=data.name,
        description=data.description,
        position=(max_position + 1) if max_position is not None else 0,
        staff_only=data.staff_only,
        is_featured=data.is_featured,
        is_archived=data.is_archived,
        created_by=actor.id,
    )
    db.add(section)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None, "slug_taken"
    db.refresh(section)
    return section, None


def update_forum_section(
    db: Session, section: models.ForumSection, data: schemas.ForumSectionUpdate
) -> tuple[Optional[models.ForumSection], Optional[str]]:
    old_slug = section.slug
    if data.slug and data.slug != old_slug:
        if _section_slug_taken(db, data.slug, exclude_id=section.id):
            return None, "slug_taken"
        section.slug = data.slug
        db.query(models.ForumThread).filter(models.ForumThread.section == old_slug).update(
            {models.ForumThread.section: data.slug}, synchronize_session=False
        )
    if data.name is not None:
        section.name = data.name
    if data.description is not None:
        section.description = data.description or None
    for field in ("staff_only", "is_featured", "is_archived"):
        value = getattr(data, field)
        if value is not None:
            setattr(section, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None, "slug_taken"
    db.refresh(section)
    return section, None


def reorder_forum_sections(db: Session, section_ids: List[int]) -> List[models.ForumSection]:
    """Put the given sections first, in that order; sections not listed keep their relative order after them."""
    sections = list_forum_sections(db)
    by_id = {section.id: section for section in sections}
    ordered = []
    for section_id in section_ids:
        section = by_id.pop(section_id, None)
        if section is not None:
            ordered.append(section)
    ordered.extend(section for section in sections if section.id in by_id)
    for position, section in enumerate(ordered):
        section.position = position
    db.commit()
    return list_forum_sections(db)


def count_threads_in_section(db: Session, slug: str) -> int:
    return db.query(func.count(models.ForumThread.id)).filter(models.ForumThread.section == slug).scalar() or 0


def delete_forum_section(
    db: Session, section: models.ForumSection, move_to: Optional[models.ForumSection] = None
) -> tuple[int, Optional[str]]:
    """Delete a section. A non-empty section needs `move_to`, which receives its threads.

    Returns (moved_thread_count, error)."""
    if (db.query(func.count(models.ForumSection.id)).scalar() or 0) <= 1:
        return 0, "last_section"
    if move_to is not None and move_to.id == section.id:
        return 0, "same_section"
    thread_count = count_threads_in_section(db, section.slug)
    if thread_count and move_to is None:
        return 0, "not_empty"
    if thread_count:
        db.query(models.ForumThread).filter(models.ForumThread.section == section.slug).update(
            {models.ForumThread.section: move_to.slug}, synchronize_session=False
        )
    db.delete(section)
    db.commit()
    return thread_count, None


def _public_thread_condition():
    return and_(
        models.ForumThread.moderation_status.in_(PUBLIC_FORUM_STATUSES),
        not_human_rejected_condition("forum_thread", models.ForumThread.id),
    )


def forum_section_stats(db: Session, slugs: List[str]) -> Dict[str, Dict[str, Any]]:
    """Public thread/reply counts and the most recently active thread for each section slug."""
    stats: Dict[str, Dict[str, Any]] = {slug: {"thread_count": 0, "reply_count": 0, "last_thread": None} for slug in slugs}
    if not slugs:
        return stats
    thread_rows = (
        db.query(models.ForumThread.section, func.count(models.ForumThread.id))
        .filter(models.ForumThread.section.in_(slugs), _public_thread_condition())
        .group_by(models.ForumThread.section)
        .all()
    )
    for slug, count in thread_rows:
        stats[slug]["thread_count"] = int(count or 0)
    reply_rows = (
        db.query(models.ForumThread.section, func.count(models.ForumReply.id))
        .join(models.ForumThread, models.ForumReply.thread_id == models.ForumThread.id)
        .filter(
            models.ForumThread.section.in_(slugs),
            _public_thread_condition(),
            models.ForumReply.moderation_status.in_(PUBLIC_FORUM_STATUSES),
            not_human_rejected_condition("forum_reply", models.ForumReply.id),
        )
        .group_by(models.ForumThread.section)
        .all()
    )
    for slug, count in reply_rows:
        stats[slug]["reply_count"] = int(count or 0)
    for slug in slugs:
        if not stats[slug]["thread_count"]:
            continue
        stats[slug]["last_thread"] = (
            db.query(models.ForumThread)
            .options(joinedload(models.ForumThread.author))
            .filter(models.ForumThread.section == slug, _public_thread_condition())
            .order_by(models.ForumThread.last_activity_at.desc(), models.ForumThread.id.desc())
            .first()
        )
    return stats


def forum_thread_reply_stats(db: Session, thread_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Public reply count and latest public reply per thread, in two queries for the whole list."""
    stats: Dict[int, Dict[str, Any]] = {thread_id: {"reply_count": 0, "latest_reply": None} for thread_id in thread_ids}
    if not thread_ids:
        return stats
    public_reply = and_(
        models.ForumReply.thread_id.in_(thread_ids),
        models.ForumReply.moderation_status.in_(PUBLIC_FORUM_STATUSES),
        not_human_rejected_condition("forum_reply", models.ForumReply.id),
    )
    rows = (
        db.query(models.ForumReply.thread_id, func.count(models.ForumReply.id), func.max(models.ForumReply.id))
        .filter(public_reply)
        .group_by(models.ForumReply.thread_id)
        .all()
    )
    latest_ids = {}
    for thread_id, count, latest_id in rows:
        stats[thread_id]["reply_count"] = int(count or 0)
        if latest_id is not None:
            latest_ids[latest_id] = thread_id
    if latest_ids:
        replies = (
            db.query(models.ForumReply)
            .options(joinedload(models.ForumReply.author))
            .filter(models.ForumReply.id.in_(list(latest_ids)))
            .all()
        )
        for reply in replies:
            stats[latest_ids[reply.id]]["latest_reply"] = reply
    return stats


def latest_public_forum_reply(db: Session, thread_id: int) -> Optional[models.ForumReply]:
    return (
        db.query(models.ForumReply)
        .options(joinedload(models.ForumReply.author))
        .filter(
            models.ForumReply.thread_id == thread_id,
            models.ForumReply.moderation_status.in_(PUBLIC_FORUM_STATUSES),
            not_human_rejected_condition("forum_reply", models.ForumReply.id),
        )
        .order_by(models.ForumReply.created_at.desc(), models.ForumReply.id.desc())
        .first()
    )


# ===================================
# THREADS & REPLIES
# ===================================

def count_approved_forum_contributions(db: Session, user_id: int) -> int:
    thread_count = db.query(func.count(models.ForumThread.id)).filter(
        models.ForumThread.author_id == user_id,
        models.ForumThread.moderation_status == "approved",
    ).scalar() or 0
    reply_count = db.query(func.count(models.ForumReply.id)).filter(
        models.ForumReply.author_id == user_id,
        models.ForumReply.moderation_status == "approved",
    ).scalar() or 0
    return int(thread_count) + int(reply_count)

def _forum_status_value(moderation_result) -> str:
    status = getattr(moderation_result, "status", "approved")
    return getattr(status, "value", status)

def _ensure_unique_forum_slug(db: Session, base_slug: str) -> str:
    normalized = base_slug or "discutie"
    slug = normalized
    counter = 1
    while db.query(models.ForumThread).filter(models.ForumThread.slug == slug).first():
        slug = f"{normalized}-{counter}"
        counter += 1
    return slug

def get_forum_thread(db: Session, thread_id: int) -> Optional[models.ForumThread]:
    return (
        db.query(models.ForumThread)
        .options(joinedload(models.ForumThread.author))
        .filter(models.ForumThread.id == thread_id)
        .first()
    )

def get_forum_thread_by_slug(db: Session, slug: str) -> Optional[models.ForumThread]:
    return (
        db.query(models.ForumThread)
        .options(
            joinedload(models.ForumThread.author),
            joinedload(models.ForumThread.replies).joinedload(models.ForumReply.author),
        )
        .filter(models.ForumThread.slug == slug)
        .first()
    )

def can_view_forum_thread(user: Optional[models.User], thread: models.ForumThread, db: Optional[Session] = None) -> bool:
    if thread.moderation_status == "rejected":
        return False
    if db is not None and content_has_human_rejection(db, "forum_thread", thread.id):
        return False
    return (
        thread.moderation_status in PUBLIC_FORUM_STATUSES
        or bool(user and thread.author_id == user.id)
        or bool(user and user.is_admin)
        or bool(user and user.is_moderator)
    )

def can_moderate_forum(user: models.User) -> bool:
    return user.is_admin or user.is_moderator

def _public_threads_query(db: Session, section: Optional[str] = None, q: Optional[str] = None, pinned: Optional[bool] = None):
    query = db.query(models.ForumThread).filter(_public_thread_condition())
    if section:
        query = query.filter(models.ForumThread.section == section)
    if pinned is not None:
        query = query.filter(models.ForumThread.is_pinned == pinned)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.ForumThread.title.ilike(pattern),
                models.ForumThread.content.ilike(pattern),
            )
        )
    return query


def list_forum_threads(
    db: Session,
    section: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    pinned: Optional[bool] = None,
    sort: str = "activity",
    pin_first: bool = True,
) -> List[models.ForumThread]:
    query = _public_threads_query(db, section=section, q=q, pinned=pinned).options(joinedload(models.ForumThread.author))
    if sort == "newest":
        ordering = (models.ForumThread.created_at.desc(), models.ForumThread.id.desc())
    elif sort == "replies":
        ordering = (
            models.ForumThread.approved_reply_count.desc(),
            models.ForumThread.last_activity_at.desc(),
            models.ForumThread.id.desc(),
        )
    else:
        ordering = (models.ForumThread.last_activity_at.desc(), models.ForumThread.id.desc())
    if pinned is None and pin_first:
        ordering = (models.ForumThread.is_pinned.desc(),) + ordering
    elif pinned:
        ordering = (models.ForumThread.pinned_at.desc(),) + ordering
    return (
        query.order_by(*ordering)
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )


def count_forum_threads(
    db: Session, section: Optional[str] = None, q: Optional[str] = None, pinned: Optional[bool] = None
) -> int:
    return _public_threads_query(db, section=section, q=q, pinned=pinned).with_entities(func.count(models.ForumThread.id)).scalar() or 0


def create_forum_thread(
    db: Session, author: models.User, data: schemas.ForumThreadCreate
) -> models.ForumThread:
    section = get_forum_section_by_slug(db, data.section)
    error = section_posting_error(author, section)
    if error:
        raise ForumSectionError(error)
    base_slug = generate_slug(data.title.strip(), fallback="discutie")
    thread = models.ForumThread(
        author_id=author.id,
        section=data.section,
        title=data.title.strip(),
        slug=_ensure_unique_forum_slug(db, base_slug),
        content=data.content.strip(),
        moderation_status="pending",
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread

def list_forum_replies_for_thread(
    db: Session, thread_id: int, viewer: Optional[models.User]
) -> List[models.ForumReply]:
    query = (
        db.query(models.ForumReply)
        .options(joinedload(models.ForumReply.author))
        .filter(
            models.ForumReply.thread_id == thread_id,
            models.ForumReply.moderation_status != "rejected",
            not_human_rejected_condition("forum_reply", models.ForumReply.id),
        )
    )
    if viewer is None:
        query = query.filter(models.ForumReply.moderation_status.in_(PUBLIC_FORUM_STATUSES))
    elif not can_moderate_forum(viewer):
        query = query.filter(
            or_(
                models.ForumReply.moderation_status.in_(PUBLIC_FORUM_STATUSES),
                models.ForumReply.author_id == viewer.id,
            )
        )
    return query.order_by(models.ForumReply.created_at.asc(), models.ForumReply.id.asc()).all()

def create_forum_reply(
    db: Session,
    author: models.User,
    thread: models.ForumThread,
    data: schemas.ForumReplyCreate,
) -> tuple[Optional[models.ForumReply], Optional[str]]:
    if not can_view_forum_thread(author, thread, db=db):
        return None, "not_found"
    if thread.moderation_status != "approved":
        return None, "thread_not_approved"
    if thread.is_locked and not can_moderate_forum(author):
        return None, "locked"
    if section_posting_error(author, get_forum_section_by_slug(db, thread.section), reply=True):
        return None, "archived"
    reply = models.ForumReply(
        thread_id=thread.id,
        author_id=author.id,
        content=data.content.strip(),
        moderation_status="pending",
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply, None

def _notify_forum_reply_approved(db: Session, reply: models.ForumReply) -> None:
    thread = reply.thread or get_forum_thread(db, reply.thread_id)
    if not thread or thread.author_id == reply.author_id:
        return
    author = reply.author or get_user_by_id(db, reply.author_id)
    create_notification(
        db=db,
        user_id=thread.author_id,
        notif_type="forum_reply",
        title="Răspuns nou în discuția ta",
        message=f"{author.username if author else 'Un utilizator'} a răspuns în „{thread.title}\".",
        link=f"/discutii/{thread.slug}",
        extra_data={"thread_id": thread.id, "reply_id": reply.id, "thread_slug": thread.slug},
    )

def apply_forum_thread_moderation_result(db: Session, thread: models.ForumThread, moderation_result) -> models.ForumThread:
    was_approved = thread.moderation_status == "approved"
    thread.moderation_status = _forum_status_value(moderation_result)
    thread.toxicity_score = getattr(moderation_result, "toxicity_score", None)
    thread.moderation_reason = getattr(moderation_result, "reason", None)
    if thread.moderation_status == "approved":
        thread.last_activity_at = func.now()
    db.commit()
    db.refresh(thread)
    if thread.moderation_status == "approved" and not was_approved:
        award_content_approved(db, "forum_thread", thread)
        notify_mentions_for_forum_thread(db, thread)
    return thread

def apply_forum_reply_moderation_result(db: Session, reply: models.ForumReply, moderation_result) -> models.ForumReply:
    was_approved = reply.moderation_status == "approved"
    reply.moderation_status = _forum_status_value(moderation_result)
    reply.toxicity_score = getattr(moderation_result, "toxicity_score", None)
    reply.moderation_reason = getattr(moderation_result, "reason", None)
    if reply.moderation_status == "approved":
        thread = reply.thread or get_forum_thread(db, reply.thread_id)
        if thread:
            thread.last_activity_at = func.now()
    db.commit()
    db.refresh(reply)
    if reply.moderation_status == "approved" and not was_approved:
        award_content_approved(db, "forum_reply", reply)
        _notify_forum_reply_approved(db, reply)
        notify_mentions_for_forum_reply(db, reply)
    return reply

def delete_forum_thread(db: Session, actor: models.User, thread: models.ForumThread) -> bool:
    if thread.author_id != actor.id and not can_moderate_forum(actor):
        return False
    db.delete(thread)
    db.commit()
    return True

def get_forum_reply(db: Session, reply_id: int) -> Optional[models.ForumReply]:
    return (
        db.query(models.ForumReply)
        .options(
            joinedload(models.ForumReply.author),
            joinedload(models.ForumReply.thread),
        )
        .filter(models.ForumReply.id == reply_id)
        .first()
    )

def delete_forum_reply(db: Session, actor: models.User, reply: models.ForumReply) -> bool:
    if reply.author_id != actor.id and not can_moderate_forum(actor):
        return False
    db.delete(reply)
    db.commit()
    return True

def _apply_thread_state(
    actor: models.User, thread: models.ForumThread, action: str, target: Optional[models.ForumSection] = None
) -> Optional[str]:
    now = utcnow_naive()
    if action == "lock":
        if not thread.is_locked:
            thread.is_locked = True
            thread.locked_at = now
            thread.locked_by = actor.id
    elif action == "unlock":
        thread.is_locked = False
        thread.locked_at = None
        thread.locked_by = None
    elif action == "pin":
        if not thread.is_pinned:
            thread.is_pinned = True
            thread.pinned_at = now
            thread.pinned_by = actor.id
    elif action == "unpin":
        thread.is_pinned = False
        thread.pinned_at = None
        thread.pinned_by = None
    elif action == "move":
        if target is None:
            return "invalid_section"
        thread.section = target.slug
    else:
        return "bad_action"
    return None


def update_forum_thread_state(
    db: Session, actor: models.User, thread: models.ForumThread, action: str, section: Optional[str] = None
) -> tuple[Optional[models.ForumThread], Optional[str]]:
    if not can_moderate_forum(actor):
        return None, "not_allowed"
    target = get_forum_section_by_slug(db, section) if action == "move" else None
    error = _apply_thread_state(actor, thread, action, target)
    if error:
        return None, error
    db.commit()
    db.refresh(thread)
    return thread, None


def update_forum_reply_state(
    db: Session, actor: models.User, reply: models.ForumReply, action: str
) -> tuple[Optional[models.ForumReply], Optional[str]]:
    if not can_moderate_forum(actor):
        return None, "not_allowed"
    if action == "pin":
        if reply.moderation_status != "approved":
            return None, "not_approved"
        if not reply.is_pinned:
            reply.is_pinned = True
            reply.pinned_at = utcnow_naive()
            reply.pinned_by = actor.id
    elif action == "unpin":
        reply.is_pinned = False
        reply.pinned_at = None
        reply.pinned_by = None
    else:
        return None, "bad_action"
    db.commit()
    db.refresh(reply)
    return reply, None


def bulk_update_forum_threads(
    db: Session, actor: models.User, thread_ids: List[int], action: str, section: Optional[str] = None
) -> tuple[int, Optional[str]]:
    """Apply one moderation action to many threads. Returns (affected_count, error)."""
    if not can_moderate_forum(actor):
        return 0, "not_allowed"
    target = None
    if action == "move":
        target = get_forum_section_by_slug(db, section)
        if target is None:
            return 0, "invalid_section"
    threads = db.query(models.ForumThread).filter(models.ForumThread.id.in_(set(thread_ids))).all()
    if action == "delete":
        for thread in threads:
            db.delete(thread)
        db.commit()
        return len(threads), None
    for thread in threads:
        error = _apply_thread_state(actor, thread, action, target)
        if error:
            db.rollback()
            return 0, error
    db.commit()
    return len(threads), None


def list_forum_threads_for_admin(
    db: Session,
    section: Optional[str] = None,
    status: Optional[str] = None,
    pinned: Optional[bool] = None,
    locked: Optional[bool] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[models.ForumThread], int]:
    query = db.query(models.ForumThread)
    if section:
        query = query.filter(models.ForumThread.section == section)
    if status:
        query = query.filter(models.ForumThread.moderation_status == status)
    if pinned is not None:
        query = query.filter(models.ForumThread.is_pinned == pinned)
    if locked is not None:
        query = query.filter(models.ForumThread.is_locked == locked)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(models.ForumThread.title.ilike(pattern), models.ForumThread.content.ilike(pattern)))
    total = query.with_entities(func.count(models.ForumThread.id)).scalar() or 0
    items = (
        query.options(joinedload(models.ForumThread.author))
        .order_by(models.ForumThread.is_pinned.desc(), models.ForumThread.last_activity_at.desc(), models.ForumThread.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return items, int(total)


# ===================================
# READ TRACKING
# ===================================

def mark_forum_thread_read(db: Session, user: Optional[models.User], thread: models.ForumThread) -> None:
    """Record that `user` opened the thread. A first visit by anyone but the author counts as a view."""
    if user is None or not getattr(user, "id", None):
        return
    # Store the activity mark the reader has seen (not the wall clock), so "new replies"
    # is a plain comparison against the thread's own last_activity_at.
    seen_activity = thread.last_activity_at or func.now()
    read = (
        db.query(models.ForumThreadRead)
        .filter(models.ForumThreadRead.thread_id == thread.id, models.ForumThreadRead.user_id == user.id)
        .first()
    )
    if read is not None:
        read.last_read_at = seen_activity
        db.commit()
        return
    db.add(models.ForumThreadRead(thread_id=thread.id, user_id=user.id, last_read_at=seen_activity))
    if thread.author_id != user.id:
        db.query(models.ForumThread).filter(models.ForumThread.id == thread.id).update(
            # Keep updated_at as is: a view is not an edit (the column has onupdate=now()).
            {
                models.ForumThread.view_count: models.ForumThread.view_count + 1,
                models.ForumThread.updated_at: models.ForumThread.updated_at,
            },
            synchronize_session=False,
        )
    try:
        db.commit()
    except IntegrityError:
        # A concurrent first visit already recorded it.
        db.rollback()
    db.refresh(thread)


def forum_threads_with_new_replies(db: Session, user: Optional[models.User], thread_ids: List[int]) -> set:
    """Threads the user opened before that have had activity since the activity mark they last saw."""
    if user is None or not getattr(user, "id", None) or not thread_ids:
        return set()
    rows = (
        db.query(models.ForumThreadRead.thread_id)
        .join(models.ForumThread, models.ForumThread.id == models.ForumThreadRead.thread_id)
        .filter(
            models.ForumThreadRead.user_id == user.id,
            models.ForumThreadRead.thread_id.in_(thread_ids),
            models.ForumThread.last_activity_at > models.ForumThreadRead.last_read_at,
        )
        .all()
    )
    return {row[0] for row in rows}


def get_forum_threads_for_moderation(
    db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50
) -> List[models.ForumThread]:
    query = db.query(models.ForumThread).options(joinedload(models.ForumThread.author))
    if status_filter:
        query = query.filter(models.ForumThread.moderation_status == status_filter)
    return query.order_by(models.ForumThread.created_at.desc()).offset(skip).limit(limit).all()

def get_forum_replies_for_moderation(
    db: Session, status_filter: Optional[str] = None, skip: int = 0, limit: int = 50
) -> List[models.ForumReply]:
    query = db.query(models.ForumReply).options(
        joinedload(models.ForumReply.author),
        joinedload(models.ForumReply.thread),
    )
    if status_filter:
        query = query.filter(models.ForumReply.moderation_status == status_filter)
    return query.order_by(models.ForumReply.created_at.desc()).offset(skip).limit(limit).all()


# ===================================
# MESSAGE CRUD FUNCTIONS
# ===================================
