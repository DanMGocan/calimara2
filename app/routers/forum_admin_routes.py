"""Admin-only forum management: sections (create, edit, reorder, archive, delete) and bulk thread tools."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from .. import admin, crud, models, schemas
from ..database import get_db
from .forum_routes import _author_ref, _section_payload

router = APIRouter(prefix="/api/admin/forum", tags=["admin", "forum"])

THREAD_STATUSES = {"approved", "pending", "flagged", "rejected"}


def _audit(
    db: Session,
    request: Request,
    actor: models.User,
    *,
    action: str,
    target_type: str,
    target_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    admin.write_admin_audit_log(
        db,
        actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=None,
        request=request,
        extra_data=metadata,
    )


def _sections_response(db: Session, actor: models.User) -> dict:
    sections = crud.list_forum_sections(db)
    stats = crud.forum_section_stats(db, [section.slug for section in sections])
    payload = []
    for section in sections:
        item = _section_payload(section, actor, stats=stats.get(section.slug, {}), db=db)
        # Admins see every thread, including pending/flagged/rejected ones.
        item["total_thread_count"] = crud.count_threads_in_section(db, section.slug)
        payload.append(item)
    return {"sections": payload}


def _get_section_or_404(db: Session, section_id: int) -> models.ForumSection:
    section = crud.get_forum_section(db, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Secțiunea nu a fost găsită")
    return section


def _admin_thread_payload(thread: models.ForumThread, labels: dict, reply_count: int = 0) -> dict:
    return {
        "id": thread.id,
        "title": thread.title,
        "slug": thread.slug,
        "section": thread.section,
        "section_label": labels.get(thread.section, thread.section),
        "author": _author_ref(thread.author),
        "moderation_status": thread.moderation_status,
        "is_pinned": thread.is_pinned,
        "is_locked": thread.is_locked,
        "view_count": thread.view_count,
        "reply_count": reply_count,
        "created_at": thread.created_at,
        "last_activity_at": thread.last_activity_at,
    }


@router.get("/sectiuni")
def admin_list_forum_sections(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    return _sections_response(db, current_user)


@router.post("/sectiuni", status_code=201)
def admin_create_forum_section(
    data: schemas.ForumSectionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    section, error = crud.create_forum_section(db, current_user, data)
    if error == "slug_taken":
        raise HTTPException(status_code=409, detail="Există deja o secțiune cu acest identificator")
    _audit(db, request, current_user, action="forum_section_create", target_type="forum_section", target_id=section.id,
           metadata={"slug": section.slug, "name": section.name})
    return _section_payload(section, current_user)


@router.post("/sectiuni/ordine")
def admin_reorder_forum_sections(
    data: schemas.ForumSectionOrder,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    sections = crud.reorder_forum_sections(db, data.section_ids)
    _audit(db, request, current_user, action="forum_section_reorder", target_type="forum_section",
           metadata={"order": [section.slug for section in sections]})
    return _sections_response(db, current_user)


@router.put("/sectiuni/{section_id}")
def admin_update_forum_section(
    section_id: int,
    data: schemas.ForumSectionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    section = _get_section_or_404(db, section_id)
    before = {
        "slug": section.slug,
        "name": section.name,
        "description": section.description,
        "staff_only": section.staff_only,
        "is_featured": section.is_featured,
        "is_archived": section.is_archived,
    }
    updated, error = crud.update_forum_section(db, section, data)
    if error == "slug_taken":
        raise HTTPException(status_code=409, detail="Există deja o secțiune cu acest identificator")
    _audit(db, request, current_user, action="forum_section_update", target_type="forum_section", target_id=section_id,
           metadata={"before": before, "changes": data.model_dump(exclude_none=True)})
    return _section_payload(updated, current_user)


@router.delete("/sectiuni/{section_id}")
def admin_delete_forum_section(
    section_id: int,
    request: Request,
    move_to: Optional[str] = Query(None, max_length=60),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    section = _get_section_or_404(db, section_id)
    target = None
    if move_to:
        target = crud.get_forum_section_by_slug(db, move_to)
        if target is None:
            raise HTTPException(status_code=400, detail="Secțiunea de destinație nu există")
    slug = section.slug
    moved, error = crud.delete_forum_section(db, section, target)
    if error == "last_section":
        raise HTTPException(status_code=409, detail="Forumul trebuie să aibă cel puțin o secțiune")
    if error == "same_section":
        raise HTTPException(status_code=400, detail="Alege o altă secțiune pentru discuții")
    if error == "not_empty":
        raise HTTPException(status_code=409, detail="Secțiunea are discuții. Alege unde le muți sau arhiveaz-o.")
    _audit(db, request, current_user, action="forum_section_delete", target_type="forum_section", target_id=section_id,
           metadata={"slug": slug, "moved_threads": moved, "move_to": target.slug if target else None})
    return {"deleted": True, "moved_threads": moved, **_sections_response(db, current_user)}


@router.get("/discutii")
def admin_list_forum_threads(
    section: Optional[str] = None,
    status: Optional[str] = None,
    pinned: Optional[bool] = None,
    locked: Optional[bool] = None,
    q: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    if status and status not in THREAD_STATUSES:
        raise HTTPException(status_code=400, detail="Status invalid")
    per_page = max(1, min(per_page, 200))
    page = max(1, page)
    threads, total = crud.list_forum_threads_for_admin(
        db,
        section=section or None,
        status=status or None,
        pinned=pinned,
        locked=locked,
        q=q,
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    labels = crud.forum_section_labels(db)
    reply_stats = crud.forum_thread_reply_stats(db, [thread.id for thread in threads])
    return {
        "threads": [
            _admin_thread_payload(thread, labels, reply_stats.get(thread.id, {}).get("reply_count", 0))
            for thread in threads
        ],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // per_page)),
        "per_page": per_page,
    }


@router.post("/discutii/actiuni")
def admin_bulk_forum_thread_action(
    data: schemas.AdminForumThreadBulkAction,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(admin.require_admin),
):
    affected, error = crud.bulk_update_forum_threads(db, current_user, data.thread_ids, data.action, data.section)
    if error == "invalid_section":
        raise HTTPException(status_code=400, detail="Secțiune invalidă")
    if error:
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    _audit(db, request, current_user, action=f"forum_thread_bulk_{data.action}", target_type="forum_thread",
           metadata={"thread_ids": data.thread_ids, "affected": affected, "section": data.section})
    return {"affected": affected}
