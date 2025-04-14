from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from models.menu_management import MenuCategory, MenuItem, MenuScope
from models.user import User, UserRole
from models.restaurant_outlet import RestaurantOutlet
from models.restaurant_chain import RestaurantChain
from schemas.menu_management import MenuCategoryCreate, MenuCategoryUpdate, MenuCategoryResponse, MenuItemCreate, MenuItemUpdate, MenuItemResponse
from utils.auth import get_current_active_user, get_current_owner

router = APIRouter(prefix="/api/v1/menu-management", tags=["menu_management"])

# Menu Category Management Endpoints
@router.post("/categories", response_model=MenuCategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_menu_category(category: MenuCategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Check if user has appropriate role
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin, owner, and manager can create menu categories"
        )
    
        # Check if category exists
    chain_id  = db.query(RestaurantChain).filter(RestaurantChain.id == category.chain_id).first()
    outlet_id = db.query(RestaurantOutlet).filter(RestaurantOutlet.id == category.outlet_id).first()
    if not chain_id and not outlet_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu category with chain id {category.chain_id} or outlet id {category.outlet_id} not found"
        )


    
    db_category = MenuCategory(**category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

@router.get("/categories", response_model=List[MenuCategoryResponse])
async def list_menu_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Filter categories based on user role and permissions
    if current_user.role == UserRole.SUPERADMIN.value:
        categories = db.query(MenuCategory).all()
    elif current_user.role == UserRole.OWNER.value:
        # Get categories from chains owned by the user
        chain_ids = [chain.id for chain in current_user.restaurant_chains]
        categories = db.query(MenuCategory).filter(
            (MenuCategory.chain_id.in_(chain_ids)) |
            (MenuCategory.outlet_id.in_([outlet.id for chain in current_user.restaurant_chains for outlet in chain.outlets]))
        ).all()
    else:
        # For MANAGER and WAITER, only show categories from their assigned outlet
        categories = db.query(MenuCategory).filter(
            (MenuCategory.outlet_id == current_user.outlet_id) |
            (MenuCategory.chain_id == db.query(User).filter(User.id == current_user.id).first().outlet_id)
        ).all()
    return categories

@router.put("/categories/{category_id}", response_model=MenuCategoryResponse)
async def update_menu_category(
    category_id: int,
    category_update: MenuCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    db_category = db.query(MenuCategory).filter(MenuCategory.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Menu category not found")
    
    for field, value in category_update.dict(exclude_unset=True).items():
        setattr(db_category, field, value)
    
    db.commit()
    db.refresh(db_category)
    return db_category

@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_category(category_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_owner)):
    db_category = db.query(MenuCategory).filter(MenuCategory.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Menu category not found")
    
    db.delete(db_category)
    db.commit()

# Menu Item Management Endpoints
@router.post("/items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_menu_item(item: MenuItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Check if user has appropriate role
    if current_user.role not in [UserRole.SUPERADMIN, UserRole.OWNER, UserRole.MANAGER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superadmin, owner, and manager can create menu items"
        )
    
    # Check if category exists
    category = db.query(MenuCategory).filter(MenuCategory.id == item.category_id).first()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Menu category with id {item.category_id} not found"
        )
    
    db_item = MenuItem(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/items", response_model=List[MenuItemResponse])
async def list_menu_items(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    # Filter items based on user role and permissions
    if current_user.role == UserRole.SUPERADMIN.value:
        items = db.query(MenuItem).all()
    elif current_user.role == UserRole.OWNER.value:
        # Get items from categories in chains owned by the user
        chain_ids = [chain.id for chain in current_user.restaurant_chains]
        items = db.query(MenuItem).join(MenuItem.category).filter(
            (MenuCategory.chain_id.in_(chain_ids)) |
            (MenuCategory.outlet_id.in_([outlet.id for chain in current_user.restaurant_chains for outlet in chain.outlets]))
        ).all()
    else:
        # For MANAGER and WAITER, only show items from their assigned outlet
        items = db.query(MenuItem).join(MenuItem.category).filter(
            (MenuCategory.outlet_id == current_user.outlet_id) |
            (MenuCategory.chain_id == db.query(User).filter(User.id == current_user.id).first().outlet.chain_id)
        ).all()
    return items

@router.put("/items/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    item_id: int,
    item_update: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_owner)
):
    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    for field, value in item_update.dict(exclude_unset=True).items():
        setattr(db_item, field, value)
    
    db.commit()
    db.refresh(db_item)
    return db_item

@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_owner)):
    db_item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    
    db.delete(db_item)
    db.commit()