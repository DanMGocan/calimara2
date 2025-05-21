import os
from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request # Import Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import crud, models, schemas
from .database import get_db

# Configuration for JWT
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-fallback") # Use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token") # Updated tokenUrl

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES) # Use ACCESS_TOKEN_EXPIRE_MINUTES
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        # No need for username="temp" if not used, just email
        token_data = {"email": email}
    except JWTError:
        raise credentials_exception
    return token_data

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    print("get_current_user called.")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = request.cookies.get("access_token") # Try to get token from cookie
    if token:
        print(f"Token found in cookie: {token[:10]}...") # Log first 10 chars of token
    else:
        # Fallback to Authorization header if not in cookie (e.g., for API calls from other clients)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            print(f"Token found in Authorization header: {token[:10]}...")
    
    if not token:
        print("No token found in cookie or Authorization header.")
        raise credentials_exception

    try:
        token_data = verify_token(token, credentials_exception)
        print(f"Token verified for email: {token_data['email']}")
    except HTTPException as e:
        print(f"Token verification failed: {e.detail}")
        raise e
    except Exception as e:
        print(f"Unexpected error during token verification: {e}")
        raise credentials_exception

    user = crud.get_user_by_email(db, email=token_data["email"])
    if user is None:
        print(f"User not found for email: {token_data['email']}")
        raise credentials_exception
    print(f"Current user retrieved: {user.username}")
    return user
