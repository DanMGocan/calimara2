from ._shared import *
from .users import get_user_by_username

def _conversation_access_filter(user_id: int):
    return or_(
        models.Conversation.user1_id == user_id,
        models.Conversation.user2_id == user_id,
    )

def _ordered_participants(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    return (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)

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
    db.add(message)
    conversation.updated_at = func.now()
    db.commit()
    db.refresh(message)
    return message

def send_message_to_user(db: Session, sender_id: int, recipient_username: str, content: str):
    recipient = get_user_by_username(db, recipient_username.strip())
    if recipient is None or recipient.id == sender_id:
        return None

    user1_id, user2_id = _ordered_participants(sender_id, recipient.id)
    conversation = db.query(models.Conversation).filter(
        models.Conversation.user1_id == user1_id,
        models.Conversation.user2_id == user2_id,
    ).first()

    if conversation is None:
        conversation = models.Conversation(user1_id=user1_id, user2_id=user2_id)
        db.add(conversation)
        db.flush()

    message = models.Message(
        conversation_id=conversation.id,
        sender_id=sender_id,
        content=content,
    )
    db.add(message)
    conversation.updated_at = func.now()
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
