from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True, future=True)

from app.models import User, UserRole, Team
from datetime import datetime
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_hash(password):
    return pwd_context.hash(password)

async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    
    # Seeding
    async with AsyncSession(engine) as session:
        # Check if teams exist
        from sqlmodel import select
        result = await session.exec(select(Team))
        if not result.first():
            print("--- SEEDING TEAMS & USERS ---")
            
            # Teams
            team_dev = Team(name="Engineering")
            team_ops = Team(name="Operations")
            session.add(team_dev)
            session.add(team_ops)
            await session.commit()
            await session.refresh(team_dev)
            await session.refresh(team_ops)

            # Users
            users = [
                User(username="admin", password_hash=get_hash("admin"), role=UserRole.ADMIN, team_id=None),
                User(username="manager", password_hash=get_hash("manager"), role=UserRole.MANAGER, team_id=team_dev.id),
                User(username="alice", password_hash=get_hash("alice"), role=UserRole.MEMBER, team_id=team_dev.id),
                User(username="bob", password_hash=get_hash("bob"), role=UserRole.MEMBER, team_id=team_dev.id),
                User(username="ops_lead", password_hash=get_hash("manager"), role=UserRole.MANAGER, team_id=team_ops.id),
            ]
            
            session.add_all(users)
            await session.commit()
            
            # Refresh users to get IDs
            for u in users:
                await session.refresh(u)
                
            # Create Realistic Tasks
            from app.models import Page, PagePriority, PageStatus, PageCategory
            from datetime import timedelta
            
            now = datetime.utcnow()
            
            tasks = [
                # Engineering Tasks (Team Dev)
                Page(title="Refactor Authentication Module", content="Switch to JWT strict mode and improving logout", 
                     start_time=now, end_time=now + timedelta(hours=4), 
                     status=PageStatus.IN_PROGRESS, priority=PagePriority.HIGH, category=PageCategory.FEATURE,
                     author_id=users[1].id, assignee_id=users[2].id), # Manager -> Alice
                     
                Page(title="Fix CI/CD Pipeline", content="Pipeline failing on Docker build step", 
                     start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=2), 
                     status=PageStatus.TODO, priority=PagePriority.CRITICAL, category=PageCategory.DEVOPS,
                     author_id=users[1].id, assignee_id=users[3].id), # Manager -> Bob

                Page(title="Weekly Code Review", content="Reviewing PRs for the new release", 
                     start_time=now + timedelta(days=2), end_time=now + timedelta(days=2, hours=1), 
                     status=PageStatus.TODO, priority=PagePriority.MEDIUM, category=PageCategory.MEETING,
                     author_id=users[1].id, assignee_id=users[1].id), # Manager Self

                # Operations Tasks (Team Ops)
                Page(title="Server Maintenance", content="Upgrade kernel on prod servers", 
                     start_time=now, end_time=now + timedelta(hours=3), 
                     status=PageStatus.DONE, priority=PagePriority.HIGH, category=PageCategory.DEVOPS,
                     author_id=users[4].id, assignee_id=users[4].id), # Ops Lead Self
            ]
            
            session.add_all(tasks)
            await session.commit()
            print("--- SEEDING COMPLETED ---")

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
