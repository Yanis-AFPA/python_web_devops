from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlmodel import select, desc
from sqlmodel.ext.asyncio.session import AsyncSession
from app.database import get_session
from app.models import StorageFile, User
from app.auth import get_current_active_user
import shutil
import os
import uuid
from datetime import datetime

router = APIRouter()
UPLOAD_DIR = "app/static/uploads"

@router.get("/files", response_model=List[StorageFile])
async def list_files(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    query = select(StorageFile).order_by(desc(StorageFile.uploaded_at))
    result = await session.exec(query)
    return result.all()

@router.post("/files", response_model=StorageFile)
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Secure filename and save
    file_ext = file.filename.split(".")[-1] if "." in file.filename else "bin"
    unique_name = f"{uuid.uuid4()}.{file_ext}"
    file_path = f"{UPLOAD_DIR}/{unique_name}"
    
    # Calculate size (seek to end, tell, seek to start) - UploadFile is a SpooledTemporaryFile
    # file.file.seek(0, 2)
    # size = file.file.tell()
    # file.file.seek(0)
    # Actually checking Content-Length header is safer for UploadFile wrapper or reading it.
    # Let's just save it and check size on disk.
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    size = os.path.getsize(file_path)
    url = f"/static/uploads/{unique_name}"
    
    db_file = StorageFile(
        filename=file.filename,
        filesize=size,
        url=url,
        uploaded_by_id=current_user.id,
        uploaded_at=datetime.utcnow()
    )
    
    session.add(db_file)
    await session.commit()
    await session.refresh(db_file)
    return db_file

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user)
):
    db_file = await session.get(StorageFile, file_id)
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
        
    # Permission: Admin or Uploader
    if current_user.role != "admin" and db_file.uploaded_by_id != current_user.id:
         raise HTTPException(status_code=403, detail="Permission denied")
         
    # Remove from disk
    # Extract filename from url or just check path.
    # url is /static/uploads/uuid.ext
    filename = db_file.url.split("/")[-1]
    path = f"{UPLOAD_DIR}/{filename}"
    if os.path.exists(path):
        os.remove(path)
        
    await session.delete(db_file)
    await session.commit()
    return {"ok": True}
