from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
import uuid

class UserRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

class PageCategory(str, Enum):
    MEETING = "meeting"
    PROJECT = "project"
    INCIDENT = "incident"
    PERSONAL = "personal"

class PageStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

class PagePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"



# Models Refactor
class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    role: UserRole = Field(default=UserRole.VIEWER)

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str
    
    pages: list["Page"] = Relationship(back_populates="author", sa_relationship_kwargs={"primaryjoin": "User.id==Page.author_id"})
    assigned_pages: list["Page"] = Relationship(back_populates="assignee", sa_relationship_kwargs={"primaryjoin": "User.id==Page.assignee_id"})

class UserRead(UserBase):
    id: int

class PageBase(SQLModel):
    title: str
    content: str = Field(sa_column_kwargs={"default": ""})
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    category: PageCategory = Field(default=PageCategory.PERSONAL)
    status: PageStatus = Field(default=PageStatus.DRAFT)
    priority: PagePriority = Field(default=PagePriority.MEDIUM)
    assignee_id: Optional[int] = Field(default=None, foreign_key="user.id")

class Page(PageBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    author_id: Optional[int] = Field(default=None, foreign_key="user.id")
    author: Optional[User] = Relationship(back_populates="pages", sa_relationship_kwargs={"foreign_keys": "[Page.author_id]"})
    assignee: Optional[User] = Relationship(back_populates="assigned_pages", sa_relationship_kwargs={"foreign_keys": "[Page.assignee_id]"})

class PageCreate(PageBase):
    pass

class PageRead(PageBase):
    id: int
    author_id: Optional[int]
    created_at: datetime
    updated_at: datetime

class StorageFile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    filesize: int
    url: str
    uploaded_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
