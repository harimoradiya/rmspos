from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional
import shutil
import os

from database import get_db
from models.restaurant_chain import RestaurantChain
from models.restaurant_outlet import RestaurantOutlet
from models.user import User

from schemas.restaurant_chain import (
    RestaurantChainCreate, 
    RestaurantChainResponse, 
    RestaurantChainUpdate, 
    RestaurantChainDetailResponse
)
from utils.auth import get_current_owner, get_current_active_user
from utils.validators import validate_name_uniqueness

router = APIRouter(prefix="/api/v1/restaurant-chains", tags=["restaurant-chains"])

@router.post("", response_model=RestaurantChainResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant_chain(
    chain: RestaurantChainCreate,
    logo: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    try:
        # Validate chain name uniqueness
        validate_name_uniqueness(db, RestaurantChain, chain.name, current_user.id)
        
        # Handle logo upload if provided
        logo_url = None
        if logo:
            # Validate file type
            if not logo.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File must be an image"
                )
            
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(os.getcwd(), 'static', 'uploads', 'logos')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Generate unique filename
            file_extension = os.path.splitext(logo.filename)[1]
            logo_filename = f"{chain.name.lower().replace(' ', '_')}_{current_user.id}{file_extension}"
            file_path = os.path.join(upload_dir, logo_filename)
            
            # Save the file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(logo.file, buffer)
            
            # Set the logo URL
            logo_url = f"/static/uploads/logos/{logo_filename}"
        
        # Create new restaurant chain
        db_chain = RestaurantChain(
            name=chain.name,
            owner_id=current_user.id,
            status=chain.status,
            logo_url=logo_url
        )
        
        db.add(db_chain)
        db.commit()
        db.refresh(db_chain)
        return db_chain
    
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A restaurant chain with this name already exists"
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.get("", response_model=List[RestaurantChainResponse])
async def list_restaurant_chains(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_owner),
    status: Optional[str] = None,
    name: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    List restaurant chains with optional filtering and pagination
    """
    try:
        query = db.query(RestaurantChain).filter(RestaurantChain.owner_id == current_user.id)
        
        # Apply filters
        if status:
            query = query.filter(RestaurantChain.status == status)
        
        if name:
            query = query.filter(RestaurantChain.name.ilike(f"%{name}%"))
        
        # Apply pagination
        total_count = query.count()
        chains = query.offset(offset).limit(limit).all()
        
        return chains
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.get("/{chain_id}", response_model=RestaurantChainResponse)
async def get_restaurant_chain(
    chain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    """
    Get detailed information about a specific restaurant chain
    """
    try:
        # Fetch chain with associated restaurants
        chain = db.query(RestaurantChain).options(
            joinedload(RestaurantChain.outlets)  # Assuming a relationship exists
        ).filter(
            RestaurantChain.id == chain_id,
            RestaurantChain.owner_id == current_user.id
        ).first()
        
        if not chain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant chain with ID {chain_id} not found"
            )
        
        return chain
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.put("/{chain_id}", response_model=RestaurantChainResponse)
async def update_restaurant_chain(
    chain_id: int,
    chain_update: RestaurantChainUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    """
    Update a restaurant chain with comprehensive validation
    """
    try:
        # Find chain to update
        chain = db.query(RestaurantChain).filter(
            RestaurantChain.id == chain_id,
            RestaurantChain.owner_id == current_user.id
        ).first()
        
        if not chain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant chain with ID {chain_id} not found"
            )
        
        # Validate name uniqueness if name is being changed
        update_data = chain_update.dict(exclude_unset=True)
        if 'name' in update_data and update_data['name'] != chain.name:
            validate_name_uniqueness(db, RestaurantChain, update_data['name'], current_user.id)
        
        # Update chain fields
        for field, value in update_data.items():
            setattr(chain, field, value)
        
        # Additional validation for status changes
        if chain.status == "inactive" and len(chain.restaurants) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set chain to inactive while it has active restaurants"
            )
        
        db.commit()
        db.refresh(chain)
        return chain
    
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A restaurant chain with this name already exists"
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.delete("/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_restaurant_chain(
    chain_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    """
    Delete a restaurant chain with cascading checks
    """
    try:
        # Check for associated restaurants
        restaurants_count = db.query(RestaurantOutlet).filter(
            RestaurantOutlet.chain_id == chain_id
        ).count()
        
        if restaurants_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete chain with associated restaurants. Migrate or remove restaurants first."
            )
        
        # Find chain to delete
        chain = db.query(RestaurantChain).filter(
            RestaurantChain.id == chain_id,
            RestaurantChain.owner_id == current_user.id
        ).first()
        
        if not chain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant chain with ID {chain_id} not found"
            )
        
        db.delete(chain)
        db.commit()
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

@router.patch("/{chain_id}/status", response_model=RestaurantChainResponse)
async def update_chain_status(
    chain_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    """
    Dedicated endpoint for updating chain status
    """
    try:
        chain = db.query(RestaurantChain).filter(
            RestaurantChain.id == chain_id,
            RestaurantChain.owner_id == current_user.id
        ).first()
        
        if not chain:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Restaurant chain with ID {chain_id} not found"
            )
        
        # Additional business logic for status changes
        if status == "inactive" and len(chain.restaurants) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot set chain to inactive while it has active restaurants"
            )
        
        chain.status = status
        db.commit()
        db.refresh(chain)
        return chain
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )