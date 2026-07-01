from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Book, InspirationImage
from app.services import storage

router = APIRouter()

# content-type -> file extension for allowed image uploads
_ALLOWED_TYPES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


class InspirationUpdate(BaseModel):
    caption: Optional[str] = None
    book_id: Optional[str] = None


def _dict(img: InspirationImage) -> dict:
    return {
        "id": img.id,
        "book_id": img.book_id,
        "image_url": storage.public_url(img.image_path) if img.image_path else None,
        "caption": img.caption,
        "created_at": img.created_at.isoformat() if img.created_at else None,
    }


@router.post("", status_code=201)
async def upload_inspiration(
    files: list[UploadFile] = File(...),
    book_id: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if book_id:
        if not await db.get(Book, book_id):
            raise HTTPException(404, "Book not found")

    # Validate every file's type BEFORE storing any, so a bad file in the batch
    # doesn't leave orphaned objects from earlier files.
    payloads: list[tuple[str, bytes, str]] = []  # (ext, data, content_type)
    for f in files:
        ext = _ALLOWED_TYPES.get(f.content_type or "")
        if not ext:
            raise HTTPException(400, f"Unsupported image type: {f.content_type}")
        payloads.append((ext, await f.read(), f.content_type or "application/octet-stream"))

    created: list[InspirationImage] = []
    for ext, data, content_type in payloads:
        key = f"inspiration/{uuid.uuid4()}.{ext}"
        storage.put_bytes(key, data, content_type)
        img = InspirationImage(book_id=book_id or None, image_path=key, caption=caption)
        db.add(img)
        created.append(img)
    await db.commit()
    for img in created:
        await db.refresh(img)
    return [_dict(i) for i in created]


@router.get("")
async def list_inspiration(book_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(InspirationImage)
    if book_id in (None, "", "all"):
        pass
    elif book_id == "global":
        stmt = stmt.where(InspirationImage.book_id.is_(None))
    else:
        stmt = stmt.where(InspirationImage.book_id == book_id)
    stmt = stmt.order_by(InspirationImage.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_dict(i) for i in rows]


@router.patch("/{image_id}")
async def update_inspiration(image_id: str, body: InspirationUpdate, db: AsyncSession = Depends(get_db)):
    img = await db.get(InspirationImage, image_id)
    if not img:
        raise HTTPException(404, "Inspiration image not found")
    fields = body.model_fields_set  # distinguish explicit null from omitted
    if "caption" in fields:
        img.caption = body.caption
    if "book_id" in fields:
        if body.book_id is not None and not await db.get(Book, body.book_id):
            raise HTTPException(404, "Book not found")
        img.book_id = body.book_id
    await db.commit()
    await db.refresh(img)
    return _dict(img)


@router.delete("/{image_id}", status_code=204)
async def delete_inspiration(image_id: str, db: AsyncSession = Depends(get_db)):
    img = await db.get(InspirationImage, image_id)
    if not img:
        raise HTTPException(404, "Inspiration image not found")
    if img.image_path:
        storage.delete_object(img.image_path)
    await db.delete(img)
    await db.commit()
