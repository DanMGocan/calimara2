import logging
import math
from typing import Dict, Iterable, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import ai_queue, auth, crud, models, profile_media, rich_text, schemas
from ..database import get_db
from ..utils import get_avatar_url

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["forum"])

THREADS_PER_PAGE = 25
REPLIES_PER_PAGE = 20

SECTION_ERROR_RESPONSES = {
    "invalid_section": (400, "Secțiune invalidă"),
    "staff_only": (403, "Doar echipa Călimara poate deschide discuții în această secțiune"),
    "archived": (403, "Secțiunea este arhivată"),
}


def _profile_photo_url(user: models.User) -> Optional[str]:
    if getattr(user, "is_premium", False) and getattr(user, "profile_photo_storage_key", None):
        return profile_media.public_media_url(user.username, "profil")
    return None


def _author_ref(user: Optional[models.User]) -> Optional[dict]:
    """Lightweight author payload for lists (no per-user count queries)."""
    if not user:
        return None
    profile_photo_url = _profile_photo_url(user)
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "avatar_url": profile_photo_url or get_avatar_url(user, size=96),
        "profile_photo_url": profile_photo_url,
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
    }


def _author_payload(db: Session, user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    return {
        **_author_ref(user),
        "gologani_balance": getattr(user, "gologani_balance", 0) or 0,
        "forum_post_count": crud.count_approved_forum_contributions(db, user.id),
        "published_post_count": crud.count_posts_for_user(db, user.id),
    }


def _reply_count(db: Session, thread_id: int) -> int:
    return db.query(func.count(models.ForumReply.id)).filter(
        models.ForumReply.thread_id == thread_id,
        models.ForumReply.moderation_status.in_(crud.PUBLIC_FORUM_STATUSES),
        crud.not_human_rejected_condition("forum_reply", models.ForumReply.id),
    ).scalar() or 0


def _section_payload(
    section: models.ForumSection,
    user: Optional[models.User] = None,
    stats: Optional[dict] = None,
    db: Optional[Session] = None,
) -> dict:
    payload = {
        "id": section.id,
        "key": section.slug,
        "slug": section.slug,
        "label": section.name,
        "name": section.name,
        "description": section.description or "",
        "position": section.position,
        "staff_only": bool(section.staff_only),
        "featured": bool(section.is_featured),
        "is_featured": bool(section.is_featured),
        "is_archived": bool(section.is_archived),
        "can_post": crud.section_posting_error(user, section) is None if user else False,
    }
    if stats is not None:
        last_thread = stats.get("last_thread")
        payload.update(
            {
                "thread_count": stats.get("thread_count", 0),
                "reply_count": stats.get("reply_count", 0),
                "last_thread": _last_thread_payload(db, last_thread) if last_thread and db is not None else None,
            }
        )
    return payload


def _last_post_payload(db: Session, thread: models.ForumThread) -> dict:
    """Who posted last in a thread and when (the latest public reply, or the opening post)."""
    reply = crud.latest_public_forum_reply(db, thread.id)
    if reply:
        return {"author": _author_ref(reply.author), "created_at": reply.created_at, "reply_id": reply.id}
    return {"author": _author_ref(thread.author), "created_at": thread.created_at, "reply_id": None}


def _last_thread_payload(db: Session, thread: models.ForumThread) -> dict:
    return {
        "id": thread.id,
        "title": thread.title,
        "slug": thread.slug,
        "last_activity_at": thread.last_activity_at,
        "last_post": _last_post_payload(db, thread),
    }


def _thread_summary_payload(
    db: Session,
    thread: models.ForumThread,
    *,
    labels: Optional[Dict[str, str]] = None,
    unread_ids: Iterable[int] = (),
    author_payload: Optional[dict] = None,
) -> dict:
    labels = labels if labels is not None else crud.forum_section_labels(db)
    return {
        "id": thread.id,
        "section": thread.section,
        "section_label": labels.get(thread.section, thread.section),
        "title": thread.title,
        "slug": thread.slug,
        "author": author_payload if author_payload is not None else _author_ref(thread.author),
        "reply_count": _reply_count(db, thread.id),
        "view_count": thread.view_count,
        "is_locked": thread.is_locked,
        "is_pinned": thread.is_pinned,
        "pinned_at": thread.pinned_at,
        "moderation_status": thread.moderation_status,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "last_activity_at": thread.last_activity_at,
        "last_post": _last_post_payload(db, thread),
        "has_new_replies": thread.id in set(unread_ids),
    }


def _reply_payload(db: Session, reply: models.ForumReply, number: Optional[int] = None) -> dict:
    return {
        "id": reply.id,
        "thread_id": reply.thread_id,
        "number": number,
        "content": crud.link_mentions_in_rich_text(db, reply.content),
        "author": _author_payload(db, reply.author),
        "is_pinned": bool(reply.is_pinned),
        "moderation_status": reply.moderation_status,
        "moderation_reason": reply.moderation_reason,
        "created_at": reply.created_at,
        "updated_at": reply.updated_at,
    }


def _report_title(prefix: str, title: str, content: str = "") -> str:
    plain = rich_text.rich_text_to_plain_text(content or "").strip()
    suffix = f": {plain[:120]}" if plain else ""
    return f"{prefix}: {title}{suffix}"


def _page_count(total: int, per_page: int) -> int:
    return max(1, math.ceil(total / per_page)) if per_page else 1


def _thread_detail_payload(
    db: Session,
    thread: models.ForumThread,
    current_user: Optional[models.User],
    page: Optional[int] = None,
    reply_id: Optional[int] = None,
) -> dict:
    replies = crud.list_forum_replies_for_thread(db, thread.id, current_user)
    numbered = list(enumerate(replies, start=1))
    total = len(replies)
    pages = _page_count(total, REPLIES_PER_PAGE)
    if reply_id is not None:
        position = next((number for number, reply in numbered if reply.id == reply_id), None)
        if position is not None:
            page = math.ceil(position / REPLIES_PER_PAGE)
    page = min(max(1, page or 1), pages)
    start = (page - 1) * REPLIES_PER_PAGE
    page_items = numbered[start:start + REPLIES_PER_PAGE]
    pinned_items = [(number, reply) for number, reply in numbered if reply.is_pinned and reply.moderation_status == "approved"]

    section = crud.get_forum_section_by_slug(db, thread.section)
    labels = {section.slug: section.name} if section else {}
    is_moderator = bool(current_user and crud.can_moderate_forum(current_user))
    can_reply = bool(
        current_user
        and thread.moderation_status == "approved"
        and (not thread.is_locked or is_moderator)
        and crud.section_posting_error(current_user, section, reply=True) is None
    )
    return {
        **_thread_summary_payload(db, thread, labels=labels, author_payload=_author_payload(db, thread.author)),
        "content": crud.link_mentions_in_rich_text(db, thread.content),
        "moderation_reason": thread.moderation_reason,
        "section_info": _section_payload(section, user=current_user) if section else None,
        "replies": [_reply_payload(db, reply, number) for number, reply in page_items],
        "pinned_replies": [_reply_payload(db, reply, number) for number, reply in pinned_items],
        "reply_total": total,
        "reply_page": page,
        "reply_pages": pages,
        "replies_per_page": REPLIES_PER_PAGE,
        "can_moderate": is_moderator,
        "can_reply": can_reply,
    }


def _raise_section_error(code: str) -> None:
    status_code, detail = SECTION_ERROR_RESPONSES.get(code, (400, "Secțiune invalidă"))
    raise HTTPException(status_code=status_code, detail=detail)


@router.get("/api/forum/sectiuni")
def list_forum_sections_api(
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    sections = crud.list_forum_sections(db)
    stats = crud.forum_section_stats(db, [section.slug for section in sections])
    return {
        "sections": [
            _section_payload(section, current_user, stats=stats.get(section.slug, {}), db=db)
            for section in sections
        ]
    }


@router.get("/api/forum/discutii")
def list_forum_threads_api(
    section: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "activity",
    page: int = 1,
    per_page: int = THREADS_PER_PAGE,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    section_obj = None
    if section:
        section_obj = crud.get_forum_section_by_slug(db, section)
        if section_obj is None:
            raise HTTPException(status_code=400, detail="Secțiune invalidă")
    if sort not in crud.FORUM_THREAD_SORTS:
        sort = "activity"
    per_page = max(1, min(per_page, 100))
    page = max(1, page)
    searching = bool(q and q.strip())
    # Inside a section, pinned threads get their own block above the regular list.
    # Search results and the cross-section feed are a single list ordered by activity.
    split_pinned = section_obj is not None and not searching
    regular_filter = False if split_pinned else None

    total = crud.count_forum_threads(db, section=section, q=q, pinned=regular_filter)
    pages = _page_count(total, per_page)
    page = min(page, pages)
    threads = crud.list_forum_threads(
        db,
        section=section,
        q=q,
        limit=per_page,
        offset=(page - 1) * per_page,
        pinned=regular_filter,
        sort=sort,
        pin_first=section_obj is not None,
    )
    pinned = crud.list_forum_threads(db, section=section, pinned=True, limit=100) if split_pinned else []

    labels = crud.forum_section_labels(db)
    unread_ids = crud.forum_threads_with_new_replies(db, current_user, [thread.id for thread in [*pinned, *threads]])
    return {
        "section": _section_payload(section_obj, user=current_user) if section_obj else None,
        "pinned": [_thread_summary_payload(db, thread, labels=labels, unread_ids=unread_ids) for thread in pinned],
        "threads": [_thread_summary_payload(db, thread, labels=labels, unread_ids=unread_ids) for thread in threads],
        "total": total,
        "page": page,
        "pages": pages,
        "per_page": per_page,
        "sort": sort,
    }


@router.post("/api/forum/discutii", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_forum_thread_api(
    request: Request,
    data: schemas.ForumThreadCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    if not data.title.strip() or not rich_text.rich_text_to_plain_text(data.content):
        raise HTTPException(status_code=400, detail="Titlul și conținutul sunt obligatorii")
    try:
        thread = crud.create_forum_thread(db, current_user, data)
    except crud.ForumSectionError as error:
        _raise_section_error(error.code)
    ai_queue.enqueue_forum_thread_moderation_job(db, thread)
    return _thread_detail_payload(db, thread, current_user)


@router.get("/api/forum/discutii/{slug}")
def get_forum_thread_api(
    slug: str,
    page: Optional[int] = None,
    reply: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    thread = crud.get_forum_thread_by_slug(db, slug)
    if not thread or not crud.can_view_forum_thread(current_user, thread, db=db):
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    payload = _thread_detail_payload(db, thread, current_user, page=page, reply_id=reply)
    crud.mark_forum_thread_read(db, current_user, thread)
    payload["view_count"] = thread.view_count
    return payload


@router.post("/api/forum/discutii/{thread_id}/raspunsuri", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_forum_reply_api(
    request: Request,
    thread_id: int,
    data: schemas.ForumReplyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    if not rich_text.rich_text_to_plain_text(data.content):
        raise HTTPException(status_code=400, detail="Conținutul este obligatoriu")
    thread = crud.get_forum_thread(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    reply, error = crud.create_forum_reply(db, current_user, thread, data)
    if error == "locked":
        raise HTTPException(status_code=403, detail="Discuția este închisă")
    if error == "archived":
        raise HTTPException(status_code=403, detail="Secțiunea este arhivată")
    if error == "thread_not_approved":
        raise HTTPException(status_code=409, detail="Discuția nu este publicată")
    if error:
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    ai_queue.enqueue_forum_reply_moderation_job(db, reply)
    return _reply_payload(db, reply)


@router.post("/api/forum/discutii/{thread_id}/raportari", response_model=schemas.PostReport, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def report_forum_thread_api(
    thread_id: int,
    report: schemas.PostReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    thread = crud.get_forum_thread(db, thread_id)
    if not thread or not crud.can_view_forum_thread(current_user, thread, db=db):
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    if thread.moderation_status != "approved":
        raise HTTPException(status_code=400, detail="Discuția nu este disponibilă pentru raportare")
    db_report = crud.create_content_report(
        db,
        content_type="forum_thread",
        content_id=thread.id,
        title=_report_title("Discuție forum", thread.title, thread.content),
        author_username=thread.author.username if thread.author else None,
        reporter_user_id=current_user.id,
        report=report,
        reported_content=thread.content,
        target_url=f"/discutii/{thread.slug}",
    )
    if not db_report:
        raise HTTPException(status_code=409, detail="Ai raportat deja această discuție pentru acest motiv")
    return crud.post_report_payload(db_report)


@router.post("/api/forum/raspunsuri/{reply_id}/raportari", response_model=schemas.PostReport, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def report_forum_reply_api(
    reply_id: int,
    report: schemas.PostReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    reply = crud.get_forum_reply(db, reply_id)
    thread = reply.thread if reply else None
    if not reply or not thread or not crud.can_view_forum_thread(current_user, thread, db=db):
        raise HTTPException(status_code=404, detail="Răspunsul nu a fost găsit")
    if reply.moderation_status != "approved":
        raise HTTPException(status_code=400, detail="Răspunsul nu este disponibil pentru raportare")
    db_report = crud.create_content_report(
        db,
        content_type="forum_reply",
        content_id=reply.id,
        title=_report_title("Răspuns forum", thread.title, reply.content),
        author_username=reply.author.username if reply.author else None,
        reporter_user_id=current_user.id,
        report=report,
        reported_content=reply.content,
        target_url=f"/discutii/{thread.slug}#reply-{reply.id}",
    )
    if not db_report:
        raise HTTPException(status_code=409, detail="Ai raportat deja acest răspuns pentru acest motiv")
    return crud.post_report_payload(db_report)


@router.delete("/api/forum/discutii/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_forum_thread_api(
    thread_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    thread = crud.get_forum_thread(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    if not crud.delete_forum_thread(db, current_user, thread):
        raise HTTPException(status_code=403, detail="Nu ai permisiunea să ștergi discuția")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/api/forum/raspunsuri/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_forum_reply_api(
    reply_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    reply = crud.get_forum_reply(db, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Răspunsul nu a fost găsit")
    if not crud.delete_forum_reply(db, current_user, reply):
        raise HTTPException(status_code=403, detail="Nu ai permisiunea să ștergi răspunsul")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/forum/discutii/{thread_id}/stare")
def update_forum_thread_state_api(
    thread_id: int,
    data: schemas.ForumThreadModerationAction,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    thread = crud.get_forum_thread(db, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    updated, error = crud.update_forum_thread_state(db, current_user, thread, data.action, data.section)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Necesită drepturi de moderator")
    if error == "invalid_section":
        raise HTTPException(status_code=400, detail="Secțiune invalidă")
    if error:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    return _thread_detail_payload(db, updated, current_user)


@router.post("/api/forum/raspunsuri/{reply_id}/stare")
def update_forum_reply_state_api(
    reply_id: int,
    data: schemas.ForumReplyModerationAction,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    reply = crud.get_forum_reply(db, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Răspunsul nu a fost găsit")
    updated, error = crud.update_forum_reply_state(db, current_user, reply, data.action)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Necesită drepturi de moderator")
    if error == "not_approved":
        raise HTTPException(status_code=409, detail="Doar răspunsurile publicate pot fi fixate")
    if error:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    return _reply_payload(db, updated)
