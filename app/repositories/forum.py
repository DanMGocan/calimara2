from ._shared import *
from .economy import award_content_approved
from .mentions import notify_mentions_for_forum_reply, notify_mentions_for_forum_thread
from .notifications import create_notification
from .slugs import generate_slug
from .users import get_user_by_id

FORUM_SECTIONS = ("general", "poezie", "proza_scurta", "feedback", "anunturi")

def is_forum_section(section: str) -> bool:
    return section in FORUM_SECTIONS

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

def can_view_forum_thread(user: models.User, thread: models.ForumThread) -> bool:
    return (
        thread.moderation_status == "approved"
        or thread.author_id == user.id
        or user.is_admin
        or user.is_moderator
    )

def can_moderate_forum(user: models.User) -> bool:
    return user.is_admin or user.is_moderator

def list_forum_threads(
    db: Session,
    section: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
) -> List[models.ForumThread]:
    query = (
        db.query(models.ForumThread)
        .options(joinedload(models.ForumThread.author))
        .filter(models.ForumThread.moderation_status == "approved")
    )
    if section and is_forum_section(section):
        query = query.filter(models.ForumThread.section == section)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(
            or_(
                models.ForumThread.title.ilike(pattern),
                models.ForumThread.content.ilike(pattern),
            )
        )
    return (
        query.order_by(
            models.ForumThread.is_pinned.desc(),
            models.ForumThread.last_activity_at.desc(),
            models.ForumThread.id.desc(),
        )
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )

def create_forum_thread(
    db: Session, author: models.User, data: schemas.ForumThreadCreate
) -> models.ForumThread:
    if not is_forum_section(data.section):
        raise ValueError("invalid_section")
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
    db: Session, thread_id: int, viewer: models.User
) -> List[models.ForumReply]:
    query = (
        db.query(models.ForumReply)
        .options(joinedload(models.ForumReply.author))
        .filter(models.ForumReply.thread_id == thread_id)
    )
    if not can_moderate_forum(viewer):
        query = query.filter(
            or_(
                models.ForumReply.moderation_status == "approved",
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
    if not can_view_forum_thread(author, thread):
        return None, "not_found"
    if thread.moderation_status != "approved":
        return None, "thread_not_approved"
    if thread.is_locked and not can_moderate_forum(author):
        return None, "locked"
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

def update_forum_thread_state(
    db: Session, actor: models.User, thread: models.ForumThread, action: str
) -> tuple[Optional[models.ForumThread], Optional[str]]:
    if not can_moderate_forum(actor):
        return None, "not_allowed"
    if action == "lock":
        thread.is_locked = True
    elif action == "unlock":
        thread.is_locked = False
    elif action == "pin":
        thread.is_pinned = True
    elif action == "unpin":
        thread.is_pinned = False
    else:
        return None, "bad_action"
    db.commit()
    db.refresh(thread)
    return thread, None

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
