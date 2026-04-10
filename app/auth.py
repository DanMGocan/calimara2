import logging
from typing import Optional
from pathlib import Path
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from . import crud, models
from .database import get_db

logger = logging.getLogger(__name__)

# DB epoch: invalidates stale sessions after database reinitialization
_DB_EPOCH_FILE = Path(__file__).parent.parent / ".db_epoch"
_db_epoch_cache = None


def get_db_epoch() -> str:
    global _db_epoch_cache
    if _db_epoch_cache is None:
        try:
            _db_epoch_cache = _DB_EPOCH_FILE.read_text().strip()
        except FileNotFoundError:
            _db_epoch_cache = ""
    return _db_epoch_cache


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    # Invalidate sessions from before the last DB reinitialization
    session_epoch = request.session.get("db_epoch")
    current_epoch = get_db_epoch()
    if current_epoch and session_epoch != current_epoch:
        request.session.clear()
        return None

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
