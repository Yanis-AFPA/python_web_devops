from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True, future=True)

from app.models import User, UserRole
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
        # Check if admin exists
        from sqlmodel import select
        res = await session.exec(select(User).where(User.username == "admin"))
        user = res.first()
        if not user:
            admin = User(username="admin", password_hash=get_hash("admin"), role=UserRole.ADMIN)
            editor = User(username="editor", password_hash=get_hash("editor"), role=UserRole.EDITOR)
            viewer = User(username="viewer", password_hash=get_hash("viewer"), role=UserRole.VIEWER)
            session.add(admin)
            session.add(editor)
            session.add(viewer)
            await session.commit()
            print("--- SEEDING COMPLETED ---")

async def get_session() -> AsyncSession:
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
