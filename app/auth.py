import os
import logging # Import logging
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from . import crud, models, schemas
from .database import get_db

# Get logger instance from main.py (or configure separately if needed)
logger = logging.getLogger(__name__)

# No JWT configuration needed for session-based auth

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    logger.info("get_current_user called (session-based).")
    user_id = request.session.get("user_id")
    
    if user_id is None:
        logger.info("No user_id found in session.")
        # For HTML routes, we don't raise HTTPException 401, just return None
        # For API routes that require auth, they will handle None or raise their own 401
        return None 

    user = crud.get_user_by_id(db, user_id=user_id)
    if user is None:
        logger.warning(f"User not found in DB for session user_id: {user_id}. Clearing session.")
        request.session.clear() # Clear invalid session
        return None
    
    logger.info(f"Current user retrieved from session: {user.username}")
    return user

# This dependency is for API routes that *require* a logged-in user
async def get_required_user(current_user: models.User = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}, # Still use Bearer for consistency, though not strictly JWT
        )
    return current_user
