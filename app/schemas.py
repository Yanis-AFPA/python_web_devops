from typing import Optional
from sqlmodel import SQLModel
from app.models import UserRole

class UserUpdate(SQLModel):
    password: Optional[str] = None
    role: Optional[UserRole] = None

class UserCreate(SQLModel):
    username: str
    password: str
    role: UserRole = UserRole.MEMBER
