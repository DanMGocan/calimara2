import logging

from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from .. import models, schemas, crud, auth
from ..database import get_db

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter(tags=["messages"])


@router.get("/api/messages/conversations")
async def get_user_conversations_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get all conversations for the current user"""
    try:
        conversations = crud.get_user_conversations(db, current_user.id)

        # Format conversations for frontend
        formatted_conversations = []
        for conv in conversations:
            other_user = conv.get_other_user(current_user.id)
            latest_message = getattr(conv, '_latest_message', None)

            # Count unread messages from the other user in this conversation
            unread_count = db.query(func.count(models.Message.id)).filter(
                models.Message.conversation_id == conv.id,
                models.Message.sender_id != current_user.id,
                models.Message.is_read == False
            ).scalar() or 0

            formatted_conversations.append({
                "id": conv.id,
                "other_user": {
                    "id": other_user.id,
                    "username": other_user.username,
                    "subtitle": other_user.subtitle,
                    "avatar_seed": other_user.avatar_seed
                },
                "latest_message": {
                    "id": latest_message.id,
                    "content": latest_message.content[:100] + "..." if len(latest_message.content) > 100 else latest_message.content,
                    "sender_id": latest_message.sender_id,
                    "created_at": latest_message.created_at.isoformat(),
                    "is_read": latest_message.is_read
                } if latest_message else None,
                "unread_count": unread_count,
                "updated_at": conv.updated_at.isoformat()
            })

        return {"conversations": formatted_conversations}

    except Exception as e:
        logger.error(f"Eroare la obținerea conversațiilor pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversations")


@router.get("/api/messages/conversations/{conversation_id}")
async def get_conversation_messages_api(
    conversation_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get messages for a specific conversation"""
    try:
        # Verify user has access to this conversation
        conversation = crud.get_conversation_by_id(db, conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = crud.get_conversation_messages(db, conversation_id, current_user.id, limit, offset)

        # Mark messages as read
        crud.mark_messages_as_read(db, conversation_id, current_user.id)

        # Get other user info
        other_user = conversation.get_other_user(current_user.id)

        # Format messages for frontend
        formatted_messages = []
        for message in reversed(messages):  # Reverse to show oldest first
            formatted_messages.append({
                "id": message.id,
                "conversation_id": message.conversation_id,
                "sender_id": message.sender_id,
                "content": message.content,
                "is_read": message.is_read,
                "created_at": message.created_at.isoformat(),
                "is_mine": message.sender_id == current_user.id
            })

        return {
            "conversation": {
                "id": conversation.id,
                "other_user": {
                    "id": other_user.id,
                    "username": other_user.username,
                    "subtitle": other_user.subtitle,
                    "avatar_seed": other_user.avatar_seed
                }
            },
            "messages": formatted_messages
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la obținerea mesajelor pentru conversația {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get messages")


@router.post("/api/messages/conversations/{conversation_id}")
@limiter.limit("20/minute")
async def send_message_api(
    request: Request,
    conversation_id: int,
    message_data: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Send a message in an existing conversation"""
    try:
        message = crud.create_message(db, conversation_id, current_user.id, message_data.content)
        if not message:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")

        return {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "is_read": message.is_read,
            "created_at": message.created_at.isoformat(),
            "is_mine": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la trimiterea mesajului în conversația {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.post("/api/messages/send")
@limiter.limit("20/minute")
async def send_message_to_user_api(
    request: Request,
    message_data: schemas.MessageToUser,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Send a message to a user by username (creates conversation if needed)"""
    try:
        message = crud.send_message_to_user(
            db, current_user.id, message_data.recipient_username, message_data.content
        )
        if not message:
            raise HTTPException(status_code=404, detail="Recipient not found or cannot message yourself")

        return {
            "message": "Message sent successfully",
            "conversation_id": message.conversation_id,
            "message_id": message.id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la trimiterea mesajului către {message_data.recipient_username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.get("/api/messages/unread-count")
async def get_unread_count_api(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Get count of unread messages for current user"""
    try:
        count = crud.get_unread_message_count(db, current_user.id)
        return {"unread_count": count}

    except Exception as e:
        logger.error(f"Eroare la obținerea numărului de mesaje necitite pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get unread count")


@router.delete("/api/messages/conversations/{conversation_id}")
async def delete_conversation_api(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Delete a conversation"""
    try:
        success = crud.delete_conversation(db, conversation_id, current_user.id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Eroare la ștergerea conversației {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@router.get("/api/messages/search")
async def search_conversations_api(
    q: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_required_user)
):
    """Search conversations by user or message content"""
    try:
        conversations = crud.search_conversations(db, current_user.id, q)

        # Format conversations for frontend
        formatted_conversations = []
        for conv in conversations:
            other_user = conv.get_other_user(current_user.id)
            latest_message = conv.get_latest_message()

            formatted_conversations.append({
                "id": conv.id,
                "other_user": {
                    "id": other_user.id,
                    "username": other_user.username,
                    "subtitle": other_user.subtitle,
                    "avatar_seed": other_user.avatar_seed
                },
                "latest_message": {
                    "content": latest_message.content[:100] + "..." if len(latest_message.content) > 100 else latest_message.content,
                    "created_at": latest_message.created_at.isoformat()
                } if latest_message else None
            })

        return {"conversations": formatted_conversations}

    except Exception as e:
        logger.error(f"Eroare la căutarea conversațiilor pentru {current_user.username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to search conversations")
