import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from .. import ai_queue, auth, crud, models, schemas
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stafeta"])


def _user_payload(user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
    }


def _assignment_payload(assignment: Optional[models.StafetaAssignment]) -> Optional[dict]:
    if not assignment:
        return None
    return {
        "id": assignment.id,
        "work_id": assignment.work_id,
        "user": _user_payload(assignment.user),
        "assigned_by": _user_payload(assignment.assigned_by),
        "source": assignment.source,
        "status": assignment.status,
        "due_at": assignment.due_at,
        "responded_at": assignment.responded_at,
        "completed_at": assignment.completed_at,
        "created_at": assignment.created_at,
    }


def _segment_payload(segment: models.StafetaSegment) -> dict:
    return {
        "id": segment.id,
        "work_id": segment.work_id,
        "assignment_id": segment.assignment_id,
        "author": _user_payload(segment.author),
        "content": segment.content,
        "position": segment.position,
        "next_target_mode": segment.next_target_mode,
        "next_target_user": _user_payload(segment.next_target_user),
        "moderation_status": segment.moderation_status,
        "moderation_reason": segment.moderation_reason,
        "created_at": segment.created_at,
        "updated_at": segment.updated_at,
    }


def _participation_payload(db: Session, user: models.User) -> dict:
    return crud.get_stafeta_participation_state(db, user)


def _visible_segments(
    db: Session,
    work: models.StafetaWork,
    current_user: models.User,
) -> list[models.StafetaSegment]:
    is_creator = work.creator_id == current_user.id
    segments = crud.list_stafeta_segments(db, work.id)
    return [
        segment
        for segment in segments
        if segment.moderation_status == "approved" or is_creator or segment.author_id == current_user.id
    ]


def _summary_payload(db: Session, work: models.StafetaWork) -> dict:
    current_assignment = crud.get_current_stafeta_assignment(db, work)
    return {
        "id": work.id,
        "creator_id": work.creator_id,
        "title": work.title,
        "slug": work.slug,
        "category": work.category,
        "status": work.status,
        "deadline_days": work.deadline_days,
        "max_characters": work.max_characters,
        "creator": _user_payload(work.creator),
        "current_holder": _user_payload(work.current_holder),
        "current_assignment": _assignment_payload(current_assignment),
        "approved_segment_count": crud.count_stafeta_segments(db, work.id, approved_only=True),
        "participant_count": crud.count_stafeta_participants(db, work.id),
        "published_post_id": work.published_post_id,
        "published_post_slug": work.published_post.slug if work.published_post else None,
        "created_at": work.created_at,
        "updated_at": work.updated_at,
        "published_at": work.published_at,
    }


def _detail_payload(db: Session, work: models.StafetaWork, current_user: models.User) -> dict:
    current_assignment = crud.get_current_stafeta_assignment(db, work)
    is_creator = work.creator_id == current_user.id
    is_holder = bool(
        current_assignment
        and current_assignment.user_id == current_user.id
        and current_assignment.status == "active"
    )
    can_respond = bool(
        current_assignment
        and current_assignment.user_id == current_user.id
        and current_assignment.status == "pending"
    )
    previous = crud.list_previous_stafeta_participants(db, work, exclude_user_id=current_user.id)
    role = None
    if is_creator:
        role = "creator"
    elif is_holder:
        role = "holder"
    elif can_respond:
        role = "invited"
    elif crud.actor_can_view_stafeta(db, work, current_user):
        role = "participant"
    return {
        **_summary_payload(db, work),
        "segments": [_segment_payload(segment) for segment in _visible_segments(db, work, current_user)],
        "assignments": [_assignment_payload(assignment) for assignment in crud.list_stafeta_assignments(db, work.id)],
        "previous_participants": [
            {
                "user": _user_payload(user),
                "first_joined_at": None,
                "last_seen_at": None,
            }
            for user in previous
        ],
        "my_role": role,
        "can_write": is_holder and work.status == "active",
        "can_respond": can_respond and work.status == "active",
        **_participation_payload(db, current_user),
    }


def _load_work_or_404(db: Session, work_id: int) -> models.StafetaWork:
    work = crud.get_stafeta_work(db, work_id)
    if not work:
        raise HTTPException(status_code=404, detail="Ștafeta nu a fost găsită")
    return work


def _ensure_can_view(db: Session, work: models.StafetaWork, current_user: models.User) -> None:
    if not crud.actor_can_view_stafeta(db, work, current_user):
        raise HTTPException(status_code=404, detail="Ștafeta nu a fost găsită")


def _assignment_error(error: Optional[str]) -> None:
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Nu poți face această acțiune")
    if error == "not_pending":
        raise HTTPException(status_code=409, detail="Invitația nu mai este în așteptare")
    if error == "work_not_active":
        raise HTTPException(status_code=409, detail="Ștafeta nu mai este activă")
    if error == "bad_action":
        raise HTTPException(status_code=400, detail="Acțiune invalidă")


def _send_error(error: Optional[str]) -> None:
    if error == "work_not_active":
        raise HTTPException(status_code=409, detail="Ștafeta nu mai este activă")
    if error == "not_your_turn":
        raise HTTPException(status_code=403, detail="Nu este rândul tău")
    if error == "segment_pending":
        raise HTTPException(status_code=409, detail="Contribuția ta este încă în moderare")
    if error == "content_too_long":
        raise HTTPException(status_code=400, detail="Contribuția depășește numărul maxim de caractere")
    if error == "target_not_previous":
        raise HTTPException(status_code=400, detail="Alege un participant anterior din listă")
    if error == "target_not_found":
        raise HTTPException(status_code=404, detail="Destinatarul nu a fost găsit")
    if error == "target_is_current":
        raise HTTPException(status_code=400, detail="Nu poți trimite ștafeta către tine")
    if error == "target_at_capacity":
        raise HTTPException(status_code=409, detail="Utilizatorul are deja numărul maxim de Ștafete active")
    if error == "no_random_participant":
        raise HTTPException(status_code=409, detail="Nu există utilizatori disponibili în Ștafeta")


@router.get("/api/stafeta/participare")
def get_stafeta_participation_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    return _participation_payload(db, current_user)


@router.put("/api/stafeta/participare")
def update_stafeta_participation_api(
    data: schemas.StafetaParticipationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    crud.set_stafeta_participation(db, current_user, data.participates, data.desired_slots)
    return _participation_payload(db, current_user)


@router.get("/api/stafeta")
def list_stafeta_api(
    filter: schemas.StafetaListFilter = "all",
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    works = crud.list_stafeta_works(db, current_user, filter_value=filter, limit=limit, offset=offset)
    return {
        "works": [_summary_payload(db, work) for work in works],
        **_participation_payload(db, current_user),
    }


@router.post("/api/stafeta", status_code=status.HTTP_201_CREATED)
def create_stafeta_api(
    data: schemas.StafetaCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    work, error = crud.create_stafeta_work(db, current_user, data)
    if error == "suspended":
        raise HTTPException(status_code=403, detail="Contul tău este suspendat")
    if error == "user_not_found":
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    if error == "target_suspended":
        raise HTTPException(status_code=400, detail="Utilizatorul este suspendat")
    if error == "target_at_capacity":
        raise HTTPException(status_code=409, detail="Utilizatorul are deja numărul maxim de Ștafete active")
    if error:
        raise HTTPException(status_code=400, detail="Nu am putut crea Ștafeta")
    return _detail_payload(db, work, current_user)


@router.get("/api/stafeta/{slug}")
def get_stafeta_api(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    work = crud.get_stafeta_work_by_slug(db, slug)
    if not work:
        raise HTTPException(status_code=404, detail="Ștafeta nu a fost găsită")
    _ensure_can_view(db, work, current_user)
    return _detail_payload(db, work, current_user)


@router.post("/api/stafeta/{work_id}/invitatie/{assignment_id}/raspunde")
def respond_stafeta_assignment_api(
    work_id: int,
    assignment_id: int,
    data: schemas.StafetaAssignmentRespond,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    assignment = crud.get_stafeta_assignment(db, assignment_id)
    if not assignment or assignment.work_id != work_id:
        raise HTTPException(status_code=404, detail="Invitația nu a fost găsită")
    updated, error = crud.respond_to_stafeta_assignment(db, assignment, current_user, data.action)
    _assignment_error(error)
    return _assignment_payload(updated)


@router.post("/api/stafeta/{work_id}/trimite")
def send_stafeta_forward_api(
    work_id: int,
    data: schemas.StafetaSend,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    work = _load_work_or_404(db, work_id)
    result, error = crud.send_stafeta_forward(db, work, current_user, data)
    _send_error(error)
    if isinstance(result, models.StafetaSegment):
        return {"segment": _segment_payload(result)}
    return {"assignment": _assignment_payload(result)}


@router.post("/api/stafeta/{work_id}/atribuie")
def assign_stafeta_specific_api(
    work_id: int,
    data: schemas.StafetaAssignSpecific,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    work = _load_work_or_404(db, work_id)
    target = crud.get_user_by_username(db, data.username)
    if not target:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    assignment, error = crud.creator_assign_stafeta_user(db, work, current_user, target)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate atribui Ștafeta")
    if error == "work_not_active":
        raise HTTPException(status_code=409, detail="Ștafeta nu mai este activă")
    if error == "target_suspended":
        raise HTTPException(status_code=400, detail="Utilizatorul este suspendat")
    if error == "target_at_capacity":
        raise HTTPException(status_code=409, detail="Utilizatorul are deja numărul maxim de Ștafete active")
    return _assignment_payload(assignment)


@router.post("/api/stafeta/{work_id}/aleatoriu")
def assign_stafeta_random_api(
    work_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    work = _load_work_or_404(db, work_id)
    assignment, error = crud.creator_assign_stafeta_random(db, work, current_user)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate atribui Ștafeta")
    if error == "work_not_active":
        raise HTTPException(status_code=409, detail="Ștafeta nu mai este activă")
    if error == "no_random_participant":
        raise HTTPException(status_code=409, detail="Nu există utilizatori disponibili în Ștafeta")
    return _assignment_payload(assignment)


@router.post("/api/stafeta/{work_id}/publica")
def publish_stafeta_api(
    work_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    work = _load_work_or_404(db, work_id)
    post, error = crud.publish_stafeta_work(db, work, current_user)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate publica Ștafeta")
    if error == "work_not_active":
        raise HTTPException(status_code=409, detail="Ștafeta nu mai este activă")
    if error == "no_content":
        raise HTTPException(status_code=409, detail="Ștafeta nu are text aprobat")
    if error == "content_too_long":
        raise HTTPException(status_code=409, detail="Textul final depășește limita pentru categoria aleasă")
    ai_queue.enqueue_post_publish_job(db, post, ai_critic_requested=False)
    return {"post_id": post.id, "post_slug": post.slug, "status": post.moderation_status}


@router.delete("/api/stafeta/{work_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_stafeta_api(
    work_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    work = _load_work_or_404(db, work_id)
    ok, error = crud.cancel_stafeta_work(db, work, current_user)
    if not ok and error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate anula Ștafeta")
    if not ok and error == "already_published":
        raise HTTPException(status_code=409, detail="Ștafeta este deja publicată")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
