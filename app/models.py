from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum
import uuid

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"

class PageCategory(str, Enum):
    FEATURE = "feature"
    BUG = "bug"
    DEVOPS = "devops"
    MEETING = "meeting"

class PageStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"

class PagePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TeamBase(SQLModel):
    name: str = Field(index=True, unique=True)

class Team(TeamBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    members: list["User"] = Relationship(back_populates="team")

class TeamRead(TeamBase):
    id: int

class TeamCreate(TeamBase):
    pass



# Models Refactor
class UserBase(SQLModel):
    username: str = Field(index=True, unique=True)
    role: UserRole = Field(default=UserRole.MEMBER)
    team_id: Optional[int] = Field(default=None, foreign_key="team.id")

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    password_hash: str
    
    team: Optional[Team] = Relationship(back_populates="members")
    pages: list["Page"] = Relationship(back_populates="author", sa_relationship_kwargs={"primaryjoin": "User.id==Page.author_id"})
    assigned_pages: list["Page"] = Relationship(back_populates="assignee", sa_relationship_kwargs={"primaryjoin": "User.id==Page.assignee_id"})

class UserRead(UserBase):
    id: int
    team_id: Optional[int]

class PageBase(SQLModel):
    title: str
    content: str = Field(sa_column_kwargs={"default": ""})
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    category: PageCategory = Field(default=PageCategory.FEATURE)
    status: PageStatus = Field(default=PageStatus.TODO)
    priority: PagePriority = Field(default=PagePriority.MEDIUM)
    assignee_id: Optional[int] = Field(default=None, foreign_key="user.id")

class Page(PageBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    author_id: Optional[int] = Field(default=None, foreign_key="user.id")
    author: Optional[User] = Relationship(back_populates="pages", sa_relationship_kwargs={"foreign_keys": "[Page.author_id]"})
    assignee: Optional[User] = Relationship(back_populates="assigned_pages", sa_relationship_kwargs={"foreign_keys": "[Page.assignee_id]"})
    files: list["StorageFile"] = Relationship(back_populates="page")

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
    page_id: Optional[int] = Field(default=None, foreign_key="page.id")
    
    page: Optional[Page] = Relationship(back_populates="files")
    uploaded_by: Optional["User"] = Relationship()

class StorageFileRead(SQLModel):
    id: int
    filename: str
    filesize: int
    url: str
    uploaded_at: datetime
    uploaded_by_id: Optional[int]
    page_id: Optional[int]
    uploaded_by: Optional[UserRead] = None

# Update PageRead to include files (Circular ref handling)
class PageRead(PageBase):
    id: int
    author_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    files: list[StorageFileRead] = []
