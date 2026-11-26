import logging
from typing import Optional

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


FORUM_SECTIONS = [
    {"key": "anunturi", "label": "Anunțuri"},
    {"key": "general", "label": "Discuții generale"},
    {"key": "poezie", "label": "Poezie"},
    {"key": "proza_scurta", "label": "Proză scurtă"},
]


def _author_payload(db: Session, user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    profile_photo_url = None
    if getattr(user, "is_premium", False) and getattr(user, "profile_photo_storage_key", None):
        profile_photo_url = profile_media.public_media_url(user.username, "profil")
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "avatar_url": profile_photo_url or get_avatar_url(user, size=96),
        "profile_photo_url": profile_photo_url,
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
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


def _thread_summary_payload(db: Session, thread: models.ForumThread) -> dict:
    return {
        "id": thread.id,
        "section": thread.section,
        "title": thread.title,
        "slug": thread.slug,
        "author": _author_payload(db, thread.author),
        "reply_count": _reply_count(db, thread.id),
        "view_count": thread.view_count,
        "is_locked": thread.is_locked,
        "is_pinned": thread.is_pinned,
        "moderation_status": thread.moderation_status,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "last_activity_at": thread.last_activity_at,
    }


def _reply_payload(db: Session, reply: models.ForumReply) -> dict:
    return {
        "id": reply.id,
        "thread_id": reply.thread_id,
        "content": crud.link_mentions_in_rich_text(db, reply.content),
        "author": _author_payload(db, reply.author),
        "moderation_status": reply.moderation_status,
        "moderation_reason": reply.moderation_reason,
        "created_at": reply.created_at,
        "updated_at": reply.updated_at,
    }


def _report_title(prefix: str, title: str, content: str = "") -> str:
    plain = rich_text.rich_text_to_plain_text(content or "").strip()
    suffix = f": {plain[:120]}" if plain else ""
    return f"{prefix}: {title}{suffix}"


def _thread_detail_payload(
    db: Session,
    thread: models.ForumThread,
    current_user: Optional[models.User],
) -> dict:
    replies = crud.list_forum_replies_for_thread(db, thread.id, current_user)
    return {
        **_thread_summary_payload(db, thread),
        "content": crud.link_mentions_in_rich_text(db, thread.content),
        "moderation_reason": thread.moderation_reason,
        "replies": [_reply_payload(db, reply) for reply in replies],
    }


@router.get("/api/forum/sectiuni")
def list_forum_sections_api():
    return {"sections": FORUM_SECTIONS}


@router.get("/api/forum/discutii")
def list_forum_threads_api(
    section: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    if section and not crud.is_forum_section(section):
        raise HTTPException(status_code=400, detail="Secțiune invalidă")
    threads = crud.list_forum_threads(
        db,
        section=section,
        q=q,
        limit=limit,
        offset=offset,
    )
    return {"threads": [_thread_summary_payload(db, thread) for thread in threads]}


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
    except ValueError:
        raise HTTPException(status_code=400, detail="Secțiune invalidă")
    ai_queue.enqueue_forum_thread_moderation_job(db, thread)
    return _thread_detail_payload(db, thread, current_user)


@router.get("/api/forum/discutii/{slug}")
def get_forum_thread_api(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    thread = crud.get_forum_thread_by_slug(db, slug)
    if not thread or not crud.can_view_forum_thread(current_user, thread, db=db):
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    return _thread_detail_payload(db, thread, current_user)


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
    updated, error = crud.update_forum_thread_state(db, current_user, thread, data.action)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Necesită drepturi de moderator")
    if error:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    return _thread_detail_payload(db, updated, current_user)
