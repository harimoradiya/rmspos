from pydantic import BaseModel, EmailStr, validator, root_validator
from typing import Optional
from datetime import datetime
from models.user import UserRole

class LoginRequest(BaseModel):
    username: str
    password: Optional[str] = None
    pin: Optional[str] = None

    @validator('pin')
    def validate_pin(cls, v):
        if v is not None:
            if not v.isdigit() or len(v) != 6:
                raise ValueError('PIN must be a 6-digit number')
        return v

    @root_validator(skip_on_failure=True)
    def validate_login_method(cls, values):
        username = values.get('username')
        password = values.get('password')
        pin = values.get('pin')
        
        if pin:
            # For PIN login, password should be None and username must be provided
            if password is not None:
                raise ValueError('Password should not be provided for PIN login')
            if not username:
                raise ValueError('Username must be provided for PIN login')
        else:
            # For username/password login, both must be provided
            if not (username and password):
                raise ValueError('Provide both username and password for login')
        return values

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    role: UserRole

class UserUpdate(BaseModel):
    username : Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserInDB(UserBase):
    id: int
    role: UserRole
    username: str
    is_active: bool
    outlet_id: Optional[int] = None
    pin: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class UserResponse(UserInDB):
    pass

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[UserRole] = None