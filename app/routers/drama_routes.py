import logging
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import models, schemas, crud, auth, statistics
from ..database import get_db
from ..utils import get_client_ip

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["dramas"])


# ---------------------------------------------------------------------------
# Helper: serialize a Drama ORM object to dict
# ---------------------------------------------------------------------------

def _serialize_drama(drama: models.Drama) -> dict:
    characters = []
    for ch in drama.characters:
        characters.append({
            "id": ch.id,
            "drama_id": ch.drama_id,
            "user_id": ch.user_id,
            "character_name": ch.character_name,
            "character_description": ch.character_description,
            "is_creator": ch.is_creator,
            "joined_at": ch.joined_at.isoformat(),
            "username": ch.user.username if ch.user else None,
            "avatar_seed": ch.user.avatar_seed if ch.user else None,
        })

    acts = []
    for act in sorted(drama.acts, key=lambda a: a.act_number):
        replies = []
        for reply in sorted(act.replies, key=lambda r: r.position):
            replies.append({
                "id": reply.id,
                "act_id": reply.act_id,
                "character_id": reply.character_id,
                "content": reply.content,
                "stage_direction": reply.stage_direction,
                "position": reply.position,
                "created_at": reply.created_at.isoformat(),
                "character_name": reply.character.character_name if reply.character else None,
                "username": reply.character.user.username if (reply.character and reply.character.user) else None,
            })
        acts.append({
            "id": act.id,
            "drama_id": act.drama_id,
            "act_number": act.act_number,
            "title": act.title,
            "setting": act.setting,
            "status": act.status,
            "created_at": act.created_at.isoformat(),
            "replies": replies,
        })

    return {
        "id": drama.id,
        "user_id": drama.user_id,
        "title": drama.title,
        "slug": drama.slug,
        "description": drama.description,
        "status": drama.status,
        "is_open_for_applications": drama.is_open_for_applications,
        "view_count": drama.view_count,
        "likes_count": drama.likes_count,
        "created_at": drama.created_at.isoformat(),
        "updated_at": drama.updated_at.isoformat(),
        "owner_username": drama.owner.username if drama.owner else None,
        "owner_avatar_seed": drama.owner.avatar_seed if drama.owner else None,
        "characters": characters,
        "acts": acts,
    }


# ===========================================================================
# DRAMA CRUD
# ===========================================================================

@router.post("/api/dramas/")
@limiter.limit("20/minute")
async def create_drama(
    request: Request,
    drama_data: schemas.DramaCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Create a new drama (the creator also becomes the first character)."""
    base_slug = crud.generate_slug(drama_data.title)
    slug = crud.ensure_unique_drama_slug(db, base_slug)

    drama = crud.create_drama(
        db=db,
        title=drama_data.title,
        description=drama_data.description,
        slug=slug,
        user_id=current_user.id,
        character_name=drama_data.character_name,
        character_description=drama_data.character_description,
    )

    # Reload with relationships
    drama = crud.get_drama_by_slug(db, drama.slug)
    return _serialize_drama(drama)


@router.get("/api/dramas/{slug}")
async def get_drama(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Get full drama detail including characters, acts, and replies."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")

    statistics.record_view(db, request, "drama", drama.id, drama.slug, drama.user_id, current_user)
    return _serialize_drama(drama)


@router.put("/api/dramas/{slug}")
@limiter.limit("20/minute")
async def update_drama(
    request: Request,
    slug: str,
    drama_update: schemas.DramaUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Update drama metadata (owner only)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu ești autorizat să editezi această piesă")

    update_data = drama_update.model_dump(exclude_none=True)
    crud.update_drama(db, drama.id, update_data)

    drama = crud.get_drama_by_slug(db, slug)
    return _serialize_drama(drama)


@router.delete("/api/dramas/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drama(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Delete drama (owner only)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu ești autorizat să ștergi această piesă")

    crud.delete_drama(db, drama.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/dramas/{slug}/complete")
@limiter.limit("20/minute")
async def complete_drama(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Mark drama as completed (owner only). Notifies all participants."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Nu ești autorizat să închei această piesă")
    if drama.status == "completed":
        raise HTTPException(status_code=400, detail="Piesa de teatru este deja încheiată")

    drama = crud.complete_drama(db, drama.id)

    # Notify all participants (excluding the owner who triggered the action)
    for character in drama.characters:
        if character.user_id != current_user.id:
            crud.create_notification(
                db=db,
                user_id=character.user_id,
                notif_type="drama_completed",
                title="Piesă de teatru încheiată",
                message=f'Piesa "{drama.title}" a fost marcată ca încheiată.',
                link=f"/piese/{drama.slug}",
                extra_data={"drama_id": drama.id, "drama_slug": drama.slug},
            )

    return _serialize_drama(drama)


# ===========================================================================
# CHARACTERS & PARTICIPATION
# ===========================================================================

@router.post("/api/dramas/{slug}/invite")
@limiter.limit("20/minute")
async def invite_to_drama(
    request: Request,
    slug: str,
    invitation_data: schemas.InvitationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Send an invitation to join a drama (owner only)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar autorul poate trimite invitații")

    target_user = crud.get_user_by_username(db, invitation_data.to_username)
    if not target_user:
        raise HTTPException(status_code=404, detail="Utilizatorul invitat nu a fost găsit")
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Nu te poți invita pe tine însuți")

    # Check that user is not already a character in this drama
    existing_char = crud.get_character_for_user_in_drama(db, drama.id, target_user.id)
    if existing_char:
        raise HTTPException(status_code=409, detail="Utilizatorul este deja participant la această piesă")

    invitation = crud.create_drama_invitation(
        db=db,
        drama_id=drama.id,
        from_user_id=current_user.id,
        to_user_id=target_user.id,
        inv_type="invitation",
        character_name=invitation_data.character_name,
        message=invitation_data.message,
    )

    crud.create_notification(
        db=db,
        user_id=target_user.id,
        notif_type="drama_invitation",
        title="Invitație la piesă de teatru",
        message=f'{current_user.username} te-a invitat să participi la piesa "{drama.title}".',
        link=f"/piese/{drama.slug}",
        extra_data={"drama_id": drama.id, "invitation_id": invitation.id},
    )

    return {
        "id": invitation.id,
        "drama_id": invitation.drama_id,
        "from_user_id": invitation.from_user_id,
        "to_user_id": invitation.to_user_id,
        "type": invitation.type,
        "character_name": invitation.character_name,
        "message": invitation.message,
        "status": invitation.status,
        "created_at": invitation.created_at.isoformat(),
    }


@router.post("/api/dramas/{slug}/apply")
@limiter.limit("20/minute")
async def apply_to_drama(
    request: Request,
    slug: str,
    application_data: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Apply to join a drama as a participant."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if not drama.is_open_for_applications:
        raise HTTPException(status_code=403, detail="Această piesă nu acceptă cereri noi")
    if drama.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Ești deja autorul acestei piese")

    existing_char = crud.get_character_for_user_in_drama(db, drama.id, current_user.id)
    if existing_char:
        raise HTTPException(status_code=409, detail="Ești deja participant la această piesă")

    invitation = crud.create_drama_invitation(
        db=db,
        drama_id=drama.id,
        from_user_id=current_user.id,
        to_user_id=drama.user_id,
        inv_type="application",
        character_name=application_data.character_name,
        message=application_data.message,
    )

    crud.create_notification(
        db=db,
        user_id=drama.user_id,
        notif_type="drama_application",
        title="Cerere de participare la piesă",
        message=f'{current_user.username} a cerut să participe la piesa "{drama.title}" ca "{application_data.character_name}".',
        link=f"/piese/{drama.slug}",
        extra_data={"drama_id": drama.id, "invitation_id": invitation.id},
    )

    return {
        "id": invitation.id,
        "drama_id": invitation.drama_id,
        "from_user_id": invitation.from_user_id,
        "to_user_id": invitation.to_user_id,
        "type": invitation.type,
        "character_name": invitation.character_name,
        "message": invitation.message,
        "status": invitation.status,
        "created_at": invitation.created_at.isoformat(),
    }


@router.post("/api/dramas/{slug}/invitations/{invitation_id}/respond")
@limiter.limit("20/minute")
async def respond_to_invitation(
    request: Request,
    slug: str,
    invitation_id: int,
    response_data: schemas.InvitationRespond,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Accept or reject a drama invitation or application."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")

    invitation = crud.get_drama_invitation(db, invitation_id)
    if not invitation or invitation.drama_id != drama.id:
        raise HTTPException(status_code=404, detail="Invitația nu a fost găsită")
    if invitation.status != "pending":
        raise HTTPException(status_code=400, detail="Invitația a fost deja procesată")

    # Determine who is allowed to respond:
    # - For "invitation": the to_user responds (invited person accepts/rejects)
    # - For "application": the drama owner responds (owner accepts/rejects applicant)
    if invitation.type == "invitation" and invitation.to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar persoana invitată poate răspunde")
    if invitation.type == "application" and drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar autorul piesei poate răspunde la cereri")

    crud.respond_to_invitation(db, invitation_id, response_data.status)

    if response_data.status == "accepted":
        # Determine which user becomes the new character
        if invitation.type == "invitation":
            new_participant_id = invitation.to_user_id
        else:
            new_participant_id = invitation.from_user_id

        character_name = invitation.character_name or invitation.to_user.username

        crud.create_drama_character(
            db=db,
            drama_id=drama.id,
            user_id=new_participant_id,
            character_name=character_name,
            is_creator=False,
        )

        # Notify the other party
        if invitation.type == "invitation":
            # Notify the drama owner that invitee accepted
            crud.create_notification(
                db=db,
                user_id=drama.user_id,
                notif_type="drama_invitation_accepted",
                title="Invitație acceptată",
                message=f'{invitation.to_user.username} a acceptat invitația la piesa "{drama.title}".',
                link=f"/piese/{drama.slug}",
                extra_data={"drama_id": drama.id},
            )
        else:
            # Notify the applicant that they were accepted
            crud.create_notification(
                db=db,
                user_id=invitation.from_user_id,
                notif_type="drama_application_accepted",
                title="Cerere acceptată",
                message=f'Cererea ta de participare la piesa "{drama.title}" a fost acceptată.',
                link=f"/piese/{drama.slug}",
                extra_data={"drama_id": drama.id},
            )
    else:
        # Rejected — notify the appropriate party
        if invitation.type == "invitation":
            crud.create_notification(
                db=db,
                user_id=drama.user_id,
                notif_type="drama_invitation_rejected",
                title="Invitație respinsă",
                message=f'{invitation.to_user.username} a respins invitația la piesa "{drama.title}".',
                link=f"/piese/{drama.slug}",
                extra_data={"drama_id": drama.id},
            )
        else:
            crud.create_notification(
                db=db,
                user_id=invitation.from_user_id,
                notif_type="drama_application_rejected",
                title="Cerere respinsă",
                message=f'Cererea ta de participare la piesa "{drama.title}" a fost respinsă.',
                link=f"/piese/{drama.slug}",
                extra_data={"drama_id": drama.id},
            )

    return {"status": response_data.status, "invitation_id": invitation_id}


@router.delete("/api/dramas/{slug}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_character(
    slug: str,
    character_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Remove a character from a drama (owner only, cannot remove creator)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar autorul poate elimina personaje")

    character = crud.get_drama_character(db, character_id)
    if not character or character.drama_id != drama.id:
        raise HTTPException(status_code=404, detail="Personajul nu a fost găsit")
    if character.is_creator:
        raise HTTPException(status_code=400, detail="Creatorul piesei nu poate fi eliminat")

    crud.delete_drama_character(db, character_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ===========================================================================
# ACTS
# ===========================================================================

@router.post("/api/dramas/{slug}/acts")
@limiter.limit("20/minute")
async def create_act(
    request: Request,
    slug: str,
    act_data: schemas.ActCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Create a new act (owner only, drama must be in_progress, no other active act)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar autorul poate adăuga acte")
    if drama.status != "in_progress":
        raise HTTPException(status_code=400, detail="Nu poți adăuga acte la o piesă încheiată")

    active_act = drama.active_act
    if active_act:
        raise HTTPException(
            status_code=409,
            detail=f"Există deja un act activ (Actul {active_act.act_number}). Încheie-l mai întâi.",
        )

    act = crud.create_drama_act(db=db, drama_id=drama.id, title=act_data.title, setting=act_data.setting)

    return {
        "id": act.id,
        "drama_id": act.drama_id,
        "act_number": act.act_number,
        "title": act.title,
        "setting": act.setting,
        "status": act.status,
        "created_at": act.created_at.isoformat(),
        "replies": [],
    }


@router.put("/api/dramas/{slug}/acts/{act_number}")
@limiter.limit("20/minute")
async def update_act(
    request: Request,
    slug: str,
    act_number: int,
    act_update: schemas.ActUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Update act details (owner only)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar autorul poate edita actele")

    act = crud.get_drama_act(db, drama.id, act_number)
    if not act:
        raise HTTPException(status_code=404, detail="Actul nu a fost găsit")

    update_data = act_update.model_dump(exclude_none=True)
    act = crud.update_drama_act(db, act.id, update_data)

    return {
        "id": act.id,
        "drama_id": act.drama_id,
        "act_number": act.act_number,
        "title": act.title,
        "setting": act.setting,
        "status": act.status,
        "created_at": act.created_at.isoformat(),
    }


@router.post("/api/dramas/{slug}/acts/{act_number}/complete")
@limiter.limit("20/minute")
async def complete_act(
    request: Request,
    slug: str,
    act_number: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Complete an act (owner only)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar autorul poate încheia acte")

    act = crud.get_drama_act(db, drama.id, act_number)
    if not act:
        raise HTTPException(status_code=404, detail="Actul nu a fost găsit")
    if act.status == "completed":
        raise HTTPException(status_code=400, detail="Actul este deja încheiat")

    act = crud.complete_drama_act(db, act.id)

    return {
        "id": act.id,
        "drama_id": act.drama_id,
        "act_number": act.act_number,
        "title": act.title,
        "setting": act.setting,
        "status": act.status,
        "created_at": act.created_at.isoformat(),
    }


# ===========================================================================
# REPLIES
# ===========================================================================

@router.post("/api/dramas/{slug}/acts/{act_number}/replies")
@limiter.limit("20/minute")
async def create_reply(
    request: Request,
    slug: str,
    act_number: int,
    reply_data: schemas.ReplyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Add a reply to an act (participants only, act must be active)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")

    act = crud.get_drama_act(db, drama.id, act_number)
    if not act:
        raise HTTPException(status_code=404, detail="Actul nu a fost găsit")
    if act.status != "active":
        raise HTTPException(status_code=400, detail="Actul nu este activ, nu poți adăuga replici")

    # Caller must be a character in this drama
    character = crud.get_character_for_user_in_drama(db, drama.id, current_user.id)
    if not character:
        raise HTTPException(status_code=403, detail="Nu ești participant la această piesă")

    reply = crud.create_drama_reply(
        db=db,
        act_id=act.id,
        character_id=character.id,
        content=reply_data.content,
        stage_direction=reply_data.stage_direction,
    )

    # Notify other participants about the new reply
    for ch in drama.characters:
        if ch.user_id != current_user.id:
            crud.create_notification(
                db=db,
                user_id=ch.user_id,
                notif_type="drama_reply",
                title="Replică nouă în piesă",
                message=f'{character.character_name} a adăugat o replică în "{drama.title}".',
                link=f"/piese/{drama.slug}",
                extra_data={"drama_id": drama.id, "act_number": act_number, "reply_id": reply.id},
            )

    return {
        "id": reply.id,
        "act_id": reply.act_id,
        "character_id": reply.character_id,
        "content": reply.content,
        "stage_direction": reply.stage_direction,
        "position": reply.position,
        "created_at": reply.created_at.isoformat(),
        "character_name": character.character_name,
        "username": current_user.username,
    }


@router.put("/api/dramas/{slug}/replies/{reply_id}")
@limiter.limit("20/minute")
async def edit_reply(
    request: Request,
    slug: str,
    reply_id: int,
    reply_update: schemas.ReplyUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Edit own reply."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")

    reply = crud.get_drama_reply(db, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Replica nu a fost găsită")

    # Verify the reply belongs to this drama
    act = crud.get_drama_act(db, drama.id, reply.act.act_number)
    if not act or reply.act_id != act.id:
        raise HTTPException(status_code=404, detail="Replica nu aparține acestei piese")

    # Only the reply author may edit it
    character = crud.get_character_for_user_in_drama(db, drama.id, current_user.id)
    if not character or reply.character_id != character.id:
        raise HTTPException(status_code=403, detail="Poți edita doar propriile replici")

    update_data = reply_update.model_dump(exclude_none=True)
    reply = crud.update_drama_reply(db, reply_id, update_data)

    return {
        "id": reply.id,
        "act_id": reply.act_id,
        "character_id": reply.character_id,
        "content": reply.content,
        "stage_direction": reply.stage_direction,
        "position": reply.position,
        "created_at": reply.created_at.isoformat(),
    }


@router.delete("/api/dramas/{slug}/replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reply(
    slug: str,
    reply_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Delete a reply (drama owner or reply author)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")

    reply = crud.get_drama_reply(db, reply_id)
    if not reply:
        raise HTTPException(status_code=404, detail="Replica nu a fost găsită")

    # Check ownership: drama owner OR the character who wrote the reply
    is_drama_owner = drama.user_id == current_user.id
    character = crud.get_character_for_user_in_drama(db, drama.id, current_user.id)
    is_reply_author = character is not None and reply.character_id == character.id

    if not is_drama_owner and not is_reply_author:
        raise HTTPException(status_code=403, detail="Nu ești autorizat să ștergi această replică")

    crud.delete_drama_reply(db, reply_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/api/dramas/{slug}/replies/reorder")
@limiter.limit("20/minute")
async def reorder_replies(
    request: Request,
    slug: str,
    reorder_data: schemas.ReplyReorder,
    act_number: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    """Reorder replies within an act (owner only)."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")
    if drama.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar autorul poate reordona replicile")

    act = crud.get_drama_act(db, drama.id, act_number)
    if not act:
        raise HTTPException(status_code=404, detail="Actul nu a fost găsit")

    crud.reorder_drama_replies(db, act.id, reorder_data.reply_ids)
    return {"message": "Replicile au fost reordonate cu succes"}


# ===========================================================================
# AUDIENCE — LIKES & COMMENTS
# ===========================================================================

@router.post("/api/dramas/{slug}/likes")
@limiter.limit("20/minute")
async def like_drama(
    request: Request,
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Like or unlike a drama."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")

    user_id = current_user.id if current_user else None
    ip_address = get_client_ip(request) if not user_id else None

    like = crud.create_drama_like(db=db, drama_id=drama.id, user_id=user_id, ip_address=ip_address)
    if not like:
        raise HTTPException(status_code=409, detail="Ai apreciat deja această piesă")

    return {
        "id": like.id,
        "drama_id": like.drama_id,
        "user_id": like.user_id,
        "created_at": like.created_at.isoformat(),
    }


@router.post("/api/dramas/{slug}/comments")
@limiter.limit("20/minute")
async def comment_on_drama(
    request: Request,
    slug: str,
    comment_data: schemas.DramaCommentCreate,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Post a comment on a drama."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa de teatru nu a fost găsită")

    user_id = current_user.id if current_user else None
    author_name = comment_data.author_name

    if not user_id and not author_name:
        raise HTTPException(
            status_code=400,
            detail="Numele autorului este obligatoriu pentru comentariile neautentificate",
        )

    comment = crud.create_drama_comment(
        db=db,
        drama_id=drama.id,
        content=comment_data.content,
        user_id=user_id,
        author_name=author_name,
    )

    return {
        "id": comment.id,
        "drama_id": comment.drama_id,
        "user_id": comment.user_id,
        "author_name": comment.author_name,
        "content": comment.content,
        "moderation_status": comment.moderation_status,
        "created_at": comment.created_at.isoformat(),
    }


# ===========================================================================
# EXPORT
# ===========================================================================

@router.get("/api/dramas/{slug}/export/pdf")
async def export_drama_pdf(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    """Export a drama as a PDF file using WeasyPrint."""
    drama = crud.get_drama_by_slug(db, slug)
    if not drama:
        raise HTTPException(status_code=404, detail="Piesa nu a fost gasita")

    from weasyprint import HTML
    from jinja2 import Environment, FileSystemLoader
    from ..utils import MAIN_DOMAIN
    from starlette.responses import Response as StarletteResponse

    # Render the PDF template (standalone Jinja2 — only template still in use)
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("drama/pdf_template.html")
    html_content = template.render(drama=drama, MAIN_DOMAIN=MAIN_DOMAIN)

    # Convert to PDF
    pdf_bytes = HTML(string=html_content).write_pdf()

    return StarletteResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{drama.slug}.pdf"'
        }
    )
