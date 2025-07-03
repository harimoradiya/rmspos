from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from utils.database import get_db
from models.subscription import Subscription, SubscriptionTier, SubscriptionStatus
from models.user import User, UserRole
from models.restaurant_outlet import RestaurantOutlet
from schemas.subscription import SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse
from utils.auth import get_current_super_admin, get_current_owner, verify_subscription,get_current_active_user
from sqlalchemy.exc import SQLAlchemyError
router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])

@router.post("", response_model=SubscriptionResponse, status_code=status.HTTP_201_CREATED)
async def create_subscription(
    subscription: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
): 
     # Only superadmin can create subscriptions

    try:
        # Validate outlet existence
        outlet = db.query(RestaurantOutlet).filter(
            RestaurantOutlet.id == subscription.outlet_id
        ).first()
        
        if not outlet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Outlet with ID {subscription.outlet_id} not found"
            )
        
        # Check for existing active subscription
        existing_subscription = db.query(Subscription).filter(
            Subscription.outlet_id == subscription.outlet_id,
            Subscription.status == SubscriptionStatus.ACTIVE
        ).first()
        
        if existing_subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An active subscription already exists for this outlet"
            )
        
        # Calculate subscription duration
        start_date = datetime.now()
        duration_months = subscription.duration_months or 12
        end_date = start_date + timedelta(days=duration_months * 30)  # Approximate months
        
        # Create new subscription
        db_subscription = Subscription(
            outlet_id=subscription.outlet_id,
            tier=subscription.tier,
            status=SubscriptionStatus.ACTIVE,
            start_date=start_date,
            end_date=end_date
        )
        
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        return db_subscription
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/list_subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    outlet_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    try:

        outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == Subscription.outlet_id, RestaurantOutlet.chain_id.in_([chain.id for chain in current_user.restaurant_chains])).first()
        print(outlet)
        if not outlet:
            raise HTTPException(status_code=400, detail="No outlet ID found or you don't have permission to add an area to this outlet.")


        query = db.query(Subscription)
        
        if current_user.role == UserRole.SUPERADMIN.value:


            if outlet_id:
                query = query.filter(Subscription.outlet_id == outlet_id)
            else:
                return query.all()  
        elif current_user.role == UserRole.OWNER.value:
            # Get all outlets under the owner's chains
            chain_ids = [chain.id for chain in current_user.restaurant_chains]
            query = query.join(RestaurantOutlet).filter(
                RestaurantOutlet.chain_id.in_(chain_ids)
            )
            if outlet_id:
                query = query.filter(Subscription.outlet_id == outlet_id)
        else:
            # Staff can only view their outlet's subscription

            if not current_user.outlet_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Staff must be assigned to an outlet"
                )
            if current_user.role == UserRole.MANAGER.value:
                query = query.filter(Subscription.outlet_id == current_user.outlet_id)
        
        return query.all()
    except SQLAlchemyError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    subscription_update: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)
):
    try:
        db_subscription = db.query(Subscription).filter(
            Subscription.id == subscription_id
        ).first()
        
        if not db_subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )
        
        # Update fields
        for field, value in subscription_update.dict(exclude_unset=True).items():
            setattr(db_subscription, field, value)
        
        db.commit()
        db.refresh(db_subscription)
        return db_subscription
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
        
        db_subscription = Subscription(
            user_id=user_id,
            tier=tier,
            status=SubscriptionStatus.ACTIVE.value,  # Default to active
            start_date=start_date,
            end_date=end_date
        )
        
        db.add(db_subscription)
        db.commit()
        db.refresh(db_subscription)
        
        return db_subscription
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error occurred: {str(e)}"
        )

@router.get("", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_owner),
    status: Optional[SubscriptionStatus] = None,
    tier: Optional[SubscriptionTier] = None
):
    """
    List subscriptions with optional filtering by status and tier
    """
    outlet = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == Subscription.outlet_id).first()
    print(outlet)
    if not outlet:
        raise HTTPException(status_code=400, detail="No outlet ID Found")


    query = db.query(Subscription)
    
    if status:
        query = query.filter(Subscription.status == status)
    
    if tier:
        query = query.filter(Subscription.tier == tier)
    
    subscriptions = query.all()
    return subscriptions

@router.get("/me", response_model=SubscriptionResponse)
async def get_my_subscription(
    current_user: User = Depends(get_current_active_user), 
    db: Session = Depends(get_db)
):
    subscription = db.query(Subscription).filter(
        Subscription.id == current_user.id,
        Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.EXPIRED.value])
    ).first()
    
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )
    return subscription

@router.put("/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    subscription_update: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin)  # Changed to superadmin only
):
    try:
        # Find subscription to update
        db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not db_subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription with ID {subscription_id} not found"
            )
        
        # Update subscription fields
        update_data = subscription_update.dict(exclude_unset=True)
        
        # Additional validation for specific fields
        if 'status' in update_data:
            # Optional: Add extra logic for status transitions
            pass
        
        if 'tier' in update_data:
            # Optional: Add logic for tier upgrades/downgrades
            pass
        
        for field, value in update_data.items():
            setattr(db_subscription, field, value)
        
        db.commit()
        db.refresh(db_subscription)
        return db_subscription
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error occurred: {str(e)}"
        )

@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subscription(
    subscription_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    try:
        # Find subscription to delete
        db_subscription = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        if not db_subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subscription with ID {subscription_id} not found"
            )
        
        db.delete(db_subscription)
        db.commit()
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error occurred: {str(e)}"
        )
    
# Subscription Renewal Endpoint
@router.post("/renew", response_model=SubscriptionResponse)
async def renew_subscription(
    subscription_id: int,
    outlet_id: int,
    renewal_period: int = 365,  # Default 1 year
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    try:
        # Validate outlet existence and user's permission
        outlet = db.query(RestaurantOutlet).filter(
            RestaurantOutlet.id == outlet_id,
            RestaurantOutlet.chain_id.in_([chain.id for chain in current_user.restaurant_chains])
        ).first()
        
        if not outlet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Outlet not found or you don't have permission to access it"
            )

        # Find the existing subscription
        subscription = db.query(Subscription).filter(
            Subscription.id == subscription_id,
            Subscription.outlet_id == outlet_id
        ).first()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found"
            )
        
        # Determine new end date
        current_time = datetime.now()
        new_end_date = max(
            current_time + timedelta(days=renewal_period),
            subscription.end_date + timedelta(days=renewal_period)
        )
        
        # Update subscription
        subscription.end_date = new_end_date
        subscription.status = SubscriptionStatus.ACTIVE.value
        
        db.commit()
        db.refresh(subscription)
        
        return subscription
    
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Renewal failed: {str(e)}"
        )