import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas, auth, crud, profile_media
from ..database import get_db
from ..utils import get_avatar_url, get_cover_url
from ..week_util import utcnow_naive

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
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
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
        "is_premium": getattr(user, "is_premium", False),
        "premium_tier": getattr(user, "premium_tier", "free") or "free",
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
        "title": msg.title,
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


def _club_media_url_if_visible(club: models.Club, kind: str) -> Optional[str]:
    config = profile_media.media_kind_config(kind)
    key = getattr(club, f"{config['prefix']}_storage_key", None)
    if not key or not club.owner or not club.owner.has_audio_access:
        return None
    return profile_media.public_club_media_url(club.slug, kind)


def _viewer_club_state(
    db: Session,
    club: models.Club,
    current_user: Optional[models.User],
) -> tuple[Optional[str], Optional[str], bool]:
    if current_user is None:
        return None, None, False
    membership = crud.get_club_membership(db, club.id, current_user.id)
    my_role = membership.role if membership else None
    pending_status = None
    if membership is None:
        pending = crud.get_user_pending_request(db, club.id, current_user.id)
        pending_status = pending.direction if pending else None
    can_view_detail = bool(my_role or getattr(current_user, "is_admin", False))
    return my_role, pending_status, can_view_detail


def _club_summary_payload(
    db: Session,
    club: models.Club,
    current_user: Optional[models.User] = None,
) -> dict:
    my_role, pending_status, can_view_detail = _viewer_club_state(db, club, current_user)
    profile_photo_url = _club_media_url_if_visible(club, "profil")
    cover_photo_url = _club_media_url_if_visible(club, "coperta")
    avatar_seed = club.avatar_seed or f"{club.slug}-shapes"
    cover_seed = f"{club.slug}-cover-sky"
    return {
        "id": club.id,
        "owner_id": club.owner_id,
        "title": club.title,
        "slug": club.slug,
        "description": club.description,
        "motto": club.motto,
        "avatar_seed": avatar_seed,
        "avatar_url": profile_photo_url or get_avatar_url(avatar_seed, size=160),
        "theme": club.theme,
        "speciality": club.speciality,
        "join_policy": club.join_policy,
        "member_count": crud.count_club_members(db, club.id),
        "owner": _owner_payload(club.owner),
        "profile_photo_url": profile_photo_url,
        "cover_photo_url": cover_photo_url,
        "cover_url": cover_photo_url or get_cover_url(cover_seed, size=1600),
        "has_profile_photo": bool(club.profile_photo_storage_key and profile_photo_url),
        "has_cover_photo": bool(club.cover_photo_storage_key and cover_photo_url),
        "my_role": my_role,
        "my_pending_request_status": pending_status,
        "can_view_detail": can_view_detail,
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
        "application_text": req.application_text,
        "created_at": req.created_at,
        "responded_at": req.responded_at,
    }


def _achievement_payload(achievement: models.ClubAchievement) -> dict:
    definition = crud.achievement_definition(achievement.key)
    return {
        "id": achievement.id,
        "key": achievement.key,
        "label": definition["label"],
        "description": definition["description"],
        "unlocked_at": achievement.unlocked_at,
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
            "is_premium": getattr(m.user, "is_premium", False) if m.user else False,
            "premium_tier": (getattr(m.user, "premium_tier", "free") or "free") if m.user else "free",
            "role": m.role,
            "joined_at": m.joined_at,
            "contribution_count": crud.count_member_contributions(db, club.id, m.user_id),
        })

    featured = crud.get_active_featured(db, club)
    messages = crud.list_board_messages(db, club.id, limit=20)
    recent_messages = [_board_message_payload(m, role_by_user) for m in messages]
    achievements = [
        _achievement_payload(item)
        for item in crud.list_club_achievements(db, club.id)
    ]

    my_role = None
    my_pending_request_status = None
    pending_request_count = None
    viewer_is_site_admin = bool(getattr(current_user, "is_admin", False)) if current_user else False
    if current_user is not None:
        membership = crud.get_club_membership(db, club.id, current_user.id)
        my_role = membership.role if membership else None
        if membership is None:
            pending = crud.get_user_pending_request(db, club.id, current_user.id)
            my_pending_request_status = pending.direction if pending else None
        if my_role in ("owner", "admin") or viewer_is_site_admin:
            pending_request_count = crud.count_pending_requests_for_club(db, club.id)

    can_manage = my_role in ("owner", "admin")
    can_post = my_role is not None
    can_upload_media = bool(current_user and club.owner_id == current_user.id and current_user.has_audio_access)
    summary = _club_summary_payload(db, club, current_user=current_user)
    return {
        **summary,
        "members": member_payloads,
        "featured": _featured_payload(featured),
        "achievements": achievements,
        "recent_messages": recent_messages,
        "my_role": my_role,
        "my_pending_request_status": my_pending_request_status,
        "can_post": can_post,
        "can_manage": can_manage,
        "can_upload_media": can_upload_media,
        "viewer_is_site_admin": viewer_is_site_admin,
        "pending_request_count": pending_request_count,
    }


# ----- club CRUD endpoints -----

@router.post("/api/cluburi/", status_code=status.HTTP_201_CREATED)
def create_club_api(
    data: schemas.ClubCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    try:
        club = crud.create_club(db, owner=current_user, data=data)
    except ValueError as e:
        if str(e) == "owner_already_has_club":
            raise HTTPException(status_code=409, detail="Poți crea un singur club")
        raise HTTPException(status_code=400, detail=str(e))
    db.refresh(club)
    return _club_summary_payload(db, club, current_user=current_user)


@router.get("/api/cluburi")
def list_clubs_api(
    speciality: Optional[str] = None,
    theme: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    if speciality and speciality not in crud.CLUB_VALID_SPECIALITIES:
        raise HTTPException(status_code=400, detail="Specialitate invalidă")
    clubs = crud.list_clubs(
        db,
        speciality=speciality,
        theme_query=theme,
        search_query=q,
        limit=max(1, min(limit, 100)),
        offset=max(0, offset),
    )
    return {"clubs": [_club_summary_payload(db, c, current_user=current_user) for c in clubs]}


@router.get("/api/cluburi/aleatoriu")
def random_club_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_random_club(db)
    if not club:
        raise HTTPException(status_code=404, detail="Niciun club disponibil")
    return _club_summary_payload(db, club, current_user=current_user)


@router.get("/api/cluburi/{slug}")
def get_club_api(
    slug: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club_by_slug(db, slug)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    membership = crud.get_club_membership(db, club.id, current_user.id)
    if not membership and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Doar membrii clubului pot vedea această pagină")
    return _build_club_detail(db, club, current_user)


@router.put("/api/cluburi/{club_id}")
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
    return _club_summary_payload(db, updated, current_user=current_user)


@router.delete("/api/cluburi/{club_id}", status_code=status.HTTP_204_NO_CONTENT)
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

@router.post("/api/cluburi/{club_id}/inscriere")
def apply_to_club_api(
    club_id: int,
    body: schemas.ClubJoinApplyRequest | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    request, error = crud.apply_to_club(
        db,
        current_user,
        club,
        application_text=body.application_text if body else None,
    )
    if error == "suspended":
        raise HTTPException(status_code=403, detail="Contul tău este suspendat")
    if error == "already_member":
        raise HTTPException(status_code=409, detail="Ești deja membru al acestui club")
    if error == "already_pending":
        raise HTTPException(status_code=409, detail="Ai deja o cerere în așteptare")
    if error == "closed":
        raise HTTPException(status_code=403, detail="Acest club este pe bază de invitație")
    if error == "application_text_required":
        raise HTTPException(status_code=422, detail="Completează câmpul „De ce vrei să ni te alături\"")
    if isinstance(request, models.ClubMember):
        return {
            "status": "joined",
            "membership": {
                "id": request.id,
                "user_id": request.user_id,
                "role": request.role,
                "joined_at": request.joined_at,
            },
        }
    return _join_request_payload(request)


@router.post("/api/cluburi/{club_id}/invita")
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


@router.get("/api/cluburi/{club_id}/cereri")
def list_club_requests_api(
    club_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    membership = crud.get_club_membership(db, club.id, current_user.id)
    if not current_user.is_admin and (not membership or membership.role not in ("owner", "admin")):
        raise HTTPException(status_code=403, detail="Acces interzis")
    requests = crud.list_club_pending_requests(db, club.id)
    return {"requests": [_join_request_payload(r) for r in requests]}


@router.post("/api/cluburi/{club_id}/cereri/{request_id}/raspunde")
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


@router.delete("/api/cluburi/{club_id}/membri/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.put("/api/cluburi/{club_id}/membri/{user_id}/rol")
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

@router.get("/api/utilizator/cluburi")
def list_my_clubs_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    clubs = crud.list_user_clubs(db, current_user.id)
    owned_club = crud.get_owned_club(db, current_user.id)
    return {
        "clubs": [_club_summary_payload(db, c, current_user=current_user) for c in clubs],
        "owned_club": (
            _club_summary_payload(db, owned_club, current_user=current_user)
            if owned_club else None
        ),
    }


@router.get("/api/utilizator/cluburi/in-asteptare")
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
            "club": _club_summary_payload(db, inv.club, current_user=current_user),
            "direction": inv.direction,
        })
    return {"items": items}


# ----- board messages -----

@router.get("/api/cluburi/{club_id}/tabla")
def list_club_board_api(
    club_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    if not current_user.is_admin and not crud.get_club_membership(db, club.id, current_user.id):
        raise HTTPException(status_code=403, detail="Doar membrii clubului pot vedea discuțiile")
    messages = crud.list_board_messages(
        db, club_id, limit=max(1, min(limit, 100)), offset=max(0, offset)
    )
    members = crud.list_club_members(db, club_id)
    role_by_user = {m.user_id: m.role for m in members}
    return {"messages": [_board_message_payload(m, role_by_user) for m in messages]}


@router.post("/api/cluburi/{club_id}/tabla", status_code=status.HTTP_201_CREATED)
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
        db, current_user, club, body.content, title=body.title, parent_id=body.parent_id
    )
    if error == "not_member":
        raise HTTPException(status_code=403, detail="Trebuie să fii membru ca să postezi")
    if error == "bad_parent":
        raise HTTPException(status_code=400, detail="Mesaj părinte invalid")
    if error == "missing_title":
        raise HTTPException(status_code=422, detail="Titlul firului este obligatoriu")
    if error == "empty_content":
        raise HTTPException(status_code=422, detail="Mesajul este obligatoriu")
    members = crud.list_club_members(db, club.id)
    role_by_user = {m.user_id: m.role for m in members}
    return _board_message_payload(msg, role_by_user, include_replies=False)


@router.delete(
    "/api/cluburi/{club_id}/tabla/{message_id}",
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


# ----- club media -----

def _club_media_storage_attrs(kind: str) -> tuple[str, str, str, str]:
    config = profile_media.media_kind_config(kind)
    prefix = config["prefix"]
    return (
        f"{prefix}_storage_backend",
        f"{prefix}_storage_key",
        f"{prefix}_content_type",
        f"{prefix}_updated_at",
    )


def _require_media_owner(club: models.Club, current_user: models.User) -> None:
    if club.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Doar creatorul clubului poate gestiona imaginile")
    if not current_user.has_audio_access:
        raise HTTPException(status_code=403, detail="Imaginile clubului sunt disponibile pentru Cronicar și Rapsod")


@router.post("/api/cluburi/{club_id}/media/{kind}")
async def upload_club_media(
    club_id: int,
    kind: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    profile_media.media_kind_config(kind)
    _require_media_owner(club, current_user)

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in profile_media.ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Format de imagine neacceptat")

    max_bytes = profile_media.max_upload_bytes()
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"Imaginea depășește {max_mb} MB")
    if not content:
        raise HTTPException(status_code=400, detail="Fișierul imagine este gol")

    processed = profile_media.process_uploaded_image(content, kind)
    backend_attr, key_attr, content_type_attr, updated_attr = _club_media_storage_attrs(kind)
    old_backend = getattr(club, backend_attr)
    old_key = getattr(club, key_attr)
    backend, key, stored_content_type = profile_media.save_club_media_bytes(
        club_id=club.id,
        kind=kind,
        content=processed,
    )
    setattr(club, backend_attr, backend)
    setattr(club, key_attr, key)
    setattr(club, content_type_attr, stored_content_type)
    setattr(club, updated_attr, utcnow_naive())
    db.add(club)
    db.commit()
    db.refresh(club)
    profile_media.delete_stored_media(old_backend, old_key)
    return _club_summary_payload(db, club, current_user=current_user)


@router.delete("/api/cluburi/{club_id}/media/{kind}")
def delete_club_media(
    club_id: int,
    kind: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user),
):
    club = crud.get_club(db, club_id)
    if not club:
        raise HTTPException(status_code=404, detail="Clubul nu a fost găsit")
    _club_media_storage_attrs(kind)
    _require_media_owner(club, current_user)
    backend_attr, key_attr, content_type_attr, updated_attr = _club_media_storage_attrs(kind)
    old_backend = getattr(club, backend_attr)
    old_key = getattr(club, key_attr)
    setattr(club, backend_attr, None)
    setattr(club, key_attr, None)
    setattr(club, content_type_attr, None)
    setattr(club, updated_attr, None)
    db.add(club)
    db.commit()
    db.refresh(club)
    profile_media.delete_stored_media(old_backend, old_key)
    return _club_summary_payload(db, club, current_user=current_user)


@router.get("/api/cluburi/{slug}/media/{kind}")
def get_public_club_media(
    slug: str,
    kind: str,
    db: Session = Depends(get_db),
):
    club = crud.get_club_by_slug(db, slug)
    if not club or not club.owner or not club.owner.has_audio_access:
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    backend_attr, key_attr, content_type_attr, _ = _club_media_storage_attrs(kind)
    backend = getattr(club, backend_attr)
    key = getattr(club, key_attr)
    content_type = getattr(club, content_type_attr) or profile_media.PROFILE_MEDIA_CONTENT_TYPE
    if not key:
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    if backend == "s3":
        return RedirectResponse(profile_media.presigned_media_url(key))
    if backend != "local":
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    path = profile_media.local_path_for_key(key)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Imaginea nu a fost găsită")
    return FileResponse(path, media_type=content_type)


# ----- featured creation -----

@router.post("/api/cluburi/{club_id}/creatia-saptamanii")
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


@router.delete("/api/cluburi/{club_id}/creatia-saptamanii", status_code=status.HTTP_204_NO_CONTENT)
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
