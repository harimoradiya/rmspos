from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from typing import List, Optional
from models.user import User, UserRole
from models.restaurant_chain import RestaurantChain
from models.restaurant_outlet import RestaurantOutlet
from datetime import datetime, timedelta
from jose import JWTError, jwt
from utils.auth import get_current_user, get_current_active_user, get_current_owner, get_current_super_admin
from utils.database import get_db
from models.user import User
from schemas.user import UserCreate, UserResponse, UserUpdate, Token, LoginRequest
from sqlalchemy import or_
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



logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/users", tags=["users"])



@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: UserCreate,
    admin_secret: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user, use_cache=False)
):
    try:
        logger.info(f"Attempting to register user with email: {user.email}")

        # Check if a Super Admin exists
        super_admin_exists = db.query(User).filter(User.role == UserRole.SUPERADMIN.value).first()

        # Case 1: No Super Admin exists (first registration)
        if not super_admin_exists:
            if admin_secret != SUPER_ADMIN_SECRET_KEY:
                logger.warning("Invalid secret key provided for first Super Admin registration")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid secret key for Super Admin registration. Please provide the correct secret key."
                )
            # Force role to SUPERADMIN for first user
            if user.role != UserRole.SUPERADMIN:
                logger.info(f"Overriding role to SUPERADMIN for first user: {user.email}")
                user.role = UserRole.SUPERADMIN
        else:
            # Case 2: Super Admin exists, require authenticated Super Admin
            if not current_user or current_user.role != UserRole.SUPERADMIN.value:
                logger.warning(f"Unauthorized registration attempt by user: {current_user.email if current_user else 'None'}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only a Super Admin can register new users"
                )
            # Restrict role assignment
            if user.role == UserRole.SUPERADMIN and admin_secret != SUPER_ADMIN_SECRET_KEY:
                logger.warning(f"Attempt to create Super Admin without valid secret key by {current_user.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Secret key required to create another Super Admin"
                )

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            logger.warning(f"Registration failed: Email already registered: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Validate outlet_id if provided
        if user.outlet_id:
            outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == user.outlet_id).first()
            if not outlet:
                logger.warning(f"Invalid outlet_id {user.outlet_id} provided for user {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Outlet ID {user.outlet_id} not found"
                )
            # Optional: Restrict outlet_id for non-MANAGER roles
            if user.role != UserRole.MANAGER:
                logger.warning(f"Outlet ID provided for non-manager role: {user.role} for user {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Outlet ID can only be assigned to MANAGER role"
                )

        # Generate unique username
        base_username = user.email.split('@')[0]
        username = base_username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        # Create new user
        hashed_password = get_password_hash(user.password)
        unique_pin = generate_unique_pin(db)
        db_user = User(
            email=user.email,
            username=username,
            hashed_password=hashed_password,
            pin=unique_pin,
            role=user.role.value,
            is_active=True,
            created_at=datetime.utcnow(),
            outlet_id=user.outlet_id  # Assign outlet_id
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"User registered successfully: {db_user.email} (ID: {db_user.id}, Role: {db_user.role}, Outlet ID: {db_user.outlet_id})")
        return db_user

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Registration failed for {user.email}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error registering user {user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )
    

# Separate endpoint for initial Super Admin setup
@router.post("/setup-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def setup_super_admin(
    user: UserCreate,
    admin_secret: str,
    db: Session = Depends(get_db)
):
    """
    Initial Super Admin setup - only available when no Super Admin exists
    """
    try:
        logger.info(f"Attempting to setup Super Admin with email: {user.email}")

        # Check if a Super Admin already exists
        super_admin_exists = db.query(User).filter(User.role == UserRole.SUPERADMIN.value).first()
        
        if super_admin_exists:
            logger.warning("Attempt to setup Super Admin when one already exists")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Super Admin already exists. Use the regular registration endpoint."
            )

        # Validate secret key
        if admin_secret != SUPER_ADMIN_SECRET_KEY:
            logger.warning("Invalid secret key provided for Super Admin setup")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid secret key for Super Admin setup"
            )

        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user.email).first()
        if existing_user:
            logger.warning(f"Setup failed: Email already registered: {user.email}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Force role to SUPERADMIN
        user.role = UserRole.SUPERADMIN

        # Generate unique username
        base_username = user.email.split('@')[0]
        username = base_username
        counter = 1
        while db.query(User).filter(User.username == username).first():
            username = f"{base_username}{counter}"
            counter += 1

        # Create Super Admin user
        hashed_password = get_password_hash(user.password)
        unique_pin = generate_unique_pin(db)
        db_user = User(
            email=user.email,
            username=username,
            hashed_password=hashed_password,
            pin=unique_pin,
            role=UserRole.SUPERADMIN.value,
            is_active=True,
            created_at=datetime.utcnow()
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"Super Admin setup successfully: {db_user.email} (ID: {db_user.id})")
        return db_user

    except HTTPException as e:
        db.rollback()
        logger.warning(f"Super Admin setup failed for {user.email}: {e.detail}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error setting up Super Admin {user.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup Super Admin"
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

              # Get outlet IDs under these chains
            outlet_ids = db.query(RestaurantOutlet.id)\
                .filter(RestaurantOutlet.chain_id.in_(chain_ids))\
                .subquery()
            
            # Include:
            # - Staff users assigned to those outlets
            # - Owner themselves
            query = query.filter(
                or_(

                    User.outlet_id.in_(outlet_ids),
                    User.id == current_user.id
                )
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