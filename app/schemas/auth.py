from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional
from app.models.user import UserRole
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    role: UserRole
    department: Optional[str] = None
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    employee_id: Optional[int] = None
    created_at: datetime

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: Optional[dict] = None

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    department: Optional[str] = None
    full_name: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str
