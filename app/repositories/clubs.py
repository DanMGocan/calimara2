from ._shared import *
from .notifications import create_notification
from .slugs import generate_slug

CLUB_FEATURED_DURATION = timedelta(days=7)

CLUB_VALID_SPECIALITIES = ("poezie", "proza_scurta")
CLUB_JOIN_POLICIES = ("open", "private", "closed")
CLUB_ACHIEVEMENT_DEFINITIONS = {
    "atelier_deschis": {
        "label": "Atelier deschis",
        "description": "Clubul a pornit primul fir de atelier.",
    },
    "cerc_de_cinci": {
        "label": "Cerc de cinci",
        "description": "Clubul a ajuns la cinci membri.",
    },
    "dialog_viu": {
        "label": "Dialog viu",
        "description": "Discuțiile clubului au adunat 25 de mesaje.",
    },
    "creatia_saptamanii": {
        "label": "Creația săptămânii",
        "description": "Clubul a ales prima creație a săptămânii.",
    },
}

def _generate_club_slug(title: str) -> str:
    return generate_slug(title, fallback="club")

def _ensure_unique_club_slug(db: Session, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while db.query(models.Club).filter(models.Club.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug

def get_club(db: Session, club_id: int) -> Optional[models.Club]:
    return db.query(models.Club).options(joinedload(models.Club.owner)).filter(models.Club.id == club_id).first()

def get_club_by_slug(db: Session, slug: str) -> Optional[models.Club]:
    return db.query(models.Club).options(
        joinedload(models.Club.owner)
    ).filter(models.Club.slug == slug).first()

def list_clubs(
    db: Session,
    *,
    speciality: Optional[str] = None,
    theme_query: Optional[str] = None,
    search_query: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    query = db.query(models.Club).options(joinedload(models.Club.owner))
    if speciality:
        query = query.filter(models.Club.speciality == speciality)
    query_text = (search_query or theme_query or "").strip()
    if query_text:
        like = f"%{query_text}%"
        query = query.filter(
            or_(
                models.Club.theme.ilike(like),
                models.Club.title.ilike(like),
                models.Club.description.ilike(like),
            )
        )
    return (
        query.order_by(models.Club.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

def get_random_club(db: Session) -> Optional[models.Club]:
    """Random club that has at least one member (always at minimum the owner)."""
    return (
        db.query(models.Club)
        .options(joinedload(models.Club.owner))
        .filter(
            db.query(models.ClubMember.id)
            .filter(models.ClubMember.club_id == models.Club.id)
            .exists()
        )
        .order_by(func.random())
        .limit(1)
        .first()
    )

def count_club_members(db: Session, club_id: int) -> int:
    return db.query(models.ClubMember).filter(models.ClubMember.club_id == club_id).count()

def count_club_board_messages(db: Session, club_id: int) -> int:
    return db.query(models.ClubBoardMessage).filter(models.ClubBoardMessage.club_id == club_id).count()

def get_owned_club(db: Session, user_id: int) -> Optional[models.Club]:
    return (
        db.query(models.Club)
        .options(joinedload(models.Club.owner))
        .filter(models.Club.owner_id == user_id)
        .first()
    )

def count_owned_clubs(db: Session, user_id: int) -> int:
    return db.query(models.Club).filter(models.Club.owner_id == user_id).count()

def get_club_membership(db: Session, club_id: int, user_id: int) -> Optional[models.ClubMember]:
    return db.query(models.ClubMember).filter(
        models.ClubMember.club_id == club_id,
        models.ClubMember.user_id == user_id,
    ).first()

def list_club_members(db: Session, club_id: int) -> List[models.ClubMember]:
    role_priority = case(
        (models.ClubMember.role == "owner", 0),
        (models.ClubMember.role == "admin", 1),
        else_=2,
    )
    return (
        db.query(models.ClubMember)
        .options(joinedload(models.ClubMember.user))
        .filter(models.ClubMember.club_id == club_id)
        .order_by(role_priority.asc(), models.ClubMember.joined_at.asc())
        .all()
    )

def count_member_contributions(db: Session, club_id: int, user_id: int) -> int:
    return (
        db.query(models.ClubBoardMessage)
        .filter(
            models.ClubBoardMessage.club_id == club_id,
            models.ClubBoardMessage.author_id == user_id,
        )
        .count()
    )

def create_club(db: Session, owner: models.User, data: schemas.ClubCreate) -> models.Club:
    if data.speciality not in CLUB_VALID_SPECIALITIES:
        raise ValueError("speciality_invalid")
    if data.join_policy not in CLUB_JOIN_POLICIES:
        raise ValueError("join_policy_invalid")
    if count_owned_clubs(db, owner.id) > 0:
        raise ValueError("owner_already_has_club")
    base_slug = _generate_club_slug(data.title)
    slug = _ensure_unique_club_slug(db, base_slug)
    club = models.Club(
        owner_id=owner.id,
        title=data.title.strip(),
        slug=slug,
        description=(data.description or "").strip() or None,
        motto=(data.motto or "").strip() or None,
        avatar_seed=(data.avatar_seed or "").strip() or None,
        theme=(data.theme or "").strip() or None,
        speciality=data.speciality,
        join_policy=data.join_policy,
    )
    try:
        db.add(club)
        db.flush()
        db.add(models.ClubMember(club_id=club.id, user_id=owner.id, role="owner"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_clubs_owner" in str(exc.orig):
            raise ValueError("owner_already_has_club") from exc
        raise
    db.refresh(club)
    return club

def update_club(db: Session, club_id: int, data: schemas.ClubUpdate) -> Optional[models.Club]:
    club = get_club(db, club_id)
    if not club:
        return None
    payload = data.model_dump(exclude_unset=True)
    if "title" in payload and payload["title"]:
        club.title = payload["title"].strip()
    if "speciality" in payload and payload["speciality"]:
        if payload["speciality"] not in CLUB_VALID_SPECIALITIES:
            raise ValueError("speciality_invalid")
        club.speciality = payload["speciality"]
    if "join_policy" in payload and payload["join_policy"]:
        if payload["join_policy"] not in CLUB_JOIN_POLICIES:
            raise ValueError("join_policy_invalid")
        club.join_policy = payload["join_policy"]
    for field in ("description", "motto", "avatar_seed", "theme"):
        if field in payload:
            value = payload[field]
            setattr(club, field, value.strip() if isinstance(value, str) and value.strip() else None)
    db.commit()
    db.refresh(club)
    return club

def delete_club(db: Session, club_id: int) -> bool:
    club = get_club(db, club_id)
    if not club:
        return False
    db.delete(club)
    db.commit()
    return True

def _has_pending_request(db: Session, club_id: int, user_id: int) -> bool:
    return db.query(models.ClubJoinRequest).filter(
        models.ClubJoinRequest.club_id == club_id,
        models.ClubJoinRequest.user_id == user_id,
        models.ClubJoinRequest.status == "pending",
    ).first() is not None

def get_user_pending_request(db: Session, club_id: int, user_id: int) -> Optional[models.ClubJoinRequest]:
    return db.query(models.ClubJoinRequest).filter(
        models.ClubJoinRequest.club_id == club_id,
        models.ClubJoinRequest.user_id == user_id,
        models.ClubJoinRequest.status == "pending",
    ).first()

def apply_to_club(
    db: Session,
    applicant: models.User,
    club: models.Club,
    application_text: Optional[str] = None,
) -> tuple[Optional[Any], Optional[str]]:
    if applicant.is_suspended:
        return None, "suspended"
    if get_club_membership(db, club.id, applicant.id):
        return None, "already_member"
    if _has_pending_request(db, club.id, applicant.id):
        return None, "already_pending"
    if club.join_policy == "closed":
        return None, "closed"
    cleaned_text = (application_text or "").strip()
    if club.join_policy == "open":
        membership = models.ClubMember(
            club_id=club.id,
            user_id=applicant.id,
            role="member",
        )
        db.add(membership)
        db.commit()
        db.refresh(membership)
        _notify_club_open_join_to_admins(db, club, applicant)
        evaluate_member_count_achievements(db, club)
        return membership, None
    if not cleaned_text:
        return None, "application_text_required"
    request = models.ClubJoinRequest(
        club_id=club.id,
        user_id=applicant.id,
        direction="application",
        status="pending",
        initiator_id=applicant.id,
        application_text=cleaned_text,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    _notify_club_application_to_admins(db, club, applicant, request)
    return request, None

def invite_to_club(
    db: Session, inviter: models.User, club: models.Club, target: models.User
) -> tuple[Optional[models.ClubJoinRequest], Optional[str]]:
    inviter_membership = get_club_membership(db, club.id, inviter.id)
    if not inviter_membership or inviter_membership.role not in ("owner", "admin"):
        return None, "not_allowed"
    if target.is_suspended:
        return None, "target_suspended"
    if get_club_membership(db, club.id, target.id):
        return None, "already_member"
    if _has_pending_request(db, club.id, target.id):
        return None, "already_pending"
    request = models.ClubJoinRequest(
        club_id=club.id,
        user_id=target.id,
        direction="invitation",
        status="pending",
        initiator_id=inviter.id,
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    _notify_club_invitation_to_target(db, club, inviter, target, request)
    return request, None

def respond_to_club_request(
    db: Session,
    request: models.ClubJoinRequest,
    responder: models.User,
    action: str,
) -> tuple[Optional[models.ClubJoinRequest], Optional[str]]:
    if action not in ("approve", "reject"):
        return None, "bad_action"
    if request.status != "pending":
        return None, "not_pending"

    club = request.club

    # For applications: counterparty is owner/admin of the club.
    # For invitations: counterparty is the invited user themselves.
    if request.direction == "application":
        membership = get_club_membership(db, club.id, responder.id)
        if not membership or membership.role not in ("owner", "admin"):
            return None, "not_allowed"
    elif request.direction == "invitation":
        if responder.id != request.user_id:
            return None, "not_allowed"
    else:
        return None, "inconsistent_direction"

    if action == "approve":
        # If they happen to already be a member (race), just close the request.
        if not get_club_membership(db, club.id, request.user_id):
            db.add(models.ClubMember(
                club_id=club.id,
                user_id=request.user_id,
                role="member",
            ))
        request.status = "approved"
    else:
        request.status = "rejected"

    request.responded_at = utcnow_naive()
    request.responded_by = responder.id
    db.commit()
    db.refresh(request)
    _notify_club_request_outcome(db, request, action, responder)
    if action == "approve":
        evaluate_member_count_achievements(db, club)
    return request, None

def kick_member(
    db: Session, actor: models.User, club: models.Club, target_user_id: int
) -> tuple[bool, Optional[str]]:
    """Remove a member from a club.

    Permission rules:
      - Owner can kick anyone except themselves (must delete club to leave).
      - Admin can kick role="member" only.
      - Any user can leave (kick themselves) unless they are the owner.
    """
    actor_membership = get_club_membership(db, club.id, actor.id)
    target_membership = get_club_membership(db, club.id, target_user_id)
    if not target_membership:
        return False, "not_member"

    is_self = actor.id == target_user_id
    actor_role = actor_membership.role if actor_membership else None
    target_role = target_membership.role

    if is_self:
        if target_role == "owner":
            return False, "owner_cannot_leave"
    else:
        if actor_role == "owner":
            if target_role == "owner":
                return False, "cannot_kick_self"
        elif actor_role == "admin":
            if target_role != "member":
                return False, "not_allowed"
        else:
            return False, "not_allowed"

    db.delete(target_membership)
    db.commit()
    if not is_self:
        create_notification(
            db=db,
            user_id=target_user_id,
            notif_type="club_kicked",
            title="Ai fost scos dintr-un club",
            message=f"Nu mai faci parte din clubul „{club.title}\".",
            link=f"/cluburi/{club.slug}",
            extra_data={"club_id": club.id, "club_slug": club.slug},
        )
    return True, None

def update_member_role(
    db: Session,
    actor: models.User,
    club: models.Club,
    target_user_id: int,
    role: str,
) -> tuple[Optional[models.ClubMember], Optional[str]]:
    if role not in ("admin", "member"):
        return None, "bad_role"
    if club.owner_id != actor.id:
        return None, "not_allowed"
    if target_user_id == actor.id:
        return None, "cannot_change_own_role"
    membership = get_club_membership(db, club.id, target_user_id)
    if not membership:
        return None, "not_member"
    if membership.role == "owner":
        return None, "cannot_change_owner_role"
    if membership.role == role:
        return membership, None
    membership.role = role
    db.commit()
    db.refresh(membership)
    create_notification(
        db=db,
        user_id=target_user_id,
        notif_type="club_role_changed",
        title="Rolul tău în club s-a schimbat",
        message=(
            f"Ai fost numit administrator în clubul „{club.title}\"."
            if role == "admin"
            else f"Nu mai ești administrator în clubul „{club.title}\"."
        ),
        link=f"/cluburi/{club.slug}",
        extra_data={"club_id": club.id, "club_slug": club.slug, "role": role},
    )
    return membership, None

def set_featured_post(
    db: Session, actor: models.User, club: models.Club, post_id: int
) -> tuple[Optional[models.Post], Optional[str]]:
    if club.owner_id != actor.id:
        return None, "not_allowed"
    post = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
        models.Post.id == post_id
    ).first()
    if not post:
        return None, "post_not_found"
    if post.moderation_status != "approved":
        return None, "post_not_approved"
    if post.category != club.speciality:
        return None, "speciality_mismatch"
    if not get_club_membership(db, club.id, post.user_id):
        return None, "author_not_member"
    club.featured_post_id = post.id
    club.featured_until = utcnow_naive() + CLUB_FEATURED_DURATION
    db.commit()
    db.refresh(club)
    if post.user_id != actor.id:
        create_notification(
            db=db,
            user_id=post.user_id,
            notif_type="club_featured",
            title="Postarea ta este creația săptămânii",
            message=(
                f"Postarea „{post.title}\" a fost aleasă creația săptămânii "
                f"în clubul „{club.title}\"."
            ),
            link=f"/cluburi/{club.slug}",
            extra_data={"club_id": club.id, "club_slug": club.slug, "post_id": post.id},
        )
    ensure_club_achievement(db, club, "creatia_saptamanii")
    return post, None

def clear_featured_post(db: Session, actor: models.User, club: models.Club) -> tuple[bool, Optional[str]]:
    if club.owner_id != actor.id:
        return False, "not_allowed"
    club.featured_post_id = None
    club.featured_until = None
    db.commit()
    return True, None

def get_active_featured(db: Session, club: models.Club):
    """Return (post, featured_until) if a featured post is currently active.

    Implements read-time expiry: if featured_until is in the past, lazily
    clear the columns and return None.
    """
    if not club.featured_post_id or not club.featured_until:
        return None
    if club.featured_until <= utcnow_naive():
        # Best-effort cleanup; don't block the read on the write.
        try:
            club.featured_post_id = None
            club.featured_until = None
            db.commit()
        except Exception:
            db.rollback()
        return None
    post = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
        models.Post.id == club.featured_post_id
    ).first()
    if not post:
        return None
    return post, club.featured_until

def list_board_messages(
    db: Session, club_id: int, *, limit: int = 50, offset: int = 0
) -> List[models.ClubBoardMessage]:
    """Return top-level messages newest-first; replies eager-loaded per message."""
    top_level = (
        db.query(models.ClubBoardMessage)
        .options(
            joinedload(models.ClubBoardMessage.author),
            joinedload(models.ClubBoardMessage.replies).joinedload(models.ClubBoardMessage.author),
        )
        .filter(
            models.ClubBoardMessage.club_id == club_id,
            models.ClubBoardMessage.parent_id.is_(None),
        )
        .order_by(models.ClubBoardMessage.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return top_level

def get_board_message(db: Session, message_id: int) -> Optional[models.ClubBoardMessage]:
    return (
        db.query(models.ClubBoardMessage)
        .options(joinedload(models.ClubBoardMessage.author))
        .filter(models.ClubBoardMessage.id == message_id)
        .first()
    )

def post_board_message(
    db: Session,
    author: models.User,
    club: models.Club,
    content: str,
    title: Optional[str] = None,
    parent_id: Optional[int] = None,
) -> tuple[Optional[models.ClubBoardMessage], Optional[str]]:
    if not get_club_membership(db, club.id, author.id):
        return None, "not_member"
    cleaned_title = (title or "").strip()
    cleaned_content = content.strip()
    if not cleaned_content:
        return None, "empty_content"
    if parent_id is not None:
        parent = get_board_message(db, parent_id)
        if not parent or parent.club_id != club.id:
            return None, "bad_parent"
        # Don't allow nesting beyond one level; replies-of-replies are flattened
        # to siblings of the original reply (frontend renders as a single thread).
        if parent.parent_id is not None:
            parent_id = parent.parent_id
        cleaned_title = None
    elif not cleaned_title:
        return None, "missing_title"
    msg = models.ClubBoardMessage(
        club_id=club.id,
        author_id=author.id,
        parent_id=parent_id,
        title=cleaned_title,
        content=cleaned_content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    if parent_id is None:
        if db.query(models.ClubBoardMessage).filter(
            models.ClubBoardMessage.club_id == club.id,
            models.ClubBoardMessage.parent_id.is_(None),
        ).count() == 1:
            ensure_club_achievement(db, club, "atelier_deschis")
        _notify_club_board_activity(db, club, author, msg, is_reply=False)
    else:
        _notify_club_board_activity(db, club, author, msg, is_reply=True)
    if count_club_board_messages(db, club.id) >= 25:
        ensure_club_achievement(db, club, "dialog_viu")
    return msg, None

def delete_board_message(
    db: Session, actor: models.User, message: models.ClubBoardMessage
) -> tuple[bool, Optional[str]]:
    if actor.id == message.author_id:
        allowed = True
    elif getattr(actor, "is_admin", False):
        allowed = True
    else:
        membership = get_club_membership(db, message.club_id, actor.id)
        allowed = bool(membership and membership.role in ("owner", "admin"))
    if not allowed:
        return False, "not_allowed"
    db.delete(message)
    db.commit()
    return True, None

def list_user_clubs(db: Session, user_id: int) -> List[models.Club]:
    """All clubs the user belongs to (any role)."""
    return (
        db.query(models.Club)
        .options(joinedload(models.Club.owner))
        .join(models.ClubMember, models.ClubMember.club_id == models.Club.id)
        .filter(models.ClubMember.user_id == user_id)
        .order_by(models.Club.created_at.desc())
        .all()
    )

def list_user_pending_invitations(db: Session, user_id: int) -> List[models.ClubJoinRequest]:
    return (
        db.query(models.ClubJoinRequest)
        .options(
            joinedload(models.ClubJoinRequest.club).joinedload(models.Club.owner),
            joinedload(models.ClubJoinRequest.user),
        )
        .filter(
            models.ClubJoinRequest.user_id == user_id,
            models.ClubJoinRequest.status == "pending",
            models.ClubJoinRequest.direction == "invitation",
        )
        .order_by(models.ClubJoinRequest.created_at.desc())
        .all()
    )

def list_club_pending_requests(db: Session, club_id: int) -> List[models.ClubJoinRequest]:
    return (
        db.query(models.ClubJoinRequest)
        .options(
            joinedload(models.ClubJoinRequest.user),
            joinedload(models.ClubJoinRequest.initiator),
        )
        .filter(
            models.ClubJoinRequest.club_id == club_id,
            models.ClubJoinRequest.status == "pending",
        )
        .order_by(models.ClubJoinRequest.created_at.desc())
        .all()
    )

def get_club_join_request(db: Session, request_id: int) -> Optional[models.ClubJoinRequest]:
    return (
        db.query(models.ClubJoinRequest)
        .options(
            joinedload(models.ClubJoinRequest.club),
            joinedload(models.ClubJoinRequest.user),
            joinedload(models.ClubJoinRequest.initiator),
        )
        .filter(models.ClubJoinRequest.id == request_id)
        .first()
    )

def count_pending_requests_for_club(db: Session, club_id: int) -> int:
    return (
        db.query(models.ClubJoinRequest)
        .filter(
            models.ClubJoinRequest.club_id == club_id,
            models.ClubJoinRequest.status == "pending",
        )
        .count()
    )


# ----- club achievements -----

def achievement_definition(key: str) -> dict:
    return CLUB_ACHIEVEMENT_DEFINITIONS.get(key, {
        "label": key.replace("_", " ").title(),
        "description": "Insignă de club.",
    })


def list_club_achievements(db: Session, club_id: int) -> List[models.ClubAchievement]:
    return (
        db.query(models.ClubAchievement)
        .filter(models.ClubAchievement.club_id == club_id)
        .order_by(models.ClubAchievement.unlocked_at.asc(), models.ClubAchievement.id.asc())
        .all()
    )


def ensure_club_achievement(
    db: Session, club: models.Club, key: str
) -> Optional[models.ClubAchievement]:
    if key not in CLUB_ACHIEVEMENT_DEFINITIONS:
        return None
    existing = db.query(models.ClubAchievement).filter(
        models.ClubAchievement.club_id == club.id,
        models.ClubAchievement.key == key,
    ).first()
    if existing:
        return existing
    achievement = models.ClubAchievement(club_id=club.id, key=key)
    db.add(achievement)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(models.ClubAchievement).filter(
            models.ClubAchievement.club_id == club.id,
            models.ClubAchievement.key == key,
        ).first()
    db.refresh(achievement)
    _notify_club_achievement_unlocked(db, club, achievement)
    return achievement


def evaluate_member_count_achievements(db: Session, club: models.Club) -> None:
    if count_club_members(db, club.id) >= 5:
        ensure_club_achievement(db, club, "cerc_de_cinci")


# ----- club notification helpers -----

def _admin_memberships(db: Session, club_id: int) -> List[models.ClubMember]:
    return (
        db.query(models.ClubMember)
        .filter(
            models.ClubMember.club_id == club_id,
            models.ClubMember.role.in_(("owner", "admin")),
        )
        .all()
    )


def _member_user_ids(db: Session, club_id: int) -> List[int]:
    return [
        item[0]
        for item in db.query(models.ClubMember.user_id)
        .filter(models.ClubMember.club_id == club_id)
        .all()
    ]


def _notify_club_open_join_to_admins(
    db: Session,
    club: models.Club,
    member: models.User,
) -> None:
    for m in _admin_memberships(db, club.id):
        if m.user_id == member.id:
            continue
        create_notification(
            db=db,
            user_id=m.user_id,
            notif_type="club_member_joined",
            title="Membru nou în club",
            message=f"{member.username} s-a alăturat clubului „{club.title}\".",
            link=f"/cluburi/{club.slug}",
            extra_data={
                "club_id": club.id,
                "club_slug": club.slug,
                "member_username": member.username,
            },
        )


def _notify_club_board_activity(
    db: Session,
    club: models.Club,
    author: models.User,
    message: models.ClubBoardMessage,
    *,
    is_reply: bool,
) -> None:
    title = "Răspuns nou în club" if is_reply else "Fir nou în club"
    subject = message.title or "discuția de pe tablă"
    body = (
        f"{author.username} a răspuns în „{subject}\"."
        if is_reply
        else f"{author.username} a deschis firul „{subject}\"."
    )
    notif_type = "club_board_reply" if is_reply else "club_board_thread"
    for user_id in _member_user_ids(db, club.id):
        if user_id == author.id:
            continue
        create_notification(
            db=db,
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            message=body,
            link=f"/cluburi/{club.slug}#club-message-{message.id}",
            extra_data={
                "club_id": club.id,
                "club_slug": club.slug,
                "message_id": message.id,
                "is_reply": is_reply,
            },
        )


def _notify_club_achievement_unlocked(
    db: Session,
    club: models.Club,
    achievement: models.ClubAchievement,
) -> None:
    definition = achievement_definition(achievement.key)
    for user_id in _member_user_ids(db, club.id):
        create_notification(
            db=db,
            user_id=user_id,
            notif_type="club_achievement_unlocked",
            title=f"Insignă nouă pentru „{club.title}\"",
            message=f"Clubul a deblocat insigna „{definition['label']}\".",
            link=f"/cluburi/{club.slug}",
            extra_data={
                "club_id": club.id,
                "club_slug": club.slug,
                "achievement_key": achievement.key,
            },
        )

def _notify_club_application_to_admins(
    db: Session,
    club: models.Club,
    applicant: models.User,
    request: models.ClubJoinRequest,
) -> None:
    for m in _admin_memberships(db, club.id):
        if m.user_id == applicant.id:
            continue
        create_notification(
            db=db,
            user_id=m.user_id,
            notif_type="club_application_received",
            title="Cerere de aderare la club",
            message=f"{applicant.username} dorește să se alăture clubului „{club.title}\".",
            link=f"/cluburi/{club.slug}",
            extra_data={
                "club_id": club.id,
                "club_slug": club.slug,
                "request_id": request.id,
                "applicant_username": applicant.username,
            },
        )

def _notify_club_invitation_to_target(
    db: Session,
    club: models.Club,
    inviter: models.User,
    target: models.User,
    request: models.ClubJoinRequest,
) -> None:
    create_notification(
        db=db,
        user_id=target.id,
        notif_type="club_invitation_received",
        title="Invitație într-un club",
        message=f"{inviter.username} te-a invitat în clubul „{club.title}\".",
        link=f"/cluburi/{club.slug}",
        extra_data={
            "club_id": club.id,
            "club_slug": club.slug,
            "request_id": request.id,
            "inviter_username": inviter.username,
        },
    )

def _notify_club_request_outcome(
    db: Session,
    request: models.ClubJoinRequest,
    action: str,
    responder: models.User,
) -> None:
    club = request.club
    # Notify the user who initiated the request.
    target_user_id = request.initiator_id
    if request.direction == "application":
        if action == "approve":
            title = "Cererea ta a fost acceptată"
            message = f"Faci acum parte din clubul „{club.title}\"."
            notif_type = "club_application_approved"
        else:
            title = "Cererea ta a fost respinsă"
            message = f"Cererea ta către clubul „{club.title}\" a fost respinsă."
            notif_type = "club_application_rejected"
    else:  # invitation
        # For invitations, notify the original inviter about the invitee's decision.
        if action == "approve":
            title = "Invitație acceptată"
            message = f"{request.user.username} s-a alăturat clubului „{club.title}\"."
            notif_type = "club_invitation_accepted"
        else:
            title = "Invitație refuzată"
            message = f"{request.user.username} a refuzat invitația în clubul „{club.title}\"."
            notif_type = "club_invitation_declined"

    create_notification(
        db=db,
        user_id=target_user_id,
        notif_type=notif_type,
        title=title,
        message=message,
        link=f"/cluburi/{club.slug}",
        extra_data={
            "club_id": club.id,
            "club_slug": club.slug,
            "request_id": request.id,
        },
    )
