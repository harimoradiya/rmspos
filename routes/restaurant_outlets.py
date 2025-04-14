from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.restaurant_outlet import RestaurantOutlet
from models.restaurant_chain import RestaurantChain
from models.user import User,UserRole
from schemas.restaurant_outlet import RestaurantOutletCreate, RestaurantOutletResponse, RestaurantOutletUpdate
from utils.auth import get_current_super_admin,get_current_active_user

router = APIRouter(prefix="/api/v1/restaurant-outlets", tags=["restaurant-outlets"])

@router.post("", response_model=RestaurantOutletResponse, status_code=status.HTTP_201_CREATED)
async def create_restaurant_outlet(
    outlet: RestaurantOutletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    # Verify chain exists
    chain = db.query(RestaurantChain).filter(
        RestaurantChain.id == outlet.chain_id
    ).first()
    
    if not chain:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant chain not found or you don't have access to it"
        )
    
    # Create new restaurant outlet
    db_outlet = RestaurantOutlet(
        chain_id=outlet.chain_id,
        name=outlet.name,
        address=outlet.address,
        city=outlet.city,
        state=outlet.state,
        postal_code=outlet.postal_code,
        country=outlet.country,
        latitude=outlet.latitude,
        longitude=outlet.longitude,
        phone=outlet.phone,
        email=outlet.email,
        status=outlet.status
    )
    db.add(db_outlet)
    db.commit()
    db.refresh(db_outlet)
    return db_outlet

@router.get("", response_model=List[RestaurantOutletResponse])
async def list_restaurant_outlets(
    chain_id: int = None,
    city: str = None,
    state: str = None,
    country: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Start with base query for all outlets
    query = db.query(RestaurantOutlet)
    
    # Filter based on user role and outlet
    if current_user.role == UserRole.SUPERADMIN:
        pass  # Superadmin can see all outlets
    elif current_user.role == UserRole.OWNER:
        # Owner can see all outlets in their chains
        query = query.join(RestaurantChain).filter(
            RestaurantChain.owner_id == current_user.id
        )
    else:  # Staff roles (MANAGER, WAITER, KITCHEN)
        if not current_user.outlet_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff must be assigned to an outlet"
            )
        # Staff can only see their assigned outlet
        query = query.filter(RestaurantOutlet.id == current_user.outlet_id)
    
    # Apply filters if provided
    if chain_id:
        query = query.filter(RestaurantOutlet.chain_id == chain_id)
    if city:
        query = query.filter(RestaurantOutlet.city == city)
    if state:
        query = query.filter(RestaurantOutlet.state == state)
    if country:
        query = query.filter(RestaurantOutlet.country == country)
    
    return query.all()

@router.get("/{outlet_id}", response_model=RestaurantOutletResponse)
async def get_restaurant_outlet(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    # Get specific outlet
    outlet = db.query(RestaurantOutlet).filter(
        RestaurantOutlet.id == outlet_id
    ).first()
    
    if not outlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant outlet not found or you don't have access to it"
        )
    return outlet

@router.put("/{outlet_id}", response_model=RestaurantOutletResponse)
async def update_restaurant_outlet(
    outlet_id: int,
    outlet_update: RestaurantOutletUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    # Find outlet to update
    outlet = db.query(RestaurantOutlet).filter(
        RestaurantOutlet.id == outlet_id
    ).first()
    
    if not outlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant outlet not found or you don't have access to it"
        )
    
    # Update outlet fields
    for field, value in outlet_update.dict(exclude_unset=True).items():
        setattr(outlet, field, value)
    
    db.commit()
    db.refresh(outlet)
    return outlet

@router.delete("/{outlet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_restaurant_outlet(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    # Find outlet to delete
    outlet = db.query(RestaurantOutlet).filter(
        RestaurantOutlet.id == outlet_id
    ).first()
    
    if not outlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant outlet not found or you don't have access to it"
        )
    
    db.delete(outlet)
    db.commit()