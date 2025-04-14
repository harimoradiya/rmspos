from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from models.user import User, UserRole
from models.restaurant_chain import RestaurantChain
from datetime import datetime, timedelta
from jose import JWTError, jwt
from utils.auth import get_current_user, get_current_active_user, get_current_owner
from database import get_db
from models.user import User
from schemas.user import UserCreate, UserResponse, UserUpdate, Token, LoginRequest
from utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,generate_unique_pin,
    require_role
    )
import logging
import os
SUPER_ADMIN_SECRET_KEY = os.getenv("SECRET_KEY")

bearer_scheme = HTTPBearer()

router = APIRouter(prefix="/api/v1/users", tags=["users"])

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)



@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserCreate, 
    admin_secret: Optional[str] = None,  # Accept secret key in request body
    db: Session = Depends(get_db), 
):
    try:
        logger.info("Registering user")
        logger.info(f"Super Admin Secret: {SUPER_ADMIN_SECRET_KEY}")
        super_admin_exists = db.query(User).filter(User.role == UserRole.SUPERADMIN.value).first()
    
    # If no Super Admin exists, allow creation ONLY if the correct secret key is provided
        if not super_admin_exists:
                if admin_secret != SUPER_ADMIN_SECRET_KEY:
                    raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid secret key for Super Admin registration. Please contact the system administrator."
                )
                else:
                    user.role = UserRole.SUPERADMIN
                                                        

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            print(f"User exists: {existing_user.email}")  # ✅ Safe to access email
            raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Generate username from email
        base_username = user.email.split('@')[0]
        username = base_username
        counter = 1
        
        # Ensure username is unique
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        # Create new user
        hashed_password = get_password_hash(user.password)
        # Generate unique PIN for the user
        unique_pin = generate_unique_pin(db)
        db_user = User(
            email=user.email,
            username=username,
            hashed_password=hashed_password,
            pin=unique_pin,
            role=user.role.value,
            is_active=True,
            created_at=datetime.utcnow()
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error registering user: {e, str(e)}"
        )

@router.post("/login", response_model=Token)
async def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    try:
        if login_data.pin:
            # PIN-based login
            user = db.query(User).filter(
                User.pin == login_data.pin,
                User.username == login_data.username
            ).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or PIN",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # Username/password login
            user = db.query(User).filter(User.username == login_data.username).first()
            if not user or not verify_password(login_data.password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect username or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        access_token = create_access_token(
            data={"sub": user.username}
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login error: {e, str(e)}"
        )

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@router.get("", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_owner),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None
):
    try:
        # Base query
        query = db.query(User)
        
        # Filter by role if provided
        if role:
            query = query.filter(User.role == role)
        
        # Filter by active status if provided
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # If not super admin, filter by restaurant chains
        if current_user.role != UserRole.SUPERADMIN.value:
            # Correctly extract chain IDs
            chain_ids = [chain.id for chain in current_user.restaurant_chains]
            
            query = query.filter(
                User.restaurant_chains.any(RestaurantChain.id.in_(chain_ids))
            )
        
        users = query.order_by(User.created_at.desc()).all()
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving users: {str(e)}"
        )

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    try:
        # Find user to update
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Authorization check
        if current_user.role != UserRole.SUPERADMIN.value:
            chain_ids = [chain.id for chain in current_user.restaurant_chains]
            if not any(chain.id in chain_ids for chain in db_user.restaurant_chains):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only modify users in your restaurant chains"
                )
        
        # Update user fields
        update_data = user_update.dict(exclude_unset=True)
        
        # Special handling for password update
        if 'password' in update_data:
            update_data['hashed_password'] = get_password_hash(update_data.pop('password'))
        
        # Update specified fields
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        db_user.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(db_user)
        return db_user
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error updating user: {str(e)}"
        )
    
# @router.post("/logout")
# async def logout(
#     token: HTTPBearer = Depends(get_current_user),
#     current_user: User = Depends(get_current_user)
# ):
#     """
#     Logout endpoint to invalidate the current access token
#     """
#     try:
#         # Blacklist the current token
#         blacklist_token(token.credentials)
#         return {"detail": "Successfully logged out"}
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Logout failed: {str(e)}"
#         )

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    try:
        # Find user to delete
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Authorization check
        if current_user.role != UserRole.SUPERADMIN.value:
            chain_ids = [chain.id for chain in current_user.restaurant_chains]
            if not any(chain.id in chain_ids for chain in db_user.restaurant_chains):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only delete users in your restaurant chains"
                )
        
        
        # Find a replacement owner before deleting the user
        DEFAULT_OWNER_ID = (
            db.query(User.id).filter(User.role == UserRole.SUPERADMIN.value).first()
        )
        if not DEFAULT_OWNER_ID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No default owner found. Assign a new owner before deleting this user."
            )
        DEFAULT_OWNER_ID = DEFAULT_OWNER_ID[0]  # Extract ID from tuple

        # Reassign ownership of restaurant chains before deleting the user
        db.query(RestaurantChain).filter(RestaurantChain.owner_id == user_id).update(
            {"owner_id": DEFAULT_OWNER_ID}
        )
        db.commit()  # Ensure ownership is reassigned before deletion

        db.delete(db_user)  # Now delete the user
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting user: {str(e)}"
        )