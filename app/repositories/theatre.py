from ._shared import *
from .notifications import create_notification
from .slugs import generate_slug
from .users import get_user_by_username


def _generate_theatre_slug(title: str) -> str:
    return generate_slug(title, fallback="teatru")


def _ensure_unique_theatre_slug(db: Session, base_slug: str) -> str:
    slug = base_slug or "teatru"
    counter = 1
    while db.query(models.TheatrePlay).filter(models.TheatrePlay.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _theatre_link(play: models.TheatrePlay) -> str:
    return f"/teatru/{play.slug}"


def get_theatre_play(db: Session, play_id: int) -> Optional[models.TheatrePlay]:
    return (
        db.query(models.TheatrePlay)
        .options(joinedload(models.TheatrePlay.creator))
        .filter(models.TheatrePlay.id == play_id)
        .first()
    )


def get_theatre_play_by_slug(db: Session, slug: str) -> Optional[models.TheatrePlay]:
    return (
        db.query(models.TheatrePlay)
        .options(
            joinedload(models.TheatrePlay.creator),
            joinedload(models.TheatrePlay.members).joinedload(models.TheatreMember.user),
            joinedload(models.TheatrePlay.characters).joinedload(models.TheatreCharacter.assigned_user),
            joinedload(models.TheatrePlay.characters).joinedload(models.TheatreCharacter.proposer),
            joinedload(models.TheatrePlay.scenes).joinedload(models.TheatreScene.entries).joinedload(models.TheatreEntry.author),
            joinedload(models.TheatrePlay.scenes).joinedload(models.TheatreScene.entries).joinedload(models.TheatreEntry.character),
            joinedload(models.TheatrePlay.scenes).joinedload(models.TheatreScene.entries).joinedload(models.TheatreEntry.next_character),
        )
        .filter(models.TheatrePlay.slug == slug)
        .first()
    )


def list_theatre_plays(db: Session, *, limit: int = 50, offset: int = 0) -> List[models.TheatrePlay]:
    return (
        db.query(models.TheatrePlay)
        .options(joinedload(models.TheatrePlay.creator))
        .order_by(models.TheatrePlay.updated_at.desc(), models.TheatrePlay.id.desc())
        .offset(max(0, offset))
        .limit(max(1, min(limit, 100)))
        .all()
    )


def get_theatre_membership(db: Session, play_id: int, user_id: int) -> Optional[models.TheatreMember]:
    return (
        db.query(models.TheatreMember)
        .filter(models.TheatreMember.play_id == play_id, models.TheatreMember.user_id == user_id)
        .first()
    )


def list_theatre_members(db: Session, play_id: int) -> List[models.TheatreMember]:
    role_priority = case((models.TheatreMember.role == "creator", 0), else_=1)
    return (
        db.query(models.TheatreMember)
        .options(joinedload(models.TheatreMember.user))
        .filter(models.TheatreMember.play_id == play_id)
        .order_by(role_priority.asc(), models.TheatreMember.joined_at.asc(), models.TheatreMember.id.asc())
        .all()
    )


def list_theatre_characters(db: Session, play_id: int) -> List[models.TheatreCharacter]:
    status_priority = case(
        (models.TheatreCharacter.status == "approved", 0),
        (models.TheatreCharacter.status == "pending", 1),
        else_=2,
    )
    return (
        db.query(models.TheatreCharacter)
        .options(
            joinedload(models.TheatreCharacter.assigned_user),
            joinedload(models.TheatreCharacter.proposer),
        )
        .filter(models.TheatreCharacter.play_id == play_id)
        .order_by(status_priority.asc(), models.TheatreCharacter.created_at.asc(), models.TheatreCharacter.id.asc())
        .all()
    )


def get_theatre_character(db: Session, character_id: int) -> Optional[models.TheatreCharacter]:
    return (
        db.query(models.TheatreCharacter)
        .options(
            joinedload(models.TheatreCharacter.play),
            joinedload(models.TheatreCharacter.assigned_user),
            joinedload(models.TheatreCharacter.proposer),
        )
        .filter(models.TheatreCharacter.id == character_id)
        .first()
    )


def get_active_theatre_scene(db: Session, play: models.TheatrePlay) -> Optional[models.TheatreScene]:
    if not play.current_scene_id:
        return None
    return (
        db.query(models.TheatreScene)
        .filter(
            models.TheatreScene.id == play.current_scene_id,
            models.TheatreScene.play_id == play.id,
            models.TheatreScene.status == "active",
        )
        .first()
    )


def list_theatre_scenes(db: Session, play_id: int) -> List[models.TheatreScene]:
    return (
        db.query(models.TheatreScene)
        .options(
            joinedload(models.TheatreScene.entries).joinedload(models.TheatreEntry.author),
            joinedload(models.TheatreScene.entries).joinedload(models.TheatreEntry.character),
            joinedload(models.TheatreScene.entries).joinedload(models.TheatreEntry.next_character),
        )
        .filter(models.TheatreScene.play_id == play_id)
        .order_by(models.TheatreScene.scene_number.asc())
        .all()
    )


def count_theatre_characters(db: Session, play_id: int) -> int:
    return db.query(models.TheatreCharacter).filter(models.TheatreCharacter.play_id == play_id).count()


def count_theatre_actors(db: Session, play_id: int) -> int:
    return db.query(models.TheatreMember).filter(models.TheatreMember.play_id == play_id).count()


def count_theatre_scenes(db: Session, play_id: int) -> int:
    return db.query(models.TheatreScene).filter(models.TheatreScene.play_id == play_id).count()


def count_pending_theatre_requests(db: Session, play_id: int) -> int:
    return (
        db.query(models.TheatreJoinRequest)
        .filter(models.TheatreJoinRequest.play_id == play_id, models.TheatreJoinRequest.status == "pending")
        .count()
    )


def count_pending_theatre_characters(db: Session, play_id: int) -> int:
    return (
        db.query(models.TheatreCharacter)
        .filter(models.TheatreCharacter.play_id == play_id, models.TheatreCharacter.status == "pending")
        .count()
    )


def get_user_pending_theatre_request(db: Session, play_id: int, user_id: int) -> Optional[models.TheatreJoinRequest]:
    return (
        db.query(models.TheatreJoinRequest)
        .filter(
            models.TheatreJoinRequest.play_id == play_id,
            models.TheatreJoinRequest.user_id == user_id,
            models.TheatreJoinRequest.status == "pending",
        )
        .first()
    )


def list_theatre_pending_requests(db: Session, play_id: int) -> List[models.TheatreJoinRequest]:
    return (
        db.query(models.TheatreJoinRequest)
        .options(
            joinedload(models.TheatreJoinRequest.user),
            joinedload(models.TheatreJoinRequest.character).joinedload(models.TheatreCharacter.assigned_user),
            joinedload(models.TheatreJoinRequest.character).joinedload(models.TheatreCharacter.proposer),
        )
        .filter(models.TheatreJoinRequest.play_id == play_id, models.TheatreJoinRequest.status == "pending")
        .order_by(models.TheatreJoinRequest.created_at.desc(), models.TheatreJoinRequest.id.desc())
        .all()
    )


def get_theatre_join_request(db: Session, request_id: int) -> Optional[models.TheatreJoinRequest]:
    return (
        db.query(models.TheatreJoinRequest)
        .options(
            joinedload(models.TheatreJoinRequest.play),
            joinedload(models.TheatreJoinRequest.user),
            joinedload(models.TheatreJoinRequest.initiator),
            joinedload(models.TheatreJoinRequest.character).joinedload(models.TheatreCharacter.assigned_user),
            joinedload(models.TheatreJoinRequest.character).joinedload(models.TheatreCharacter.proposer),
        )
        .filter(models.TheatreJoinRequest.id == request_id)
        .first()
    )


def list_user_theatre_plays(db: Session, user_id: int) -> List[models.TheatrePlay]:
    return (
        db.query(models.TheatrePlay)
        .options(joinedload(models.TheatrePlay.creator))
        .join(models.TheatreMember, models.TheatreMember.play_id == models.TheatrePlay.id)
        .filter(models.TheatreMember.user_id == user_id)
        .order_by(models.TheatrePlay.updated_at.desc(), models.TheatrePlay.id.desc())
        .all()
    )


def list_user_pending_theatre_invitations(db: Session, user_id: int) -> List[models.TheatreJoinRequest]:
    return (
        db.query(models.TheatreJoinRequest)
        .options(
            joinedload(models.TheatreJoinRequest.play).joinedload(models.TheatrePlay.creator),
            joinedload(models.TheatreJoinRequest.user),
            joinedload(models.TheatreJoinRequest.character),
        )
        .filter(
            models.TheatreJoinRequest.user_id == user_id,
            models.TheatreJoinRequest.status == "pending",
            models.TheatreJoinRequest.direction == "invitation",
        )
        .order_by(models.TheatreJoinRequest.created_at.desc(), models.TheatreJoinRequest.id.desc())
        .all()
    )


def _user_has_assigned_theatre_character(
    db: Session,
    play_id: int,
    user_id: int,
    *,
    exclude_character_id: Optional[int] = None,
) -> bool:
    query = db.query(models.TheatreCharacter.id).filter(
        models.TheatreCharacter.play_id == play_id,
        models.TheatreCharacter.assigned_user_id == user_id,
        models.TheatreCharacter.status == "approved",
    )
    if exclude_character_id is not None:
        query = query.filter(models.TheatreCharacter.id != exclude_character_id)
    return query.first() is not None


def _character_has_pending_theatre_request(
    db: Session,
    play_id: int,
    character_id: int,
    *,
    exclude_request_id: Optional[int] = None,
) -> bool:
    query = db.query(models.TheatreJoinRequest.id).filter(
        models.TheatreJoinRequest.play_id == play_id,
        models.TheatreJoinRequest.character_id == character_id,
        models.TheatreJoinRequest.status == "pending",
    )
    if exclude_request_id is not None:
        query = query.filter(models.TheatreJoinRequest.id != exclude_request_id)
    return query.first() is not None


def _member_user_ids(db: Session, play_id: int) -> list[int]:
    return [
        row[0]
        for row in db.query(models.TheatreMember.user_id)
        .filter(models.TheatreMember.play_id == play_id)
        .all()
    ]


def _ensure_character_is_available(
    db: Session,
    character: Optional[models.TheatreCharacter],
    play_id: int,
    *,
    require_approved: bool = True,
    ignore_request_id: Optional[int] = None,
) -> Optional[str]:
    if not character or character.play_id != play_id:
        return "character_not_found"
    if require_approved and character.status != "approved":
        return "character_not_approved"
    if character.assigned_user_id is not None:
        return "character_unavailable"
    if _character_has_pending_theatre_request(db, play_id, character.id, exclude_request_id=ignore_request_id):
        return "character_has_pending_request"
    return None


def create_theatre_play(db: Session, creator: models.User, data: schemas.TheatrePlayCreate) -> models.TheatrePlay:
    if creator.is_suspended:
        raise ValueError("suspended")

    seen_names = set()
    for character in data.characters:
        key = character.name.strip().lower()
        if key in seen_names:
            raise ValueError("duplicate_character")
        seen_names.add(key)

    play = models.TheatrePlay(
        creator_id=creator.id,
        title=data.title.strip(),
        slug=_ensure_unique_theatre_slug(db, _generate_theatre_slug(data.title)),
        description=(data.description or "").strip() or None,
        status="setup",
    )
    db.add(play)
    db.flush()
    db.add(models.TheatreMember(play_id=play.id, user_id=creator.id, role="creator"))

    pending_invites: list[tuple[models.User, models.TheatreCharacter]] = []
    assigned_user_ids: set[int] = set()
    for item in data.characters:
        character = models.TheatreCharacter(
            play_id=play.id,
            name=item.name.strip(),
            description=item.description.strip(),
            status="approved",
            proposed_by=creator.id,
            approved_by=creator.id,
            approved_at=utcnow_naive(),
        )
        db.add(character)
        db.flush()
        if item.assigned_username:
            target = get_user_by_username(db, item.assigned_username)
            if not target:
                raise ValueError("assigned_user_not_found")
            if target.id == creator.id:
                if target.id in assigned_user_ids:
                    raise ValueError("user_already_assigned")
                character.assigned_user_id = creator.id
                assigned_user_ids.add(target.id)
            else:
                request = models.TheatreJoinRequest(
                    play_id=play.id,
                    user_id=target.id,
                    direction="invitation",
                    status="pending",
                    initiator_id=creator.id,
                    character_id=character.id,
                )
                db.add(request)
                pending_invites.append((target, character))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("duplicate_character") from exc
    db.refresh(play)
    for target, character in pending_invites:
        _notify_theatre_invitation(db, play, creator, target, character)
    return play


def update_theatre_play(db: Session, play: models.TheatrePlay, actor: models.User, data: schemas.TheatrePlayUpdate) -> tuple[Optional[models.TheatrePlay], Optional[str]]:
    if play.creator_id != actor.id:
        return None, "not_allowed"
    payload = data.model_dump(exclude_unset=True)
    if "title" in payload and payload["title"]:
        play.title = payload["title"].strip()
    if "description" in payload:
        play.description = (payload["description"] or "").strip() or None
    if "status" in payload and payload["status"]:
        play.status = payload["status"]
        if payload["status"] == "completed":
            play.current_scene_id = None
            play.current_character_id = None
            play.current_actor_user_id = None
    db.commit()
    db.refresh(play)
    return play, None


def delete_theatre_play(db: Session, play: models.TheatrePlay, actor: models.User) -> tuple[bool, Optional[str]]:
    if play.creator_id != actor.id:
        return False, "not_allowed"
    db.delete(play)
    db.commit()
    return True, None


def delete_theatre_character(
    db: Session,
    actor: models.User,
    character: models.TheatreCharacter,
) -> tuple[bool, Optional[str]]:
    play = character.play
    if not play or play.creator_id != actor.id:
        return False, "not_allowed"
    if play.current_character_id == character.id:
        return False, "character_in_use"
    in_use = db.query(models.TheatreEntry.id).filter(
        models.TheatreEntry.play_id == play.id,
        or_(
            models.TheatreEntry.character_id == character.id,
            models.TheatreEntry.next_character_id == character.id,
        ),
    ).first()
    if in_use:
        return False, "character_in_use"
    for request in db.query(models.TheatreJoinRequest).filter(
        models.TheatreJoinRequest.play_id == play.id,
        models.TheatreJoinRequest.character_id == character.id,
        models.TheatreJoinRequest.status == "pending",
    ).all():
        request.status = "rejected"
        request.responded_by = actor.id
        request.responded_at = utcnow_naive()
    db.delete(character)
    db.commit()
    return True, None


def apply_to_theatre_play(
    db: Session,
    applicant: models.User,
    play: models.TheatrePlay,
    data: schemas.TheatreJoinApply,
) -> tuple[Optional[models.TheatreJoinRequest], Optional[str]]:
    if applicant.is_suspended:
        return None, "suspended"
    if get_theatre_membership(db, play.id, applicant.id):
        return None, "already_member"
    if data.character_id and data.proposed_character:
        return None, "too_many_characters"

    character = None
    if data.character_id:
        character = get_theatre_character(db, data.character_id)
        error = _ensure_character_is_available(db, character, play.id)
        if error:
            return None, error
    elif data.proposed_character:
        character = models.TheatreCharacter(
            play_id=play.id,
            name=data.proposed_character.name.strip(),
            description=data.proposed_character.description.strip(),
            status="pending",
            proposed_by=applicant.id,
        )
        db.add(character)
        db.flush()

    request = models.TheatreJoinRequest(
        play_id=play.id,
        user_id=applicant.id,
        direction="application",
        status="pending",
        initiator_id=applicant.id,
        character_id=character.id if character else None,
        note=data.note,
    )
    db.add(request)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("duplicate_character") from exc
    db.refresh(request)
    _notify_theatre_application(db, play, applicant, request)
    return request, None


def invite_to_theatre_play(
    db: Session,
    inviter: models.User,
    play: models.TheatrePlay,
    target: models.User,
    data: schemas.TheatreInvite,
) -> tuple[Optional[models.TheatreJoinRequest], Optional[str]]:
    if play.creator_id != inviter.id:
        return None, "not_allowed"
    if target.is_suspended:
        return None, "target_suspended"
    if get_theatre_membership(db, play.id, target.id):
        return None, "already_member"
    character = None
    if data.character_id:
        character = get_theatre_character(db, data.character_id)
        error = _ensure_character_is_available(db, character, play.id)
        if error:
            return None, error
    request = models.TheatreJoinRequest(
        play_id=play.id,
        user_id=target.id,
        direction="invitation",
        status="pending",
        initiator_id=inviter.id,
        character_id=character.id if character else None,
        note=data.note,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    _notify_theatre_invitation(db, play, inviter, target, character)
    return request, None


def respond_to_theatre_request(
    db: Session,
    request: models.TheatreJoinRequest,
    responder: models.User,
    action: str,
) -> tuple[Optional[models.TheatreJoinRequest], Optional[str]]:
    if action not in ("approve", "reject"):
        return None, "bad_action"
    if request.status != "pending":
        return None, "not_pending"
    play = request.play
    character = request.character
    if request.direction == "application":
        if play.creator_id != responder.id:
            return None, "not_allowed"
    elif request.direction == "invitation":
        if responder.id != request.user_id:
            return None, "not_allowed"
    else:
        return None, "bad_direction"

    if action == "approve":
        if character:
            if character.status == "pending":
                character.status = "approved"
                character.approved_by = responder.id
                character.approved_at = utcnow_naive()
            error = _ensure_character_is_available(db, character, play.id, require_approved=True, ignore_request_id=request.id)
            if error:
                return None, error
            if _user_has_assigned_theatre_character(db, play.id, request.user_id, exclude_character_id=character.id):
                return None, "user_already_assigned"
        if not get_theatre_membership(db, play.id, request.user_id):
            db.add(models.TheatreMember(play_id=play.id, user_id=request.user_id, role="actor"))
        if character:
            character.assigned_user_id = request.user_id
        request.status = "approved"
    else:
        if character and character.status == "pending" and character.proposed_by == request.user_id:
            character.status = "rejected"
            character.approved_by = responder.id
            character.approved_at = utcnow_naive()
        request.status = "rejected"

    request.responded_at = utcnow_naive()
    request.responded_by = responder.id
    db.commit()
    db.refresh(request)
    _notify_theatre_request_outcome(db, request, action, responder)
    return request, None


def create_theatre_character(
    db: Session,
    actor: models.User,
    play: models.TheatrePlay,
    data: schemas.TheatreCharacterCreate,
) -> tuple[Optional[models.TheatreCharacter], Optional[str]]:
    membership = get_theatre_membership(db, play.id, actor.id)
    if not membership:
        return None, "not_member"
    is_creator = play.creator_id == actor.id
    character = models.TheatreCharacter(
        play_id=play.id,
        name=data.name.strip(),
        description=data.description.strip(),
        status="approved" if is_creator else "pending",
        proposed_by=actor.id,
        approved_by=actor.id if is_creator else None,
        approved_at=utcnow_naive() if is_creator else None,
    )
    db.add(character)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("duplicate_character") from exc
    db.refresh(character)
    if not is_creator:
        _notify_theatre_character_request(db, play, actor, character)
    return character, None


def review_theatre_character(
    db: Session,
    actor: models.User,
    character: models.TheatreCharacter,
    action: str,
) -> tuple[Optional[models.TheatreCharacter], Optional[str]]:
    play = character.play
    if not play or play.creator_id != actor.id:
        return None, "not_allowed"
    if character.status != "pending":
        return None, "not_pending"
    if action == "approve":
        character.status = "approved"
        character.approved_by = actor.id
        character.approved_at = utcnow_naive()
        if (
            character.proposed_by
            and get_theatre_membership(db, play.id, character.proposed_by)
            and not character.assigned_user_id
            and not _user_has_assigned_theatre_character(db, play.id, character.proposed_by, exclude_character_id=character.id)
        ):
            character.assigned_user_id = character.proposed_by
    elif action == "reject":
        character.status = "rejected"
        character.approved_by = actor.id
        character.approved_at = utcnow_naive()
    else:
        return None, "bad_action"
    db.commit()
    db.refresh(character)
    if character.proposed_by:
        create_notification(
            db=db,
            user_id=character.proposed_by,
            notif_type="theatre_character_approved" if action == "approve" else "theatre_character_rejected",
            title="Personaj aprobat" if action == "approve" else "Personaj respins",
            message=(
                f"Personajul „{character.name}\" a fost aprobat în piesa „{play.title}\"."
                if action == "approve"
                else f"Personajul „{character.name}\" a fost respins în piesa „{play.title}\"."
            ),
            link=_theatre_link(play),
            extra_data={"play_id": play.id, "play_slug": play.slug, "character_id": character.id},
        )
    return character, None


def assign_theatre_character(
    db: Session,
    actor: models.User,
    character: models.TheatreCharacter,
    username: str,
) -> tuple[Optional[models.TheatreCharacter], Optional[str]]:
    play = character.play
    if not play or play.creator_id != actor.id:
        return None, "not_allowed"
    if character.status != "approved":
        return None, "character_not_approved"
    target = get_user_by_username(db, username.strip())
    if not target:
        return None, "user_not_found"
    if not get_theatre_membership(db, play.id, target.id):
        return None, "not_member"
    if character.assigned_user_id and character.assigned_user_id != target.id:
        return None, "character_unavailable"
    if _user_has_assigned_theatre_character(db, play.id, target.id, exclude_character_id=character.id):
        return None, "user_already_assigned"
    character.assigned_user_id = target.id
    db.commit()
    db.refresh(character)
    create_notification(
        db=db,
        user_id=target.id,
        notif_type="theatre_character_assigned",
        title="Personaj atribuit",
        message=f"Ai primit personajul „{character.name}\" în piesa „{play.title}\".",
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "character_id": character.id},
    )
    return character, None


def _next_scene_number(db: Session, play_id: int) -> int:
    current = db.query(func.coalesce(func.max(models.TheatreScene.scene_number), 0)).filter(
        models.TheatreScene.play_id == play_id
    ).scalar()
    return int(current or 0) + 1


def _next_entry_position(db: Session, scene_id: int) -> int:
    current = db.query(func.coalesce(func.max(models.TheatreEntry.position), 0)).filter(
        models.TheatreEntry.scene_id == scene_id
    ).scalar()
    return int(current or 0) + 1


def start_theatre_scene(
    db: Session,
    actor: models.User,
    play: models.TheatrePlay,
    data: schemas.TheatreSceneCreate,
) -> tuple[Optional[models.TheatreScene], Optional[str]]:
    if play.creator_id != actor.id:
        return None, "not_allowed"
    if get_active_theatre_scene(db, play):
        return None, "scene_active"
    first_character = get_theatre_character(db, data.first_character_id)
    if not first_character or first_character.play_id != play.id:
        return None, "character_not_found"
    if first_character.status != "approved" or not first_character.assigned_user_id:
        return None, "character_not_ready"
    scene = models.TheatreScene(
        play_id=play.id,
        scene_number=_next_scene_number(db, play.id),
        title=data.title.strip(),
        status="active",
        opened_by=actor.id,
    )
    db.add(scene)
    db.flush()
    entry = models.TheatreEntry(
        play_id=play.id,
        scene_id=scene.id,
        author_id=actor.id,
        entry_type="scene_opening",
        content=data.content,
        next_character_id=first_character.id,
        position=1,
        moderation_status="pending",
    )
    db.add(entry)
    play.status = "active"
    play.current_scene_id = scene.id
    play.current_character_id = None
    play.current_actor_user_id = None
    db.commit()
    db.refresh(scene)
    return scene, None


def create_theatre_reply(
    db: Session,
    actor: models.User,
    play: models.TheatrePlay,
    scene: models.TheatreScene,
    data: schemas.TheatreReplyCreate,
) -> tuple[Optional[models.TheatreEntry], Optional[str]]:
    if scene.play_id != play.id or scene.status != "active":
        return None, "scene_not_active"
    if play.current_actor_user_id != actor.id or not play.current_character_id:
        return None, "not_your_turn"
    current_character = get_theatre_character(db, play.current_character_id)
    if not current_character or current_character.assigned_user_id != actor.id:
        return None, "not_your_turn"
    next_character = get_theatre_character(db, data.next_character_id)
    if not next_character or next_character.play_id != play.id:
        return None, "next_character_not_found"
    if next_character.status != "approved" or not next_character.assigned_user_id:
        return None, "next_character_not_ready"
    pending_turn = (
        db.query(models.TheatreEntry)
        .filter(
            models.TheatreEntry.scene_id == scene.id,
            models.TheatreEntry.entry_type == "line",
            models.TheatreEntry.author_id == actor.id,
            models.TheatreEntry.character_id == current_character.id,
            models.TheatreEntry.moderation_status == "pending",
        )
        .first()
    )
    if pending_turn:
        return None, "turn_pending"
    entry = models.TheatreEntry(
        play_id=play.id,
        scene_id=scene.id,
        author_id=actor.id,
        character_id=current_character.id,
        next_character_id=next_character.id,
        entry_type="line",
        content=data.content,
        position=_next_entry_position(db, scene.id),
        moderation_status="pending",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry, None


def create_theatre_stage_direction(
    db: Session,
    actor: models.User,
    play: models.TheatrePlay,
    scene: models.TheatreScene,
    content: str,
) -> tuple[Optional[models.TheatreEntry], Optional[str]]:
    if play.creator_id != actor.id:
        return None, "not_allowed"
    if scene.play_id != play.id or scene.status != "active":
        return None, "scene_not_active"
    entry = models.TheatreEntry(
        play_id=play.id,
        scene_id=scene.id,
        author_id=actor.id,
        entry_type="stage_direction",
        content=content,
        position=_next_entry_position(db, scene.id),
        moderation_status="pending",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry, None


def override_theatre_turn(
    db: Session,
    actor: models.User,
    play: models.TheatrePlay,
    data: schemas.TheatreTurnOverride,
) -> tuple[Optional[models.TheatreCharacter], Optional[str]]:
    if play.creator_id != actor.id:
        return None, "not_allowed"
    scene = get_active_theatre_scene(db, play)
    if not scene:
        return None, "scene_not_active"
    character = get_theatre_character(db, data.character_id)
    if not character or character.play_id != play.id:
        return None, "character_not_found"
    if character.status != "approved" or not character.assigned_user_id:
        return None, "character_not_ready"
    play.current_character_id = character.id
    play.current_actor_user_id = character.assigned_user_id
    if data.note:
        db.add(
            models.TheatreEntry(
                play_id=play.id,
                scene_id=scene.id,
                author_id=actor.id,
                entry_type="stage_direction",
                content=data.note,
                position=_next_entry_position(db, scene.id),
                moderation_status="pending",
            )
        )
    db.commit()
    db.refresh(character)
    _notify_theatre_turn(db, play, character, "theatre_turn_override")
    return character, None


def end_theatre_scene(
    db: Session,
    actor: models.User,
    play: models.TheatrePlay,
    scene: models.TheatreScene,
    data: schemas.TheatreSceneEnd,
) -> tuple[Optional[models.TheatreScene], Optional[str]]:
    if play.creator_id != actor.id:
        return None, "not_allowed"
    if scene.play_id != play.id or scene.status != "active":
        return None, "scene_not_active"
    scene.status = "ended"
    scene.ended_by = actor.id
    scene.ended_at = utcnow_naive()
    play.current_scene_id = None
    play.current_character_id = None
    play.current_actor_user_id = None
    if data.content:
        db.add(
            models.TheatreEntry(
                play_id=play.id,
                scene_id=scene.id,
                author_id=actor.id,
                entry_type="scene_end",
                content=data.content,
                position=_next_entry_position(db, scene.id),
                moderation_status="pending",
            )
        )
    db.commit()
    db.refresh(scene)
    _notify_theatre_scene_ended(db, play, scene, actor.id)
    return scene, None


def get_theatre_entry(db: Session, entry_id: int) -> Optional[models.TheatreEntry]:
    return (
        db.query(models.TheatreEntry)
        .options(
            joinedload(models.TheatreEntry.play),
            joinedload(models.TheatreEntry.scene),
            joinedload(models.TheatreEntry.author),
            joinedload(models.TheatreEntry.character),
            joinedload(models.TheatreEntry.next_character),
        )
        .filter(models.TheatreEntry.id == entry_id)
        .first()
    )


def list_theatre_entries_for_moderation(
    db: Session,
    status_filter: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> List[models.TheatreEntry]:
    query = db.query(models.TheatreEntry).options(
        joinedload(models.TheatreEntry.author),
        joinedload(models.TheatreEntry.play),
        joinedload(models.TheatreEntry.scene),
        joinedload(models.TheatreEntry.character),
    )
    if status_filter:
        query = query.filter(models.TheatreEntry.moderation_status == status_filter)
    return (
        query.order_by(models.TheatreEntry.created_at.desc(), models.TheatreEntry.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def apply_theatre_entry_moderation_result(
    db: Session,
    entry: models.TheatreEntry,
    moderation_result,
    *,
    moderator_id: Optional[int] = None,
    reason: Optional[str] = None,
) -> models.TheatreEntry:
    was_approved = entry.moderation_status == "approved"
    status = getattr(moderation_result, "status", "approved")
    entry.moderation_status = getattr(status, "value", status)
    entry.toxicity_score = getattr(moderation_result, "toxicity_score", None)
    entry.moderation_reason = reason or getattr(moderation_result, "reason", None)
    if moderator_id is not None:
        entry.moderated_by = moderator_id
        entry.moderated_at = utcnow_naive()
    db.commit()
    db.refresh(entry)
    if entry.moderation_status == "approved" and not was_approved:
        _after_theatre_entry_approved(db, entry)
    elif entry.moderation_status == "flagged":
        _notify_theatre_entry_flagged(db, entry)
    elif entry.moderation_status == "rejected":
        _notify_theatre_entry_rejected(db, entry)
    return entry


def _after_theatre_entry_approved(db: Session, entry: models.TheatreEntry) -> None:
    play = entry.play or get_theatre_play(db, entry.play_id)
    if not play:
        return
    if entry.entry_type in ("scene_opening", "line") and entry.next_character_id:
        next_character = get_theatre_character(db, entry.next_character_id)
        if next_character and next_character.status == "approved" and next_character.assigned_user_id:
            active_scene = get_active_theatre_scene(db, play)
            if active_scene and active_scene.id == entry.scene_id:
                play.current_character_id = next_character.id
                play.current_actor_user_id = next_character.assigned_user_id
                db.commit()
                db.refresh(play)
                _notify_theatre_turn(db, play, next_character, "theatre_turn_assigned")
    if entry.entry_type == "line":
        _notify_theatre_new_entry(db, play, entry, "Replică nouă în piesă")
    elif entry.entry_type == "stage_direction":
        _notify_theatre_new_entry(db, play, entry, "Indicație scenică nouă")
    elif entry.entry_type == "scene_opening":
        _notify_theatre_new_entry(db, play, entry, "Scenă nouă în piesă")
    elif entry.entry_type == "scene_end":
        _notify_theatre_new_entry(db, play, entry, "Scenă încheiată")


def _notify_theatre_turn(db: Session, play: models.TheatrePlay, character: models.TheatreCharacter, notif_type: str) -> None:
    if not character.assigned_user_id:
        return
    create_notification(
        db=db,
        user_id=character.assigned_user_id,
        notif_type=notif_type,
        title="Este rândul tău",
        message=f"Personajul „{character.name}\" trebuie să continue piesa „{play.title}\".",
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "character_id": character.id},
    )


def _notify_theatre_new_entry(db: Session, play: models.TheatrePlay, entry: models.TheatreEntry, title: str) -> None:
    author_name = entry.author.username if entry.author else "Un participant"
    for user_id in _member_user_ids(db, play.id):
        if user_id == entry.author_id:
            continue
        create_notification(
            db=db,
            user_id=user_id,
            notif_type="theatre_entry_approved",
            title=title,
            message=f"{author_name} a adăugat conținut în „{play.title}\".",
            link=_theatre_link(play),
            extra_data={"play_id": play.id, "play_slug": play.slug, "entry_id": entry.id},
        )


def _notify_theatre_entry_flagged(db: Session, entry: models.TheatreEntry) -> None:
    play = entry.play or get_theatre_play(db, entry.play_id)
    if not play:
        return
    create_notification(
        db=db,
        user_id=entry.author_id,
        notif_type="theatre_entry_flagged",
        title="Text în curs de moderare",
        message=f"Textul tău din piesa „{play.title}\" a fost trimis pentru revizuire manuală.",
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "entry_id": entry.id},
    )


def _notify_theatre_entry_rejected(db: Session, entry: models.TheatreEntry) -> None:
    play = entry.play or get_theatre_play(db, entry.play_id)
    if not play:
        return
    create_notification(
        db=db,
        user_id=entry.author_id,
        notif_type="theatre_entry_rejected",
        title="Text respins",
        message=f"Textul tău din piesa „{play.title}\" a fost respins.",
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "entry_id": entry.id},
    )


def _notify_theatre_application(db: Session, play: models.TheatrePlay, applicant: models.User, request: models.TheatreJoinRequest) -> None:
    create_notification(
        db=db,
        user_id=play.creator_id,
        notif_type="theatre_application_received",
        title="Cerere pentru teatru colaborativ",
        message=f"{applicant.username} dorește să participe la piesa „{play.title}\".",
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "request_id": request.id},
    )


def _notify_theatre_invitation(
    db: Session,
    play: models.TheatrePlay,
    inviter: models.User,
    target: models.User,
    character: Optional[models.TheatreCharacter],
) -> None:
    character_text = f" ca „{character.name}\"" if character else ""
    create_notification(
        db=db,
        user_id=target.id,
        notif_type="theatre_invitation_received",
        title="Invitație la teatru colaborativ",
        message=f"{inviter.username} te-a invitat în piesa „{play.title}\"{character_text}.",
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "character_id": character.id if character else None},
    )


def _notify_theatre_request_outcome(
    db: Session,
    request: models.TheatreJoinRequest,
    action: str,
    responder: models.User,
) -> None:
    play = request.play
    if request.direction == "application":
        target_user_id = request.user_id
        title = "Cerere acceptată" if action == "approve" else "Cerere respinsă"
        message = (
            f"Poți participa acum la piesa „{play.title}\"."
            if action == "approve"
            else f"Cererea ta pentru piesa „{play.title}\" a fost respinsă."
        )
        notif_type = "theatre_application_approved" if action == "approve" else "theatre_application_rejected"
    else:
        target_user_id = request.initiator_id
        title = "Invitație acceptată" if action == "approve" else "Invitație refuzată"
        message = (
            f"{request.user.username} a acceptat invitația în piesa „{play.title}\"."
            if action == "approve"
            else f"{request.user.username} a refuzat invitația în piesa „{play.title}\"."
        )
        notif_type = "theatre_invitation_accepted" if action == "approve" else "theatre_invitation_declined"
    create_notification(
        db=db,
        user_id=target_user_id,
        notif_type=notif_type,
        title=title,
        message=message,
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "request_id": request.id},
    )


def _notify_theatre_character_request(
    db: Session,
    play: models.TheatrePlay,
    proposer: models.User,
    character: models.TheatreCharacter,
) -> None:
    create_notification(
        db=db,
        user_id=play.creator_id,
        notif_type="theatre_character_requested",
        title="Personaj nou propus",
        message=f"{proposer.username} a propus personajul „{character.name}\" în piesa „{play.title}\".",
        link=_theatre_link(play),
        extra_data={"play_id": play.id, "play_slug": play.slug, "character_id": character.id},
    )


def _notify_theatre_scene_ended(
    db: Session,
    play: models.TheatrePlay,
    scene: models.TheatreScene,
    actor_id: int,
) -> None:
    for user_id in _member_user_ids(db, play.id):
        if user_id == actor_id:
            continue
        create_notification(
            db=db,
            user_id=user_id,
            notif_type="theatre_scene_ended",
            title="Scenă încheiată",
            message=f"Scena „{scene.title}\" din piesa „{play.title}\" a fost încheiată.",
            link=_theatre_link(play),
            extra_data={"play_id": play.id, "play_slug": play.slug, "scene_id": scene.id},
        )
