from ._shared import *
from .users import get_user_by_username

SYSTEM_USERNAME = "sistemcalimara"
SYSTEM_EMAIL = "system@calimara.local"
SYSTEM_AVATAR_SEED = "calimara-system"


def _conversation_access_filter(user_id: int):
    return or_(
        models.Conversation.user1_id == user_id,
        models.Conversation.user2_id == user_id,
    )

def _ordered_participants(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)

def _message_recipient_id(conversation: models.Conversation, sender_id: int) -> Optional[int]:
    if conversation.user1_id == sender_id:
        return conversation.user2_id
    if conversation.user2_id == sender_id:
        return conversation.user1_id
    return None


def _system_sender_name(sender: Optional[models.User]) -> str:
    if sender and getattr(sender, "is_system", False):
        return "Călimara"
    return sender.username if sender else "Un utilizator"


def get_or_create_system_user(db: Session) -> models.User:
    system_user = (
        db.query(models.User)
        .filter(models.User.username == SYSTEM_USERNAME)
        .first()
    )
    if system_user:
        if not system_user.is_system:
            raise ValueError("Contul de sistem pentru suport nu poate fi creat.")
        return system_user

    conflicting_user = (
        db.query(models.User)
        .filter(models.User.email == SYSTEM_EMAIL)
        .first()
    )
    if conflicting_user:
        if not conflicting_user.is_system:
            raise ValueError("Contul de sistem pentru suport nu poate fi creat.")
        return conflicting_user

    system_user = models.User(
        username=SYSTEM_USERNAME,
        email=SYSTEM_EMAIL,
        avatar_seed=SYSTEM_AVATAR_SEED,
        subtitle="Mesaje de la echipa Călimara",
        is_system=True,
    )
    db.add(system_user)
    db.flush()
    return system_user


def _get_or_create_conversation_between(db: Session, user_a_id: int, user_b_id: int) -> models.Conversation:
    user1_id, user2_id = _ordered_participants(user_a_id, user_b_id)
    conversation = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.user1_id == user1_id,
            models.Conversation.user2_id == user2_id,
        )
        .first()
    )
    if conversation is None:
        conversation = models.Conversation(user1_id=user1_id, user2_id=user2_id)
        db.add(conversation)
        db.flush()
    return conversation

def _add_message_notification(
    db: Session,
    *,
    conversation: models.Conversation,
    message: models.Message,
    sender: Optional[models.User],
) -> None:
    recipient_id = _message_recipient_id(conversation, message.sender_id)
    if not recipient_id:
        return
    recipient = db.query(models.User).filter(models.User.id == recipient_id).first()
    if recipient and getattr(recipient, "is_system", False):
        return
    sender_username = _system_sender_name(sender)
    db.add(
        models.Notification(
            user_id=recipient_id,
            type="private_message",
            title="Mesaj nou",
            message=f"{sender_username} ți-a trimis un mesaj privat.",
            link="/mesaje",
            extra_data={
                "source_type": "message",
                "conversation_id": conversation.id,
                "message_id": message.id,
                "sender_id": message.sender_id,
                "sender_username": sender_username,
            },
        )
    )


def _feedback_context_content(feedback: models.SiteFeedback) -> str:
    kind_label = "Bug" if feedback.kind == "bug" else "Feedback"
    lines = [
        f"Sesizare trimisă către Călimara ({kind_label}):",
        "",
        feedback.message or "",
    ]
    if feedback.page_url:
        lines.extend(["", f"Pagina: {feedback.page_url}"])
    return "\n".join(lines).strip()


def _conversation_has_feedback_context(db: Session, conversation_id: int, feedback: models.SiteFeedback) -> bool:
    context = _feedback_context_content(feedback)
    return (
        db.query(models.Message.id)
        .filter(
            models.Message.conversation_id == conversation_id,
            models.Message.sender_id == feedback.user_id,
            models.Message.content == context,
        )
        .first()
        is not None
    )


def reply_to_site_feedback(
    db: Session,
    feedback: models.SiteFeedback,
    *,
    admin_user: models.User,
    content: str,
) -> models.Message:
    if not feedback.user_id:
        raise ValueError("Sesizarea nu are un utilizator atașat.")

    recipient = db.query(models.User).filter(models.User.id == feedback.user_id).first()
    if not recipient or recipient.is_suspended or getattr(recipient, "is_system", False):
        raise ValueError("Utilizatorul sesizării nu poate primi mesaje.")

    system_user = get_or_create_system_user(db)
    conversation = None
    if feedback.support_conversation_id:
        conversation = db.query(models.Conversation).filter(
            models.Conversation.id == feedback.support_conversation_id
        ).first()
    if conversation is None:
        conversation = _get_or_create_conversation_between(db, recipient.id, system_user.id)
        feedback.support_conversation_id = conversation.id

    if not feedback.support_started_at:
        if not _conversation_has_feedback_context(db, conversation.id, feedback):
            db.add(
                models.Message(
                    conversation_id=conversation.id,
                    sender_id=recipient.id,
                    content=_feedback_context_content(feedback),
                    is_read=True,
                )
            )
        feedback.support_started_at = utcnow_naive()

    message = models.Message(
        conversation_id=conversation.id,
        sender_id=system_user.id,
        content=content,
    )
    db.add(message)
    conversation.updated_at = func.now()
    db.flush()
    _add_message_notification(db, conversation=conversation, message=message, sender=system_user)
    return message


def get_site_feedback_unread_reply_count(db: Session, feedback: Optional[models.SiteFeedback] = None) -> int:
    query = db.query(func.count(func.distinct(models.Message.id))).join(
        models.SiteFeedback,
        models.SiteFeedback.support_conversation_id == models.Message.conversation_id,
    ).filter(
        models.SiteFeedback.support_conversation_id != None,
        models.SiteFeedback.user_id != None,
        models.Message.sender_id == models.SiteFeedback.user_id,
        models.Message.is_read == False,
    )
    if feedback is not None:
        query = query.filter(models.SiteFeedback.id == feedback.id)
    return int(query.scalar() or 0)


def mark_site_feedback_replies_as_read(db: Session, feedback: models.SiteFeedback) -> int:
    if not feedback.support_conversation_id or not feedback.user_id:
        return 0
    return db.query(models.Message).filter(
        models.Message.conversation_id == feedback.support_conversation_id,
        models.Message.sender_id == feedback.user_id,
        models.Message.is_read == False,
    ).update({"is_read": True}, synchronize_session=False)

def get_user_conversations(db: Session, user_id: int):
    conversations = db.query(models.Conversation).options(
        joinedload(models.Conversation.user1),
        joinedload(models.Conversation.user2),
        joinedload(models.Conversation.messages),
    ).filter(
        _conversation_access_filter(user_id)
    ).order_by(
        models.Conversation.updated_at.desc()
    ).all()

    for conversation in conversations:
        conversation._latest_message = conversation.get_latest_message()

    return conversations

def get_conversation_by_id(db: Session, conversation_id: int, user_id: int):
    return db.query(models.Conversation).options(
        joinedload(models.Conversation.user1),
        joinedload(models.Conversation.user2),
    ).filter(
        models.Conversation.id == conversation_id,
        _conversation_access_filter(user_id),
    ).first()

def get_conversation_messages(db: Session, conversation_id: int, user_id: int, limit: int = 50, offset: int = 0):
    if not get_conversation_by_id(db, conversation_id, user_id):
        return []

    return db.query(models.Message).options(
        joinedload(models.Message.sender)
    ).filter(
        models.Message.conversation_id == conversation_id
    ).order_by(
        models.Message.created_at.desc(),
        models.Message.id.desc(),
    ).offset(offset).limit(limit).all()

def mark_messages_as_read(db: Session, conversation_id: int, user_id: int):
    if not get_conversation_by_id(db, conversation_id, user_id):
        return 0

    updated_count = db.query(models.Message).filter(
        models.Message.conversation_id == conversation_id,
        models.Message.sender_id != user_id,
        models.Message.is_read == False,
    ).update({"is_read": True}, synchronize_session=False)
    db.commit()
    return updated_count

def create_message(db: Session, conversation_id: int, sender_id: int, content: str):
    conversation = get_conversation_by_id(db, conversation_id, sender_id)
    if not conversation:
        return None

    message = models.Message(
        conversation_id=conversation.id,
        sender_id=sender_id,
        content=content,
    )
    sender = db.query(models.User).filter(models.User.id == sender_id).first()
    db.add(message)
    conversation.updated_at = func.now()
    db.flush()
    _add_message_notification(db, conversation=conversation, message=message, sender=sender)
    db.commit()
    db.refresh(message)
    return message

def send_message_to_user(db: Session, sender_id: int, recipient_username: str, content: str):
    recipient = get_user_by_username(db, recipient_username.strip())
    if recipient is None or recipient.id == sender_id or getattr(recipient, "is_system", False):
        return None

    conversation = _get_or_create_conversation_between(db, sender_id, recipient.id)

    sender = db.query(models.User).filter(models.User.id == sender_id).first()
    message = models.Message(
        conversation_id=conversation.id,
        sender_id=sender_id,
        content=content,
    )
    db.add(message)
    conversation.updated_at = func.now()
    db.flush()
    _add_message_notification(db, conversation=conversation, message=message, sender=sender)
    db.commit()
    db.refresh(message)
    return message

def get_unread_message_count(db: Session, user_id: int):
    return db.query(models.Message).join(
        models.Conversation,
        models.Message.conversation_id == models.Conversation.id,
    ).filter(
        _conversation_access_filter(user_id),
        models.Message.sender_id != user_id,
        models.Message.is_read == False,
    ).count()

def delete_conversation(db: Session, conversation_id: int, user_id: int):
    conversation = get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        return False

    db.delete(conversation)
    db.commit()
    return True

def search_conversations(db: Session, user_id: int, q: str):
    normalized_query = q.strip().lower()
    if not normalized_query:
        return get_user_conversations(db, user_id)

    matches = []
    for conversation in get_user_conversations(db, user_id):
        other_user = conversation.get_other_user(user_id)
        username_matches = normalized_query in other_user.username.lower()
        message_matches = any(
            normalized_query in (message.content or "").lower()
            for message in conversation.messages
        )
        if username_matches or message_matches:
            matches.append(conversation)
    return matches

# ===================================
# NOTIFICATION CRUD FUNCTIONS
# ===================================
