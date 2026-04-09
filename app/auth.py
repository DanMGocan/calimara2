import logging
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from . import crud, models
from .database import get_db

logger = logging.getLogger(__name__)


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")

    if user_id is None:
        return None

    user = crud.get_user_by_id(db, user_id=user_id)
    if user is None:
        logger.debug(f"User not found for session user_id={user_id}, clearing session.")
        request.session.clear()
        return None

    return user


async def get_required_user(current_user: models.User = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Neautentificat",
        )
    return current_user
