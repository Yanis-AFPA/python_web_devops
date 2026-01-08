from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlmodel import select, col, func
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Page, PageCategory, PageStatus, User, UserRole, PageRead, PageCreate
from app.auth import get_current_user, require_role, get_current_active_user

import shutil
import os
import uuid

router = APIRouter()

# --- Pages / Calendar Events ---

@router.get("/pages", response_model=List[PageRead])
async def get_pages(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    print(f"DEBUG: get_pages called with start={start}, end={end}, user={current_user.username}")
    # Eager load relationships to prevent MissingGreenlet on Pydantic serialization
    query = select(Page).options(selectinload(Page.author), selectinload(Page.assignee))
    
    # Filter by Date
    if start:
        start = start.replace(tzinfo=None)
        query = query.where(Page.start_time >= start)
    if end:
        end = end.replace(tzinfo=None)
        query = query.where(Page.start_time <= end)
    
    # --- VISIBILITY SCOPE ---
    if current_user.role == UserRole.ADMIN:
        pass # See all
    elif current_user.role == UserRole.MANAGER:
        # See own tasks + tasks assigned to team members
        if current_user.team_id:
            # Subquery to get user IDs in the same team
            sub = select(User.id).where(User.team_id == current_user.team_id)
            query = query.where(
                (Page.assignee_id.in_(sub)) | 
                (Page.assignee_id == None) | 
                (Page.author_id == current_user.id)
            )
        else:
            query = query.where(Page.assignee_id == current_user.id)
    else: # MEMBER
        # See only assigned to self
        query = query.where(Page.assignee_id == current_user.id)
    
    result = await session.exec(query)
    return result.all()

@router.post("/pages", response_model=PageRead)
async def create_page(
    page_data: PageCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    # Member restriction: Can only assign to self
    if current_user.role == UserRole.MEMBER and page_data.assignee_id and page_data.assignee_id != current_user.id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez vous assigner que vos propres tâches")

    # Convert PageCreate to Page
    db_page = Page.from_orm(page_data)
    db_page.author_id = current_user.id
    db_page.created_at = datetime.utcnow()
    db_page.updated_at = datetime.utcnow()
    
    session.add(db_page)
    await session.commit()
    await session.refresh(db_page)
    return db_page

@router.put("/pages/{page_id}", response_model=PageRead)
async def update_page(
    page_id: int,
    page_update: PageCreate, 
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    page = await session.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page introuvable")
    
    # --- PERMISSIONS ---
    if current_user.role == UserRole.MEMBER:
        # MEMBER: CAN ONLY CHANGE STATUS
        # We ignore other fields or enforce it? Let's strictly just update status.
        page.status = page_update.status
        page.updated_at = datetime.utcnow()
        session.add(page)
        await session.commit()
        await session.refresh(page)
        return page

    # MANAGER / ADMIN: Update all
    page_data = page_update.dict(exclude_unset=True)
    for key, value in page_data.items():
        setattr(page, key, value)

    page.updated_at = datetime.utcnow()
    
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return page

@router.delete("/pages/{page_id}")
async def delete_page(
    page_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    page = await session.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page introuvable")
    
    # Only Admin or Manager (of the team) can delete?
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
         raise HTTPException(status_code=403, detail="Permission refusée")

    await session.delete(page)
    await session.commit()
    return {"ok": True}

# --- Uploads ---

@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    # Ensure directory exists
    upload_dir = "app/static/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generate unique filename
    file_ext = file.filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{file_ext}"
    file_path = f"{upload_dir}/{filename}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    url = f"/static/uploads/{filename}"
    return {"url": url}

# --- Metrics ---

@router.get("/metrics")
async def get_metrics(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    from sqlalchemy import func
    
    # Pages created this week
    now = datetime.utcnow()
    start_of_week = now - timedelta(days=now.weekday())
    
    query_week = select(func.count(Page.id)).where(Page.created_at >= start_of_week)
    count_week_res = await session.exec(query_week)
    count_week = count_week_res.one()
    
    # Distribution by category
    query_cat = select(Page.category, func.count(Page.id)).group_by(Page.category)
    res_cat = await session.exec(query_cat)
    categories = res_cat.all() # [(category, count), ...]
    
    return {
        "new_pages_week": count_week,
        "categories": {cat.value: count for cat, count in categories}
    }
