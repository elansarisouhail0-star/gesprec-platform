import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_optional_user
from app.models import Photo, User
from app.routers.declarations import load_declaration
from app.schemas import DeclarationOut
from app.services import add_history

router = APIRouter(prefix="/declarations", tags=["uploads"])
settings = get_settings()


@router.post("/{declaration_id}/photos", response_model=DeclarationOut)
async def upload_photo(
    declaration_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Seules les images sont acceptees")

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier trop volumineux")

    declaration = load_declaration(db, declaration_id)
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    extension = Path(file.filename or "photo").suffix.lower()[:12] or ".jpg"
    filename = f"{declaration.reference}-{uuid4().hex}{extension}"
    file_path = upload_root / filename
    file_path.write_bytes(content)

    db.add(
        Photo(
            declaration_id=declaration.id,
            filename=filename,
            original_name=os.path.basename(file.filename or filename),
            content_type=file.content_type,
            path=str(file_path),
        )
    )
    add_history(db, declaration, f"Photo ajoutee: {file.filename}", user)
    db.commit()
    return load_declaration(db, declaration_id)
