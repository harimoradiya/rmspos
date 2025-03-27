from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models.user import User, UserRole
from schemas.user import TokenData
import os
# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY")  # Load from main.py
ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 1

# Create a bearer scheme instance
bearer_scheme = HTTPBearer()


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Use HTTPBearer for simpler JWT token authentication
bearer_scheme = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def generate_unique_pin(db: Session) -> str:
    """Generate a unique 6-digit PIN that doesn't exist in the database."""
    import random
    while True:
        pin = str(random.randint(100000, 999999))
        if not db.query(User).filter(User.pin == pin).first():
            return pin

def verify_pin(pin: str, user: User) -> bool:
    """Verify if the provided PIN matches the user's PIN."""
    return user and user.pin == pin

# def blacklist_token(token: str, expiration: int = None):
#     """
#     Blacklist a token in Redis
#     :param token: JWT token to blacklist
#     :param expiration: Optional expiration time in seconds
#     """
#     try:
#         if expiration is None:
#             # If no expiration provided, use token's original expiration
#             payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#             expiration = int(payload.get('exp', 3600))  # Default 1 hour if no expiration
        
#         redis_client.setex(f"blacklist:{token}", expiration, 'true')
#     except Exception as e:
#         print(f"Error blacklisting token: {e}")

# def is_token_blacklisted(token: str) -> bool:
#     """
#     Check if a token is blacklisted
#     """
#     return redis_client.exists(f"blacklist:{token}")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check if token is blacklisted
    # if is_token_blacklisted(token.credentials):
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Token is no longer valid. Please login again.",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    
    try:
            # Extract the token from credentials
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError as e:
        if "expired" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise credentials_exception

    user = db.query(User).filter(User.username == token_data.username).first()
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:

    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

async def get_current_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.SUPERADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super admin can perform this action"
        )
    return current_user

async def get_current_owner(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.OWNER.value, UserRole.SUPERADMIN.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only restaurant owners can perform this action"
        )
    return current_user
