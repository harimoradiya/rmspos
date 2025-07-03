from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from utils.database import get_db
from models.table_management import Area, Table, TableStatus
from models.restaurant_outlet import RestaurantOutlet
from models.restaurant_chain import RestaurantChain
from models.user import User, UserRole
from schemas.table_management import AreaCreate, AreaUpdate, AreaResponse, TableCreate, TableUpdate, TableResponse
from utils.auth import get_current_active_user, get_current_owner
import logging
from sqlalchemy import and_


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/table-management", tags=["table_management"])

# Dependency for owner or superadmin access
def get_owner_or_superadmin(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires superadmin or owner role")
    return current_user

# Dependency for owner, superadmin, or manager access
def get_authorized_user(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER, UserRole.MANAGER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires superadmin, owner, or manager role")
    return current_user

# Helper to get authorized chain IDs
def get_authorized_chain_ids(current_user: User, db: Session) -> List[int]:
    if current_user.role == UserRole.SUPERADMIN:
        chain_ids = [chain.id for chain in db.query(RestaurantChain).all()]
    elif current_user.role == UserRole.OWNER:
        chain_ids = [chain.id for chain in current_user.restaurant_chains]
    elif current_user.role == UserRole.MANAGER:
        if not current_user.outlet:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager not assigned to any outlet")
        chain_ids = [current_user.outlet.chain_id]
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid user role")
    
    if not chain_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No restaurant chains associated with your account")
    
    logger.debug(f"User {current_user.id} role {current_user.role} authorized for chain IDs: {chain_ids}")
    return chain_ids

# Area Management Endpoints
@router.post("/areas", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(
    area: AreaCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    # Validate outlet exists and user has permission
    chain_ids = get_authorized_chain_ids(current_user, db)
    outlet = db.query(RestaurantOutlet).filter(
        and_(
            RestaurantOutlet.id == area.outlet_id,
            RestaurantOutlet.chain_id.in_(chain_ids)
        )
    ).first()
    
    if not outlet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid outlet ID or insufficient permissions"
        )
    
    # Create area
    try:
        db_area = Area(**area.dict())
        db.add(db_area)
        db.commit()
        db.refresh(db_area)
        logger.info(f"Area {db_area.id} created by user {current_user.id}")
        return db_area
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create area: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create area")

@router.get("/areas", response_model=List[AreaResponse])
async def list_areas(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    chain_ids = get_authorized_chain_ids(current_user, db)
    areas = db.query(Area).join(RestaurantOutlet).filter(current_user.outlet_id == RestaurantOutlet.id).filter(
        RestaurantOutlet.chain_id.in_(chain_ids)
    ).all()
    logger.info(f"Retrieved {len(areas)} areas for user {current_user.id}")
    return areas

@router.put("/areas/{area_id}", response_model=AreaResponse)
async def update_area(
    area_id: int,
    area_update: AreaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    # Verify area exists and user has permission
    chain_ids = get_authorized_chain_ids(current_user, db)
    db_area = db.query(Area).join(RestaurantOutlet).filter(
        and_(
            Area.id == area_id,
            RestaurantOutlet.chain_id.in_(chain_ids)
        )
    ).first()
    
    if not db_area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area not found or insufficient permissions"
        )
    
    # Update area
    try:
        for field, value in area_update.dict(exclude_unset=True).items():
            setattr(db_area, field, value)
        db.commit()
        db.refresh(db_area)
        logger.info(f"Area {area_id} updated by user {current_user.id}")
        return db_area
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update area {area_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update area")

@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(
    area_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    # Verify area exists and user has permission
    chain_ids = get_authorized_chain_ids(current_user, db)
    db_area = db.query(Area).join(RestaurantOutlet).filter(
        and_(
            Area.id == area_id,
            RestaurantOutlet.chain_id.in_(chain_ids)
        )
    ).first()
    
    if not db_area:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area not found or insufficient permissions"
        )
    
    try:
        db.delete(db_area)
        db.commit()
        logger.info(f"Area {area_id} deleted by user {current_user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete area {area_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete area")

# Table Management Endpoints
@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    table: TableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    # Validate area exists and user has permission
    chain_ids = get_authorized_chain_ids(current_user, db)
    area = db.query(Area).join(RestaurantOutlet).filter(
        and_(
            Area.id == table.area_id,
            RestaurantOutlet.chain_id.in_(chain_ids)
        )
    ).first()
    
    if not area:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid area ID or insufficient permissions"
        )
    
    # Create table
    try:
        db_table = Table(**table.dict())
        db.add(db_table)
        db.commit()
        db.refresh(db_table)
        logger.info(f"Table {db_table.id} created by user {current_user.id}")
        return db_table
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create table: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create table")

@router.get("/tables", response_model=List[TableResponse])
async def list_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == UserRole.SUPERADMIN:
        tables = db.query(Table).all()
    else:
        chain_ids = get_authorized_chain_ids(current_user, db)
        tables = db.query(Table).join(Area).join(RestaurantOutlet).filter(
            current_user.outlet_id == RestaurantOutlet.id,
            RestaurantOutlet.chain_id.in_(chain_ids)    
        ).all()
    
    logger.info(f"Retrieved {len(tables)} tables for user {current_user.id}")
    return tables

@router.put("/tables/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    table_update: TableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    # Verify table exists and user has permission
    chain_ids = get_authorized_chain_ids(current_user, db)
    db_table = db.query(Table).join(Area).join(RestaurantOutlet).filter(
        and_(
            Table.id == table_id,
            RestaurantOutlet.chain_id.in_(chain_ids)
        )
    ).first()
    
    if not db_table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found or insufficient permissions"
        )
    
    # Update table
    try:
        for field, value in table_update.dict(exclude_unset=True).items():
            setattr(db_table, field, value)
        db.commit()
        db.refresh(db_table)
        logger.info(f"Table {table_id} updated by user {current_user.id}")
        return db_table
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update table {table_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update table")

@router.delete("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authorized_user)
):
    # Verify table exists and user has permission
    chain_ids = get_authorized_chain_ids(current_user, db)
    db_table = db.query(Table).join(Area).join(RestaurantOutlet).filter(
        and_(
            Table.id == table_id,
            RestaurantOutlet.chain_id.in_(chain_ids)
        )
    ).first()
    
    if not db_table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found or insufficient permissions"
        )
    
    try:
        db.delete(db_table)
        db.commit()
        logger.info(f"Table {table_id} deleted by user {current_user.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete table {table_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete table")