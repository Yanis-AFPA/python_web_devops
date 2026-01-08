from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlmodel import select, col, func, or_
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Page, PageCategory, PageStatus, User, UserRole, PageRead, PageCreate, StorageFile
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
    query = select(Page).options(selectinload(Page.author), selectinload(Page.assignee), selectinload(Page.files))
    
    # Filter by Date
    if start:
        start = start.replace(tzinfo=None)
        query = query.where(Page.start_time >= start)
    if end:
        end = end.replace(tzinfo=None)
        query = query.where(Page.start_time <= end)
    
    # --- VISIBILITY SCOPE ---
    # Global tasks always visible
    # Team tasks visible to team members
    
    if current_user.role == UserRole.ADMIN:
        pass # See all
    elif current_user.role == UserRole.MANAGER:
        # See:
        # 1. Global tasks
        # 2. Own tasks (Author or Assignee)
        # 3. Tasks assigned to MY TEAM (assigned_team_id == current_user.team_id)
        # 4. Tasks assigned to users IN MY TEAM
        
        conditions = [
            Page.is_global == True,
            Page.author_id == current_user.id,
            Page.assignee_id == current_user.id
        ]
        
        if current_user.team_id:
            conditions.append(Page.assigned_team_id == current_user.team_id)
            # Users in my team
            sub = select(User.id).where(User.team_id == current_user.team_id)
            conditions.append(Page.assignee_id.in_(sub))
            
        query = query.where(or_(*conditions))

    else: # MEMBER
        # See:
        # 1. Global tasks
        # 2. Own tasks (Assignee or Author)
        # 3. Tasks assigned to MY TEAM
        
        conditions = [
            Page.is_global == True,
            Page.assignee_id == current_user.id,
            Page.author_id == current_user.id
        ]
        
        if current_user.team_id:
            conditions.append(Page.assigned_team_id == current_user.team_id)
            
        query = query.where(or_(*conditions))
    
    result = await session.exec(query)
    return result.all()

@router.get("/pages/{page_id}", response_model=PageRead)
async def get_page(
    page_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    # Eager load files and their uploaders
    query = select(Page).where(Page.id == page_id).options(
        selectinload(Page.files).selectinload(StorageFile.uploaded_by)
    )
    result = await session.exec(query)
    page = result.first()
    
    if not page:
        raise HTTPException(status_code=404, detail="Page introuvable")
    return page

@router.post("/pages", response_model=PageRead)
async def create_page(
    page_data: PageCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    # Validations
    if page_data.is_global and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Seuls les administrateurs peuvent créer des tâches globales")
        
    if page_data.assigned_team_id:
        if current_user.role == UserRole.MEMBER and current_user.team_id != page_data.assigned_team_id:
            raise HTTPException(status_code=403, detail="Vous ne pouvez assigner une tâche qu'à votre propre équipe")
            
    # Member restriction: Can only assign to self IF not assigning to team/global
    if current_user.role == UserRole.MEMBER and not page_data.assigned_team_id and not page_data.is_global:
        if page_data.assignee_id and page_data.assignee_id != current_user.id:
            raise HTTPException(status_code=403, detail="Vous ne pouvez vous assigner que vos propres tâches")

    # Convert PageCreate to Page
    db_page = Page.from_orm(page_data)
    db_page.author_id = current_user.id
    db_page.created_at = datetime.utcnow()
    db_page.updated_at = datetime.utcnow()
    
    session.add(db_page)
    await session.commit()
    
    # Eager load relationships for response
    query = select(Page).where(Page.id == db_page.id).options(
        selectinload(Page.files).selectinload(StorageFile.uploaded_by),
        selectinload(Page.author),
        selectinload(Page.assignee)
    )
    result = await session.exec(query)
    return result.first()

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
        
        # Eager load relationships for response
        query = select(Page).where(Page.id == page.id).options(
            selectinload(Page.files).selectinload(StorageFile.uploaded_by),
            selectinload(Page.author),
            selectinload(Page.assignee)
        )
        result = await session.exec(query)
        return result.first()

    # MANAGER / ADMIN: Update all
    page_data = page_update.dict(exclude_unset=True)
    for key, value in page_data.items():
        setattr(page, key, value)

    page.updated_at = datetime.utcnow()
    
    session.add(page)
    await session.commit()
    
    # Eager load relationships for response
    query = select(Page).where(Page.id == page.id).options(
        selectinload(Page.files).selectinload(StorageFile.uploaded_by),
        selectinload(Page.author),
        selectinload(Page.assignee)
    )
    result = await session.exec(query)
    return result.first()

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
    
    response_data = {
        "role": current_user.role.value,
        "username": current_user.username,
        "context": {}
    }

    if current_user.role == UserRole.MEMBER:
        # MEMBER: Personal Stats (My Tasks by Status)
        query = select(Page.status, func.count(Page.id))\
            .where(Page.assignee_id == current_user.id)\
            .group_by(Page.status)
        result = await session.exec(query)
        stats = {s.value: c for s, c in result.all()}
        
        response_data["context"] = {
            "my_stats": {
                "todo": stats.get("todo", 0),
                "in_progress": stats.get("in_progress", 0),
                "done": stats.get("done", 0)
            }
        }

    elif current_user.role == UserRole.MANAGER:
        # MANAGER: Personal Stats + Team Stats
        
        # 1. Personal Stats (Same as Member)
        q_personal = select(Page.status, func.count(Page.id))\
            .where(Page.assignee_id == current_user.id)\
            .group_by(Page.status)
        r_personal = await session.exec(q_personal)
        stats_personal = {s.value: c for s, c in r_personal.all()}
        
        my_stats = {
            "todo": stats_personal.get("todo", 0),
            "in_progress": stats_personal.get("in_progress", 0),
            "done": stats_personal.get("done", 0)
        }

        # 2. Team Stats
        context_data = {"my_stats": my_stats}
        
        if current_user.team_id:
            sub_team = select(User.id).where(User.team_id == current_user.team_id)
            
            # Status Distribution
            q_status = select(Page.status, func.count(Page.id))\
                .where(Page.assignee_id.in_(sub_team))\
                .group_by(Page.status)
            r_status = await session.exec(q_status)
            stats_status = {s.value: c for s, c in r_status.all()}
            
            # Workload
            q_workload = select(User.username, func.count(Page.id))\
                .join(Page, User.id == Page.assignee_id)\
                .where(User.team_id == current_user.team_id)\
                .where(Page.status.in_([PageStatus.TODO, PageStatus.IN_PROGRESS]))\
                .group_by(User.username)
            r_workload = await session.exec(q_workload)
            workload = {u: c for u, c in r_workload.all()}
            
            context_data["team_stats"] = {
                "todo": stats_status.get("todo", 0),
                "in_progress": stats_status.get("in_progress", 0),
                "done": stats_status.get("done", 0)
            }
            context_data["workload"] = workload
        else:
             context_data["error"] = "No Team Assigned"
        
        response_data["context"] = context_data

    else:
        # ADMIN: System Overview (The old view)
        now = datetime.utcnow()
        start_of_week = now - timedelta(days=now.weekday())
        
        query_week = select(func.count(Page.id)).where(Page.created_at >= start_of_week)
        count_week_res = await session.exec(query_week)
        count_week = count_week_res.one()
        
        query_cat = select(Page.category, func.count(Page.id)).group_by(Page.category)
        res_cat = await session.exec(query_cat)
        categories = res_cat.all()
        
        response_data["context"] = {
            "system_stats": {
                "new_pages_week": count_week,
                "categories": {cat.value: count for cat, count in categories}
            }
        }
    
    return response_data
