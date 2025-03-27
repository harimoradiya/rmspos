from fastapi import HTTPException, status
from sqlalchemy.orm import Session
def validate_name_uniqueness(db: Session, model, name: str, owner_id: int):
    """Validate that the name is unique for the given owner"""
    existing = db.query(model).filter(
        model.name == name, 
        model.owner_id == owner_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{model.__name__} with this name already exists"
        )