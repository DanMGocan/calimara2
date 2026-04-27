import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import auth, crud, models, moderation, schemas
from ..database import get_db

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["forum"])


FORUM_SECTIONS = [
    {"key": "general", "label": "General"},
    {"key": "poezie", "label": "Poezie"},
    {"key": "proza_scurta", "label": "Proză scurtă"},
    {"key": "feedback", "label": "Feedback"},
    {"key": "anunturi", "label": "Anunțuri"},
]


def _author_payload(user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
    }


def _reply_count(db: Session, thread_id: int) -> int:
    return db.query(func.count(models.ForumReply.id)).filter(
        models.ForumReply.thread_id == thread_id,
        models.ForumReply.moderation_status == "approved",
    ).scalar() or 0


def _thread_summary_payload(db: Session, thread: models.ForumThread) -> dict:
    return {
        "id": thread.id,
        "section": thread.section,
        "title": thread.title,
        "slug": thread.slug,
        "author": _author_payload(thread.author),
        "reply_count": _reply_count(db, thread.id),
        "view_count": thread.view_count,
        "is_locked": thread.is_locked,
        "is_pinned": thread.is_pinned,
        "moderation_status": thread.moderation_status,
        "created_at": thread.created_at,
        "updated_at": thread.updated_at,
        "last_activity_at": thread.last_activity_at,
    }


def _reply_payload(reply: models.ForumReply) -> dict:
    return {
        "id": reply.id,
        "thread_id": reply.thread_id,
        "content": reply.content,
        "author": _author_payload(reply.author),
        "moderation_status": reply.moderation_status,
        "moderation_reason": reply.moderation_reason,
        "created_at": reply.created_at,
        "updated_at": reply.updated_at,
    }


def _thread_detail_payload(
    db: Session,
    thread: models.ForumThread,
    current_user: models.User,
) -> dict:
    replies = crud.list_forum_replies_for_thread(db, thread.id, current_user)
    return {
        **_thread_summary_payload(db, thread),
        "content": thread.content,
        "moderation_reason": thread.moderation_reason,
        "replies": [_reply_payload(reply) for reply in replies],
    }


def _apply_thread_moderation(
    db: Session,
    thread: models.ForumThread,
    current_user: models.User,
) -> models.ForumThread:
    try:
        result = moderation.moderate_forum_thread_with_logging(
            thread.title, thread.content, thread.id, current_user.id, db
        )
        thread = crud.apply_forum_thread_moderation_result(db, thread, result)
        if thread.moderation_status == "flagged":
            crud.create_notification(
                db=db,
                user_id=current_user.id,
                notif_type="moderation_queue",
                title="Discuție în curs de moderare",
                message=f"Discuția „{thread.title}\" a fost trimisă pentru revizuire manuală.",
                link=None,
                extra_data={"thread_id": thread.id},
            )
        return thread
    except Exception as exc:
        logger.error(f"Forum thread moderation failed for {thread.id}: {exc}")
        thread.moderation_status = "approved"
        thread.moderation_reason = "Auto-approved due to moderation error"
        db.commit()
        db.refresh(thread)
        return thread


def _apply_reply_moderation(
    db: Session,
    reply: models.ForumReply,
    thread: models.ForumThread,
    current_user: models.User,
) -> models.ForumReply:
    try:
        result = moderation.moderate_forum_reply_with_logging(
            reply.content, reply.id, current_user.id, db
        )
        reply = crud.apply_forum_reply_moderation_result(db, reply, result)
        if reply.moderation_status == "flagged":
            crud.create_notification(
                db=db,
                user_id=current_user.id,
                notif_type="moderation_queue",
                title="Răspuns în curs de moderare",
                message=f"Răspunsul tău în „{thread.title}\" a fost trimis pentru revizuire manuală.",
                link=None,
                extra_data={"thread_id": thread.id, "reply_id": reply.id},
            )
        return reply
    except Exception as exc:
        logger.error(f"Forum reply moderation failed for {reply.id}: {exc}")
        reply.moderation_status = "approved"
        reply.moderation_reason = "Auto-approved due to moderation error"
        if reply.thread:
            reply.thread.last_activity_at = func.now()
        db.commit()
        db.refresh(reply)
        crud._notify_forum_reply_approved(db, reply)
        return reply


@router.get("/api/forum/sections")
def list_forum_sections_api(
    current_user: models.User = Depends(auth.get_required_user),
):
    return {"sections": FORUM_SECTIONS}


@router.get("/api/forum/threads")
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


@router.post("/api/forum/threads", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_forum_thread_api(
    request: Request,
    data: schemas.ForumThreadCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    if not data.title.strip() or not data.content.strip():
        raise HTTPException(status_code=400, detail="Titlul și conținutul sunt obligatorii")
    try:
        thread = crud.create_forum_thread(db, current_user, data)
    except ValueError:
        raise HTTPException(status_code=400, detail="Secțiune invalidă")
    thread = _apply_thread_moderation(db, thread, current_user)
    return _thread_detail_payload(db, thread, current_user)


@router.get("/api/forum/threads/{slug}")
def get_forum_thread_api(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    thread = crud.get_forum_thread_by_slug(db, slug)
    if not thread or not crud.can_view_forum_thread(current_user, thread):
        raise HTTPException(status_code=404, detail="Discuția nu a fost găsită")
    return _thread_detail_payload(db, thread, current_user)


@router.post("/api/forum/threads/{thread_id}/replies", status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_forum_reply_api(
    request: Request,
    thread_id: int,
    data: schemas.ForumReplyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    if not data.content.strip():
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
    reply = _apply_reply_moderation(db, reply, thread, current_user)
    return _reply_payload(reply)


@router.delete("/api/forum/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.delete("/api/forum/replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.post("/api/forum/threads/{thread_id}/state")
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
