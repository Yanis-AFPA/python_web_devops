from fastapi import APIRouter, Depends, Request, Form, status, Response, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select, desc
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.auth import get_current_user, verify_password, create_access_token, get_password_hash
from app.models import User, Page, UserRole, PageStatus, PagePriority
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import timedelta

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
async def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session)
):
    query = select(User).where(User.username == username)
    result = await session.exec(query)
    user = result.first()
    
    if not user or not verify_password(password, user.password_hash):
        # Return to login with error (simplified)
        # Using a simple alert JS or just redirect back for MVP
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides")

    access_token = create_access_token(data={"sub": user.username})
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=access_token, httponly=True)
    return response

@router.get("/logout")
async def logout(response: Response):
    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("access_token")
    return resp

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    if not user:
        return RedirectResponse("/login")
        
    # Dashboard Tasks Logic
    # 1. Base Query with Eager Loading
    query = select(Page).options(selectinload(Page.author), selectinload(Page.assignee))
    
    # 2. Role Filtering
    if user.role == UserRole.MEMBER:
        query = query.where(Page.assignee_id == user.id)
    elif user.role == UserRole.MANAGER and user.team_id:
        query = query.join(Page.assignee).where(User.team_id == user.team_id)
    # Admin sees all (no filter)

    # 3. Status Filtering (Active only for tactical view)
    # displaying TODO and IN_PROGRESS. We might exclude DONE to keep the list clean, 
    # or keep them if updated recently. Let's keep Active for now as per "Tactical" goal.
    query = query.where(Page.status.in_([PageStatus.TODO, PageStatus.IN_PROGRESS]))

    result = await session.exec(query)
    tasks = result.all()

    # 4. Python Sorting
    # Priority Order: Critical(0) -> High(1) -> Medium(2) -> Low(3)
    priority_map = {
        PagePriority.CRITICAL: 0,
        PagePriority.HIGH: 1,
        PagePriority.MEDIUM: 2,
        PagePriority.LOW: 3
    }
    
    # Sort: Priority ASC, then EndTime ASC (Earliest deadline first)
    # Handle None for end_time by using max datetime (push to bottom) or min? Usually deadlines are critical.
    # If no deadline, maybe less urgent? Let's use max.
    from datetime import datetime
    
    sorted_tasks = sorted(tasks, key=lambda p: (
        priority_map.get(p.priority, 4),
        p.end_time or datetime.max
    ))
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "dashboard_tasks": sorted_tasks  # Renamed from recent_pages
    })

@router.get("/calendar", response_class=HTMLResponse)
async def calendar(
    request: Request,
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "user": user
    })

@router.get("/settings", response_class=HTMLResponse)
async def settings(
    request: Request,
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": user
    })

@router.get("/storage", response_class=HTMLResponse)
async def storage(
    request: Request,
    user: User = Depends(get_current_user)
):
    if not user:
        return RedirectResponse("/login")
    return templates.TemplateResponse("storage.html", {
        "request": request,
        "user": user
    })

@router.get("/admin", response_class=HTMLResponse)
async def admin_panel(
    request: Request,
    user: User = Depends(get_current_user)
):
    if not user or user.role != UserRole.ADMIN:
        return RedirectResponse("/dashboard")
    return templates.TemplateResponse("admin_teams.html", {
        "request": request,
        "user": user
    })
