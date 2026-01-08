from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models import Team, TeamCreate, TeamRead, User, UserRole
from app.auth import get_current_active_user, require_role

router = APIRouter()

@router.get("/teams", response_model=List[TeamRead])
async def read_teams(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    result = await session.exec(select(Team))
    return result.all()

@router.post("/teams", response_model=TeamRead)
async def create_team(
    team_data: TeamCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    team = Team.from_orm(team_data)
    session.add(team)
    await session.commit()
    await session.refresh(team)
    return team

@router.delete("/teams/{team_id}")
async def delete_team(
    team_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_role([UserRole.ADMIN]))
):
    team = await session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    
    # Optional: Check if team has members?
    # For now, just delete. Users will have team_id set to null or cascade?
    # SQLModel doesn't auto-cascade python side unless configured. 
    # Let's just delete the team.
    
    await session.delete(team)
    await session.commit()
    return {"ok": True}
