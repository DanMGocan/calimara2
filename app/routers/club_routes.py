import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, auth, crud
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["clubs"])


# ----- helpers -----

def _owner_payload(user: Optional[models.User]) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
    }


def _board_author_payload(
    user: Optional[models.User], membership_role: Optional[str] = None
) -> Optional[dict]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "avatar_seed": user.avatar_seed or f"{user.username}-shapes",
        "role": membership_role,
    }


def _board_message_payload(
    msg: models.ClubBoardMessage,
    role_by_user: dict[int, str],
    include_replies: bool = True,
) -> dict:
    payload = {
        "id": msg.id,
        "club_id": msg.club_id,
        "parent_id": msg.parent_id,
        "content": msg.content,
        "created_at": msg.created_at,
        "updated_at": msg.updated_at,
        "author": _board_author_payload(msg.author, role_by_user.get(msg.author_id)),
        "replies": [],
    }
    if include_replies and msg.replies:
        # Replies are already capped at one level by post_board_message
        ordered_replies = sorted(msg.replies, key=lambda r: (r.created_at, r.id))
        payload["replies"] = [
            _board_message_payload(r, role_by_user, include_replies=False)
            for r in ordered_replies
        ]
    return payload


def _club_summary_payload(db: Session, club: models.Club) -> dict:
    return {
        "id": club.id,
        "owner_id": club.owner_id,
        "title": club.title,
        "slug": club.slug,
        "description": club.description,
        "motto": club.motto,
        "avatar_seed": club.avatar_seed,
        "theme": club.theme,
        "speciality": club.speciality,
        "member_count": crud.count_club_members(db, club.id),
        "owner": _owner_payload(club.owner),
        "created_at": club.created_at,
        "updated_at": club.updated_at,
    }


def _featured_payload(featured) -> Optional[dict]:
    if not featured:
        return None
    post, until = featured
    return {
        "post_id": post.id,
        "post_title": post.title,
        "post_slug": post.slug,
        "post_author": _owner_payload(post.owner),
        "featured_until": until,
    }


def _join_request_payload(req: models.ClubJoinRequest) -> dict:
    return {
        "id": req.id,
        "club_id": req.club_id,
        "user": _owner_payload(req.user),
        "direction": req.direction,
        "status": req.status,
        "initiator_id": req.initiator_id,
        "created_at": req.created_at,
        "responded_at": req.responded_at,
    }


def _build_club_detail(
    db: Session,
    club: models.Club,
    current_user: Optional[models.User],
) -> dict:
    members = crud.list_club_members(db, club.id)
    role_by_user = {m.user_id: m.role for m in members}
    member_payloads = []
    for m in members:
        member_payloads.append({
            "id": m.id,
            "user_id": m.user_id,
            "username": m.user.username if m.user else "",
            "avatar_seed": (m.user.avatar_seed if m.user else None)
                            or (f"{m.user.username}-shapes" if m.user else None),
            "role": m.role,
            "joined_at": m.joined_at,
            "contribution_count": crud.count_member_contributions(db, club.id, m.user_id),
        })

    featured = crud.get_active_featured(db, club)
    messages = crud.list_board_messages(db, club.id, limit=20)
    recent_messages = [_board_message_payload(m, role_by_user) for m in messages]

    my_role = None
    my_pending_request_status = None
    pending_request_count = None
    if current_user is not None:
        membership = crud.get_club_membership(db, club.id, current_user.id)
        my_role = membership.role if membership else None
        if membership is None:
            pending = crud.get_user_pending_request(db, club.id, current_user.id)
            my_pending_request_status = pending.direction if pending else None
        if my_role in ("owner", "admin"):
            pending_request_count = crud.count_pending_requests_for_club(db, club.id)

    summary = _club_summary_payload(db, club)
    return {
        **summary,
        "members": member_payloads,
        "featured": _featured_payload(featured),
        "recent_messages": recent_messages,
        "my_role": my_role,
        "my_pending_request_status": my_pending_request_status,
        "pending_request_count": pending_request_count,
    }


# ----- club CRUD endpoints -----

@router.post("/api/clubs/", status_code=status.HTTP_201_CREATED)
def create_club_api(
    data: schemas.ClubCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_premium_user),
):
    try:
        club = crud.create_club(db, owner=current_user, data=data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(club)
    return _club_summary_payload(db, club)


@router.get("/api/clubs")
def list_clubs_api(
    speciality: Optional[str] = None,
    theme: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if speciality and speciality not in crud.CLUB_VALID_SPECIALITIES:
        raise HTTPException(status_code=400, detail="Specialitate invalidă")
    clubs = crud.list_clubs(
        db,
        speciality=speciality,
        theme_query=theme,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )
    return {"clubs": [_club_summary_payload(db, c) for c in clubs]}


@router.get("/api/clubs/random")
def random_club_api(db: Session = Depends(get_db)):
    club = crud.get_random_club(db)
    if not club:
        raise HTTPException(status_code=404, detail="Niciun club disponibil")
    return _club_summary_payload(db, club)


@router.get("/api/collections/random")
def random_collection_api(db: Session = Depends(get_db)):
    """Random collection — added here for proximity to /api/clubs/random."""
    collection = crud.get_random_collection(db)
    if not collection:
        raise HTTPException(status_code=404, detail="Nicio colecție disponibilă")
    return {
        "id": collection.id,
        "title": collection.title,
        "slug": collection.slug,
        "description": collection.description,
        "owner": _owner_payload(collection.owner),
    }


@router.get("/api/clubs/{slug}")
def get_club_api(
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_current_user),
):
    club = crud.get_club_by_slug(db, slug)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    return _build_club_detail(db, club, current_user)


@router.put("/api/clubs/{club_id}")
def update_club_api(
    club_id: int,
    data: schemas.ClubUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club or club.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    try:
        updated = crud.update_club(db, club_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(updated)
    return _club_summary_payload(db, updated)


@router.delete("/api/clubs/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_club_api(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club or club.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    crud.delete_club(db, club_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- membership: apply, invite, respond, kick, role -----

@router.post("/api/clubs/{club_id}/apply")
def apply_to_club_api(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    request, error = crud.apply_to_club(db, current_user, club)
    if error == "suspended":
        raise HTTPException(status_code=403, detail="Contul tău este suspendat")
    if error == "already_member":
        raise HTTPException(status_code=409, detail="Ești deja membru al acestui club")
    if error == "already_pending":
        raise HTTPException(status_code=409, detail="Ai deja o cerere în așteptare")
    return _join_request_payload(request)


@router.post("/api/clubs/{club_id}/invite")
def invite_to_club_api(
    club_id: int,
    body: schemas.ClubInviteRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    target = crud.get_user_by_username(db, body.username.strip())
    if not target:
        raise HTTPException(status_code=404, detail="Utilizatorul nu a fost găsit")
    request, error = crud.invite_to_club(db, current_user, club, target)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar proprietarul sau administratorii pot invita")
    if error == "target_suspended":
        raise HTTPException(status_code=400, detail="Utilizatorul este suspendat")
    if error == "already_member":
        raise HTTPException(status_code=409, detail="Utilizatorul este deja membru")
    if error == "already_pending":
        raise HTTPException(status_code=409, detail="Există deja o invitație sau cerere în așteptare pentru acest utilizator")
    return _join_request_payload(request)


@router.get("/api/clubs/{club_id}/requests")
def list_club_requests_api(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    membership = crud.get_club_membership(db, club.id, current_user.id)
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Acces interzis")
    requests = crud.list_club_pending_requests(db, club.id)
    return {"requests": [_join_request_payload(r) for r in requests]}


@router.post("/api/clubs/{club_id}/requests/{request_id}/respond")
def respond_club_request_api(
    club_id: int,
    request_id: int,
    body: schemas.ClubJoinRespondRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    request = crud.get_club_join_request(db, request_id)
    if not request or request.club_id != club_id:
        raise HTTPException(status_code=404, detail="Cererea nu a fost găsită")
    updated, error = crud.respond_to_club_request(db, request, current_user, body.action)
    if error == "bad_action":
        raise HTTPException(status_code=400, detail="Acțiune invalidă")
    if error == "not_pending":
        raise HTTPException(status_code=409, detail="Cererea nu mai este în așteptare")
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Nu poți răspunde la această cerere")
    if error == "inconsistent_direction":
        raise HTTPException(status_code=500, detail="Cerere inconsistentă")
    return _join_request_payload(updated)


@router.delete("/api/clubs/{club_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_club_member_api(
    club_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    ok, error = crud.kick_member(db, current_user, club, user_id)
    if not ok:
        if error == "not_member":
            raise HTTPException(status_code=404, detail="Membru inexistent")
        if error == "owner_cannot_leave":
            raise HTTPException(
                status_code=400,
                detail="Proprietarul nu poate părăsi clubul. Șterge clubul sau transferă-l înainte.",
            )
        if error == "cannot_kick_self":
            raise HTTPException(status_code=400, detail="Acțiune invalidă")
        raise HTTPException(status_code=403, detail="Nu ai permisiunea")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/api/clubs/{club_id}/members/{user_id}/role")
def update_member_role_api(
    club_id: int,
    user_id: int,
    body: schemas.ClubMemberRoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    membership, error = crud.update_member_role(db, current_user, club, user_id, body.role)
    if error == "bad_role":
        raise HTTPException(status_code=400, detail="Rol invalid")
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar proprietarul poate schimba roluri")
    if error == "cannot_change_own_role":
        raise HTTPException(status_code=400, detail="Nu îți poți schimba propriul rol")
    if error == "cannot_change_owner_role":
        raise HTTPException(status_code=400, detail="Rolul proprietarului nu poate fi schimbat")
    if error == "not_member":
        raise HTTPException(status_code=404, detail="Utilizatorul nu este membru")
    return {
        "id": membership.id,
        "user_id": membership.user_id,
        "role": membership.role,
        "joined_at": membership.joined_at,
    }


# ----- user-scoped club views -----

@router.get("/api/user/clubs")
def list_my_clubs_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    clubs = crud.list_user_clubs(db, current_user.id)
    return {"clubs": [_club_summary_payload(db, c) for c in clubs]}


@router.get("/api/user/clubs/pending")
def list_my_club_invitations_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    invitations = crud.list_user_pending_invitations(db, current_user.id)
    items = []
    for inv in invitations:
        if not inv.club:
            continue
        items.append({
            "request": _join_request_payload(inv),
            "club": _club_summary_payload(db, inv.club),
            "direction": inv.direction,
        })
    return {"items": items}


# ----- board messages -----

@router.get("/api/clubs/{club_id}/board")
def list_club_board_api(
    club_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    messages = crud.list_board_messages(
        db, club_id, limit=max(1, min(limit, 100)), offset=max(0, offset)
    )
    members = crud.list_club_members(db, club_id)
    role_by_user = {m.user_id: m.role for m in members}
    return {"messages": [_board_message_payload(m, role_by_user) for m in messages]}


@router.post("/api/clubs/{club_id}/board", status_code=status.HTTP_201_CREATED)
def post_club_board_message_api(
    club_id: int,
    body: schemas.ClubBoardMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    msg, error = crud.post_board_message(
        db, current_user, club, body.content, parent_id=body.parent_id
    )
    if error == "not_member":
        raise HTTPException(status_code=403, detail="Trebuie să fii membru ca să postezi")
    if error == "bad_parent":
        raise HTTPException(status_code=400, detail="Mesaj părinte invalid")
    members = crud.list_club_members(db, club.id)
    role_by_user = {m.user_id: m.role for m in members}
    return _board_message_payload(msg, role_by_user, include_replies=False)


@router.delete(
    "/api/clubs/{club_id}/board/{message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_club_board_message_api(
    club_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    msg = crud.get_board_message(db, message_id)
    if not msg or msg.club_id != club_id:
        raise HTTPException(status_code=404, detail="Mesaj inexistent")
    ok, error = crud.delete_board_message(db, current_user, msg)
    if not ok:
        raise HTTPException(status_code=403, detail="Nu ai permisiunea să ștergi mesajul")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----- featured creation -----

@router.post("/api/clubs/{club_id}/featured")
def set_club_featured_api(
    club_id: int,
    body: schemas.ClubFeaturedSetRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club or club.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    post, error = crud.set_featured_post(db, current_user, club, body.post_id)
    if error == "not_allowed":
        raise HTTPException(status_code=403, detail="Doar proprietarul poate seta creația săptămânii")
    if error == "post_not_found":
        raise HTTPException(status_code=404, detail="Postarea nu a fost găsită")
    if error == "post_not_approved":
        raise HTTPException(status_code=400, detail="Postarea nu este aprobată")
    if error == "speciality_mismatch":
        raise HTTPException(
            status_code=400,
            detail="Postarea trebuie să aibă aceeași specialitate ca clubul",
        )
    if error == "author_not_member":
        raise HTTPException(status_code=400, detail="Autorul postării nu este membru al clubului")
    return _featured_payload((post, club.featured_until))


@router.delete("/api/clubs/{club_id}/featured", status_code=status.HTTP_204_NO_CONTENT)
def clear_club_featured_api(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club or club.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    ok, error = crud.clear_featured_post(db, current_user, club)
    if not ok:
        raise HTTPException(status_code=403, detail="Acțiune nepermisă")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
