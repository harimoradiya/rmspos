from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.table_management import Area, Table, TableStatus
from models.user import User, UserRole
from schemas.table_management import AreaCreate, AreaUpdate, AreaResponse, TableCreate, TableUpdate, TableResponse
from utils.auth import get_current_active_user, get_current_owner

router = APIRouter(prefix="/api/v1/table-management", tags=["table_management"])

# Area Management Endpoints
@router.post("/areas", response_model=AreaResponse, status_code=status.HTTP_201_CREATED)
async def create_area(area: AreaCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_owner)):
    db_area = Area(**area.dict())
    db.add(db_area)
    db.commit()
    db.refresh(db_area)
    return db_area

@router.get("/areas", response_model=List[AreaResponse])
async def list_areas(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Filter areas based on user role and permissions
    if current_user.role == UserRole.SUPERADMIN.value:
        areas = db.query(Area).all()
    elif current_user.role == UserRole.OWNER.value:
        # Get areas from outlets owned by the user
        chain_ids = [chain.id for chain in current_user.restaurant_chains]
        areas = db.query(Area).join(Area.outlet).filter(
            Area.outlet.has(chain_id=chain_ids)
        ).all()
    else:
        # For MANAGER and WAITER, only show areas from their assigned outlet
        areas = db.query(Area).filter(Area.outlet_id == current_user.outlet_id).all()
    return areas

@router.put("/areas/{area_id}", response_model=AreaResponse)
async def update_area(
    area_id: int,
    area_update: AreaUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    db_area = db.query(Area).filter(Area.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    for field, value in area_update.dict(exclude_unset=True).items():
        setattr(db_area, field, value)
    
    db.commit()
    db.refresh(db_area)
    return db_area

@router.delete("/areas/{area_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_area(area_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_owner)):
    db_area = db.query(Area).filter(Area.id == area_id).first()
    if not db_area:
        raise HTTPException(status_code=404, detail="Area not found")
    
    db.delete(db_area)
    db.commit()

# Table Management Endpoints
@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(table: TableCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_owner)):
    db_table = Table(**table.dict())
    db.add(db_table)
    db.commit()
    db.refresh(db_table)
    return db_table

@router.get("/tables", response_model=List[TableResponse])
async def list_tables(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Filter tables based on user role and permissions
    if current_user.role == UserRole.SUPERADMIN.value:
        tables = db.query(Table).all()
    elif current_user.role == UserRole.OWNER.value:
        # Get tables from areas in outlets owned by the user
        chain_ids = [chain.id for chain in current_user.restaurant_chains]
        tables = db.query(Table).join(Table.area).join(Area.outlet).filter(
            Area.outlet.has(chain_id=chain_ids)
        ).all()
    else:
        # For MANAGER and WAITER, only show tables from their assigned outlet
        tables = db.query(Table).join(Table.area).filter(
            Area.outlet_id == current_user.outlet_id
        ).all()
    return tables

@router.put("/tables/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    table_update: TableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    db_table = db.query(Table).filter(Table.id == table_id).first()
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    for field, value in table_update.dict(exclude_unset=True).items():
        setattr(db_table, field, value)
    
    db.commit()
    db.refresh(db_table)
    return db_table

@router.delete("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(table_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_owner)):
    db_table = db.query(Table).filter(Table.id == table_id).first()
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    db.delete(db_table)
    db.commit()