from ._shared import *


def _ordered_friendship_pair(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)


def _friendship_participant_filter(user_id: int):
    return or_(
        models.Friendship.user1_id == user_id,
        models.Friendship.user2_id == user_id,
    )


def get_friendship_between(db: Session, user_a_id: int, user_b_id: int):
    user1_id, user2_id = _ordered_friendship_pair(user_a_id, user_b_id)
    return (
        db.query(models.Friendship)
        .options(
            joinedload(models.Friendship.user1),
            joinedload(models.Friendship.user2),
            joinedload(models.Friendship.requested_by),
        )
        .filter(
            models.Friendship.user1_id == user1_id,
            models.Friendship.user2_id == user2_id,
        )
        .first()
    )


def create_friend_request(db: Session, requester_id: int, recipient_id: int):
    user1_id, user2_id = _ordered_friendship_pair(requester_id, recipient_id)
    friendship = models.Friendship(
        user1_id=user1_id,
        user2_id=user2_id,
        requested_by_id=requester_id,
        status="pending",
    )
    db.add(friendship)
    db.flush()
    return friendship


def accept_friendship(db: Session, friendship: models.Friendship):
    friendship.status = "accepted"
    friendship.responded_at = utcnow_naive()
    db.add(friendship)
    db.flush()
    return friendship


def delete_friendship(db: Session, friendship: models.Friendship) -> None:
    db.delete(friendship)
    db.flush()


def get_friendships_for_user(db: Session, user_id: int, status: Optional[str] = None):
    query = (
        db.query(models.Friendship)
        .options(
            joinedload(models.Friendship.user1),
            joinedload(models.Friendship.user2),
            joinedload(models.Friendship.requested_by),
        )
        .filter(_friendship_participant_filter(user_id))
    )
    if status:
        query = query.filter(models.Friendship.status == status)
    return query.order_by(models.Friendship.updated_at.desc(), models.Friendship.id.desc()).all()


def get_friend_count_for_user(db: Session, user_id: int) -> int:
    return (
        db.query(models.Friendship.id)
        .join(
            models.User,
            or_(
                and_(
                    models.Friendship.user1_id == user_id,
                    models.Friendship.user2_id == models.User.id,
                ),
                and_(
                    models.Friendship.user2_id == user_id,
                    models.Friendship.user1_id == models.User.id,
                ),
            ),
        )
        .filter(
            _friendship_participant_filter(user_id),
            models.Friendship.status == "accepted",
            models.User.is_suspended == False,
        )
        .count()
    )


def get_incoming_friend_request_count(db: Session, user_id: int) -> int:
    other_user = aliased(models.User)
    return (
        db.query(models.Friendship.id)
        .join(
            other_user,
            or_(
                and_(
                    models.Friendship.user1_id == user_id,
                    models.Friendship.user2_id == other_user.id,
                ),
                and_(
                    models.Friendship.user2_id == user_id,
                    models.Friendship.user1_id == other_user.id,
                ),
            ),
        )
        .filter(
            _friendship_participant_filter(user_id),
            models.Friendship.status == "pending",
            models.Friendship.requested_by_id != user_id,
            other_user.is_suspended == False,
        )
        .count()
    )


def get_friendship_status_for_viewer(db: Session, viewer_id: Optional[int], target_id: int) -> str:
    if not viewer_id:
        return "none"
    if viewer_id == target_id:
        return "self"
    friendship = get_friendship_between(db, viewer_id, target_id)
    if not friendship:
        return "none"
    if friendship.status == "accepted":
        return "friends"
    if friendship.requested_by_id == viewer_id:
        return "outgoing_pending"
    return "incoming_pending"
