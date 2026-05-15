import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from .. import ai_queue, auth, crud, models, pdf_exporter, schemas
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["theatre"])


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


def _character_payload(
    character: Optional[models.TheatreCharacter],
    pending_request: Optional[models.TheatreJoinRequest] = None,
) -> Optional[dict]:
    if not character:
        return None
    assignment_status = None
    if character.status == "approved":
        if character.assigned_user_id:
            assignment_status = "personaj_atribuit"
        elif pending_request:
            assignment_status = "utilizator_invitat"
        else:
            assignment_status = "liber"
    return {
        "id": character.id,
        "play_id": character.play_id,
        "name": character.name,
        "description": character.description,
        "status": character.status,
        "proposed_by": character.proposed_by,
        "proposer": _user_payload(character.proposer),
        "assigned_user_id": character.assigned_user_id,
        "assigned_user": _user_payload(character.assigned_user),
        "assignment_status": assignment_status,
        "pending_invitation_user": _user_payload(pending_request.user) if pending_request else None,
        "created_at": character.created_at,
        "approved_at": character.approved_at,
    }


def _member_payload(member: models.TheatreMember) -> dict:
    return {
        "id": member.id,
        "user_id": member.user_id,
        "user": _user_payload(member.user),
        "role": member.role,
        "joined_at": member.joined_at,
    }


def _entry_payload(entry: models.TheatreEntry) -> dict:
    return {
        "id": entry.id,
        "play_id": entry.play_id,
        "scene_id": entry.scene_id,
        "author": _user_payload(entry.author),
        "character": _character_payload(entry.character),
        "next_character": _character_payload(entry.next_character),
        "entry_type": entry.entry_type,
        "content": entry.content,
        "position": entry.position,
        "moderation_status": entry.moderation_status,
        "moderation_reason": entry.moderation_reason,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def _scene_payload(scene: models.TheatreScene, *, include_pending: bool) -> dict:
    entries = sorted(scene.entries or [], key=lambda item: (item.position, item.id))
    if not include_pending:
        entries = [entry for entry in entries if entry.moderation_status == "approved"]
    return {
        "id": scene.id,
        "play_id": scene.play_id,
        "scene_number": scene.scene_number,
        "title": scene.title,
        "status": scene.status,
        "created_at": scene.created_at,
        "ended_at": scene.ended_at,
        "entries": [_entry_payload(entry) for entry in entries],
    }


def _join_request_payload(req: models.TheatreJoinRequest) -> dict:
    return {
        "id": req.id,
        "play_id": req.play_id,
        "user": _user_payload(req.user),
        "direction": req.direction,
        "status": req.status,
        "initiator_id": req.initiator_id,
        "character": _character_payload(req.character),
        "note": req.note,
        "created_at": req.created_at,
        "responded_at": req.responded_at,
    }


def _play_summary_payload(db: Session, play: models.TheatrePlay) -> dict:
    return {
        "id": play.id,
        "creator_id": play.creator_id,
        "title": play.title,
        "slug": play.slug,
        "description": play.description,
        "status": play.status,
        "creator": _user_payload(play.creator),
        "character_count": crud.count_theatre_characters(db, play.id),
        "actor_count": crud.count_theatre_actors(db, play.id),
        "scene_count": crud.count_theatre_scenes(db, play.id),
        "current_scene_id": play.current_scene_id,
        "current_character_id": play.current_character_id,
        "current_actor_user_id": play.current_actor_user_id,
        "created_at": play.created_at,
        "updated_at": play.updated_at,
    }


def _play_detail_payload(
    db: Session,
    play: models.TheatrePlay,
    current_user: Optional[models.User],
) -> dict:
    membership = None
    if current_user:
        membership = crud.get_theatre_membership(db, play.id, current_user.id)
    is_creator = bool(current_user and play.creator_id == current_user.id)
    include_pending = bool(membership or is_creator)

    members = crud.list_theatre_members(db, play.id)
    characters = crud.list_theatre_characters(db, play.id)
    scenes = crud.list_theatre_scenes(db, play.id)
    pending_requests_by_character_id = {
        request.character_id: request
        for request in crud.list_theatre_pending_requests(db, play.id)
        if request.character_id
    }
    current_character = next(
        (character for character in characters if character.id == play.current_character_id),
        None,
    )

    my_pending = None
    my_pending_request = None
    pending_request_count = None
    pending_character_count = None
    if current_user:
        pending = crud.get_user_pending_theatre_request(db, play.id, current_user.id)
        my_pending = pending.direction if pending else None
        my_pending_request = _join_request_payload(pending) if pending else None
        if is_creator:
            pending_request_count = crud.count_pending_theatre_requests(db, play.id)
            pending_character_count = crud.count_pending_theatre_characters(db, play.id)

    return {
        **_play_summary_payload(db, play),
        "members": [_member_payload(member) for member in members],
        "characters": [
            _character_payload(character, pending_requests_by_character_id.get(character.id))
            for character in characters
        ],
        "scenes": [_scene_payload(scene, include_pending=include_pending) for scene in scenes],
        "current_character": _character_payload(current_character),
        "my_role": membership.role if membership else None,
        "my_character_ids": [
            character.id
            for character in characters
            if current_user and character.assigned_user_id == current_user.id and character.status == "approved"
        ],
        "my_pending_request_status": my_pending,
        "my_pending_request": my_pending_request,
        "pending_request_count": pending_request_count,
        "pending_character_count": pending_character_count,
    }


def _load_play_or_404(db: Session, play_id: int) -> models.TheatrePlay:
    play = crud.get_theatre_play(db, play_id)
    if not play:
        raise HTTPException(status_code=404, detail="Piesa nu a fost găsită")
    return play


def _load_scene_or_404(db: Session, play: models.TheatrePlay, scene_id: int) -> models.TheatreScene:
    scene = db.query(models.TheatreScene).filter(
        models.TheatreScene.id == scene_id,
        models.TheatreScene.play_id == play.id,
    ).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scena nu a fost găsită")
    return scene


def _character_error(error: Optional[str]) -> None:
    if error == "character_not_found":
        raise HTTPException(status_code=404, detail="Personajul nu a fost găsit")
    if error == "character_not_approved":
        raise HTTPException(status_code=409, detail="Personajul nu este aprobat")
    if error == "character_unavailable":
        raise HTTPException(status_code=409, detail="Personajul este deja atribuit")
    if error == "character_has_pending_request":
        raise HTTPException(status_code=409, detail="Personajul are deja o invitație sau cerere în așteptare")
    if error == "user_already_assigned":
        raise HTTPException(status_code=409, detail="Utilizatorul joacă deja un personaj în această piesă")
    if error == "character_not_ready":
        raise HTTPException(status_code=409, detail="Personajul nu este pregătit")
    if error == "next_character_not_found":
        raise HTTPException(status_code=404, detail="Următorul personaj nu a fost găsit")
    if error == "next_character_not_ready":
        raise HTTPException(status_code=409, detail="Următorul personaj nu este pregătit")


@router.get("/api/teatru")
def list_theatre_plays_api(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    plays = crud.list_theatre_plays(db, limit=limit, offset=offset)
    return {"plays": [_play_summary_payload(db, play) for play in plays]}


@router.post("/api/teatru", status_code=status.HTTP_201_CREATED)
def create_theatre_play_api(
    data: schemas.TheatrePlayCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        play = crud.create_theatre_play(db, current_user, data)
    except ValueError as exc:
        if str(exc) == "suspended":
            raise HTTPException(status_code=403, detail="Contul tău este suspendat")
        if str(exc) == "assigned_user_not_found":
            raise HTTPException(status_code=404, detail="Un utilizator atribuit nu a fost găsit")
        if str(exc) == "user_already_assigned":
            raise HTTPException(status_code=409, detail="Fiecare utilizator poate juca un singur personaj")
        if str(exc) == "duplicate_character":
            raise HTTPException(status_code=409, detail="Există deja un personaj cu acest nume")
        raise HTTPException(status_code=400, detail="Nu am putut crea piesa")
    return _play_detail_payload(db, play, current_user)


@router.get("/api/teatru/{slug}/pdf")
def theatre_pdf_download(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
):
    play = crud.get_theatre_play_by_slug(db, slug)
    if not play:
        raise HTTPException(status_code=404, detail="Piesa nu a fost găsită")
    scenes = crud.list_theatre_scenes(db, play.id)
    page_url = pdf_exporter.theatre_page_url(request, play.slug)
    pdf_bytes = pdf_exporter.render_theatre_pdf(
        play=play,
        creator=play.creator,
        scenes=scenes,
        page_url=page_url,
    )
    return FastAPIResponse(
        content=pdf_bytes,
        media_type=pdf_exporter.PDF_MEDIA_TYPE,
        headers=pdf_exporter.pdf_response_headers(f"teatru-{play.slug}"),
    )


@router.get("/api/teatru/{slug}")
def get_theatre_play_api(
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    play = crud.get_theatre_play_by_slug(db, slug)
    if not play:
        raise HTTPException(status_code=404, detail="Piesa nu a fost găsită")
    return _play_detail_payload(db, play, current_user)


@router.put("/api/teatru/{play_id}")
def update_theatre_play_api(
    play_id: int,
    data: schemas.TheatrePlayUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    updated, error = crud.update_theatre_play(db, play, current_user, data)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate modifica piesa")
    return _play_detail_payload(db, updated, current_user)


@router.delete("/api/teatru/{play_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_theatre_play_api(
    play_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    ok, error = crud.delete_theatre_play(db, play, current_user)
    if not ok and error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate șterge piesa")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/teatru/{play_id}/cereri")
def apply_to_theatre_play_api(
    play_id: int,
    data: schemas.TheatreJoinApply,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    try:
        request, error = crud.apply_to_theatre_play(db, current_user, play, data)
    except ValueError as exc:
        if str(exc) == "duplicate_character":
            raise HTTPException(status_code=409, detail="Există deja un personaj cu acest nume")
        raise
    if error == "suspended":
        raise HTTPException(status_code=403, detail="Contul tău este suspendat")
    if error == "already_member":
        raise HTTPException(status_code=409, detail="Ești deja participant")
    if error == "already_pending":
        raise HTTPException(status_code=409, detail="Ai deja o cerere în așteptare")
    if error == "too_many_characters":
        raise HTTPException(status_code=400, detail="Alege un personaj existent sau propune unul nou")
    _character_error(error)
    return _join_request_payload(request)


@router.post("/api/teatru/{play_id}/invita")
def invite_to_theatre_play_api(
    play_id: int,
    data: schemas.TheatreInvite,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    target = crud.get_user_by_username(db, data.username)
    if not target:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    request, error = crud.invite_to_theatre_play(db, current_user, play, target, data)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate invita")
    if error == "target_suspended":
        raise HTTPException(status_code=400, detail="Utilizatorul este suspendat")
    if error == "already_member":
        raise HTTPException(status_code=409, detail="Utilizatorul este deja participant")
    if error == "already_pending":
        raise HTTPException(status_code=409, detail="Există deja o invitație sau cerere în așteptare")
    _character_error(error)
    return _join_request_payload(request)


@router.get("/api/teatru/{play_id}/cereri")
def list_theatre_requests_api(
    play_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    if play.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar creatorul poate vedea cererile")
    requests = crud.list_theatre_pending_requests(db, play.id)
    return {"requests": [_join_request_payload(request) for request in requests]}


@router.post("/api/teatru/{play_id}/cereri/{request_id}/raspunde")
def respond_theatre_request_api(
    play_id: int,
    request_id: int,
    data: schemas.TheatreJoinRespond,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    request = crud.get_theatre_join_request(db, request_id)
    if not request or request.play_id != play_id:
        raise HTTPException(status_code=404, detail="Cererea nu a fost găsită")
    updated, error = crud.respond_to_theatre_request(db, request, current_user, data.action)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Nu poți răspunde la această cerere")
    if error == "not_pending":
        raise HTTPException(status_code=409, detail="Cererea nu mai este în așteptare")
    if error == "bad_action":
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    _character_error(error)
    return _join_request_payload(updated)


@router.post("/api/teatru/{play_id}/personaje")
def create_theatre_character_api(
    play_id: int,
    data: schemas.TheatreCharacterCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    try:
        character, error = crud.create_theatre_character(db, current_user, play, data)
    except ValueError as exc:
        if str(exc) == "duplicate_character":
            raise HTTPException(status_code=409, detail="Există deja un personaj cu acest nume")
        raise
    if error == "not_member":
        raise HTTPException(status_code=403, detail="Trebuie să fii participant")
    return _character_payload(character)


@router.post("/api/teatru/{play_id}/personaje/{character_id}/raspunde")
def review_theatre_character_api(
    play_id: int,
    character_id: int,
    data: schemas.TheatreCharacterReview,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    character = crud.get_theatre_character(db, character_id)
    if not character or character.play_id != play_id:
        raise HTTPException(status_code=404, detail="Personajul nu a fost găsit")
    updated, error = crud.review_theatre_character(db, current_user, character, data.action)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate aproba personaje")
    if error == "not_pending":
        raise HTTPException(status_code=409, detail="Personajul nu mai este în așteptare")
    if error == "bad_action":
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    return _character_payload(updated)


@router.delete("/api/teatru/{play_id}/personaje/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_theatre_character_api(
    play_id: int,
    character_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    character = crud.get_theatre_character(db, character_id)
    if not character or character.play_id != play_id:
        raise HTTPException(status_code=404, detail="Personajul nu a fost găsit")
    ok, error = crud.delete_theatre_character(db, current_user, character)
    if not ok and error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate șterge personaje")
    if not ok and error == "character_in_use":
        raise HTTPException(status_code=409, detail="Personajul este deja folosit într-o scenă")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/teatru/{play_id}/personaje/{character_id}/atribuie")
def assign_theatre_character_api(
    play_id: int,
    character_id: int,
    data: schemas.TheatreCharacterAssign,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    character = crud.get_theatre_character(db, character_id)
    if not character or character.play_id != play_id:
        raise HTTPException(status_code=404, detail="Personajul nu a fost găsit")
    updated, error = crud.assign_theatre_character(db, current_user, character, data.username)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate atribui personaje")
    if error == "user_not_found":
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    if error == "not_member":
        raise HTTPException(status_code=409, detail="Utilizatorul nu este participant")
    _character_error(error)
    return _character_payload(updated)


@router.post("/api/teatru/{play_id}/scene", status_code=status.HTTP_201_CREATED)
def start_theatre_scene_api(
    play_id: int,
    data: schemas.TheatreSceneCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    scene, error = crud.start_theatre_scene(db, current_user, play, data)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate porni scena")
    if error == "scene_active":
        raise HTTPException(status_code=409, detail="Există deja o scenă activă")
    _character_error(error)
    if error == "character_not_ready":
        raise HTTPException(status_code=409, detail="Primul personaj trebuie să fie aprobat și atribuit")
    opening = next((entry for entry in scene.entries if entry.entry_type == "scene_opening"), None)
    if opening:
        ai_queue.enqueue_theatre_entry_moderation_job(db, opening)
    return _scene_payload(scene, include_pending=True)


@router.post("/api/teatru/{play_id}/scene/{scene_id}/replici", status_code=status.HTTP_201_CREATED)
def create_theatre_reply_api(
    play_id: int,
    scene_id: int,
    data: schemas.TheatreReplyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    scene = _load_scene_or_404(db, play, scene_id)
    entry, error = crud.create_theatre_reply(db, current_user, play, scene, data)
    if error == "scene_not_active":
        raise HTTPException(status_code=409, detail="Scena nu este activă")
    if error == "not_your_turn":
        raise HTTPException(status_code=403, detail="Nu este rândul tău")
    if error == "turn_pending":
        raise HTTPException(status_code=409, detail="Replica ta este încă în moderare")
    _character_error(error)
    ai_queue.enqueue_theatre_entry_moderation_job(db, entry)
    return _entry_payload(entry)


@router.post("/api/teatru/{play_id}/scene/{scene_id}/indicatii", status_code=status.HTTP_201_CREATED)
def create_theatre_stage_direction_api(
    play_id: int,
    scene_id: int,
    data: schemas.TheatreStageDirectionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    scene = _load_scene_or_404(db, play, scene_id)
    entry, error = crud.create_theatre_stage_direction(db, current_user, play, scene, data.content)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate adăuga indicații scenice")
    if error == "scene_not_active":
        raise HTTPException(status_code=409, detail="Scena nu este activă")
    ai_queue.enqueue_theatre_entry_moderation_job(db, entry)
    return _entry_payload(entry)


@router.post("/api/teatru/{play_id}/rand")
def override_theatre_turn_api(
    play_id: int,
    data: schemas.TheatreTurnOverride,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    character, error = crud.override_theatre_turn(db, current_user, play, data)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate schimba rândul")
    if error == "scene_not_active":
        raise HTTPException(status_code=409, detail="Nu există scenă activă")
    _character_error(error)
    if data.note:
        # The note is the most recent pending stage direction inserted by override.
        scene = crud.get_active_theatre_scene(db, play)
        if scene:
            pending = (
                db.query(models.TheatreEntry)
                .filter(
                    models.TheatreEntry.scene_id == scene.id,
                    models.TheatreEntry.entry_type == "stage_direction",
                    models.TheatreEntry.author_id == current_user.id,
                    models.TheatreEntry.moderation_status == "pending",
                )
                .order_by(models.TheatreEntry.id.desc())
                .first()
            )
            if pending:
                ai_queue.enqueue_theatre_entry_moderation_job(db, pending)
    return _character_payload(character)


@router.post("/api/teatru/{play_id}/scene/{scene_id}/incheie")
def end_theatre_scene_api(
    play_id: int,
    scene_id: int,
    data: schemas.TheatreSceneEnd,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    play = _load_play_or_404(db, play_id)
    scene = _load_scene_or_404(db, play, scene_id)
    updated, error = crud.end_theatre_scene(db, current_user, play, scene, data)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar creatorul poate încheia scena")
    if error == "scene_not_active":
        raise HTTPException(status_code=409, detail="Scena nu este activă")
    if data.content:
        pending = (
            db.query(models.TheatreEntry)
            .filter(
                models.TheatreEntry.scene_id == scene.id,
                models.TheatreEntry.entry_type == "scene_end",
                models.TheatreEntry.author_id == current_user.id,
                models.TheatreEntry.moderation_status == "pending",
            )
            .order_by(models.TheatreEntry.id.desc())
            .first()
        )
        if pending:
            ai_queue.enqueue_theatre_entry_moderation_job(db, pending)
    return _scene_payload(updated, include_pending=True)


@router.get("/api/utilizator/teatru")
def list_my_theatre_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    plays = crud.list_user_theatre_plays(db, current_user.id)
    return {"plays": [_play_summary_payload(db, play) for play in plays]}


@router.get("/api/utilizator/teatru/in-asteptare")
def list_my_theatre_invitations_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    invitations = crud.list_user_pending_theatre_invitations(db, current_user.id)
    return {
        "items": [
            {
                "request": _join_request_payload(invitation),
                "play": _play_summary_payload(db, invitation.play),
                "direction": invitation.direction,
            }
            for invitation in invitations
            if invitation.play
        ]
    }
