from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session, get_hash
from app.models import User, UserRole, UserRead
from app.auth import get_current_active_user, require_role
from app.schemas import UserUpdate, UserCreate

router = APIRouter()

@router.get("/users", response_model=List[UserRead])
async def read_users(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    result = await session.exec(select(User))
    return result.all()

@router.post("/users", response_model=User)
async def create_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    # Check if user exists
    existing = await session.exec(select(User).where(User.username == user_data.username))
    if existing.first():
        raise HTTPException(status_code=400, detail="Username already taken")

    new_user = User(
        username=user_data.username,
        password_hash=get_hash(user_data.password),
        role=user_data.role
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user

@router.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Permissions
    is_admin = current_user.role == UserRole.ADMIN
    is_self = current_user.id == user_id

    if not (is_admin or is_self):
        raise HTTPException(status_code=403, detail="Not authorized")

    # Access Control Logic
    if user_update.role:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only admins can change roles")
        user.role = user_update.role

    if user_update.password:
        # Everyone can change their own password, admin can change anyone's
        user.password_hash = get_hash(user_update.password)

    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    await session.delete(user)
    await session.commit()
    return {"ok": True}
