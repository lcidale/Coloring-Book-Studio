from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Book, StyleGuide, Page, PageStatus, PageVersion, InspirationImage
from app.services import storage

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class StyleGuideIn(BaseModel):
    line_weight: str = "medium"
    detail_level: str = "moderate"
    white_space: str = "balanced"
    motifs: str = ""
    positive_prefix: str = ""
    positive_suffix: str = ""
    negative_prompt: str = ""
    trim_width_in: float = 8.5
    trim_height_in: float = 11.0
    bleed_in: float = 0.125
    margin_in: float = 0.5
    target_dpi: int = 300


class BookIn(BaseModel):
    title: str
    theme: str = ""
    audience: str = ""
    positioning: str = ""
    emoji: str = "📖"
    target_page_count: int = 30
    style_guide: Optional[StyleGuideIn] = None


class BookUpdate(BaseModel):
    title: Optional[str] = None
    theme: Optional[str] = None
    audience: Optional[str] = None
    positioning: Optional[str] = None
    emoji: Optional[str] = None
    target_page_count: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _book_dict(book: Book, page_counts: Optional[dict] = None) -> dict:
    counts = page_counts or {}
    total = counts.get("total", 0)
    approved = counts.get("approved", 0)
    return {
        "id": book.id,
        "title": book.title,
        "theme": book.theme,
        "audience": book.audience,
        "positioning": book.positioning,
        "emoji": book.emoji,
        "target_page_count": book.target_page_count,
        "page_count": total,
        "approved_count": approved,
        "progress_pct": round(total / book.target_page_count * 100) if book.target_page_count else 0,
        "created_at": book.created_at.isoformat(),
        "updated_at": book.updated_at.isoformat(),
        "style_guide": _sg_dict(book.style_guide) if book.style_guide else None,
    }


def _sg_dict(sg: StyleGuide) -> dict:
    return {
        "id": sg.id,
        "line_weight": sg.line_weight,
        "detail_level": sg.detail_level,
        "white_space": sg.white_space,
        "motifs": sg.motifs,
        "positive_prefix": sg.positive_prefix,
        "positive_suffix": sg.positive_suffix,
        "negative_prompt": sg.negative_prompt,
        "trim_width_in": sg.trim_width_in,
        "trim_height_in": sg.trim_height_in,
        "bleed_in": sg.bleed_in,
        "margin_in": sg.margin_in,
        "target_dpi": sg.target_dpi,
        "updated_at": sg.updated_at.isoformat(),
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_books(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Book).options(selectinload(Book.style_guide)).order_by(Book.updated_at.desc())
    )
    books = result.scalars().all()

    # Batch fetch page counts
    counts_result = await db.execute(
        select(Page.book_id, func.count(Page.id).label("total"))
        .group_by(Page.book_id)
    )
    counts = {row.book_id: {"total": row.total, "approved": 0} for row in counts_result}

    approved_result = await db.execute(
        select(Page.book_id, func.count(Page.id).label("n"))
        .where(Page.status.in_([PageStatus.approved, PageStatus.print_ready, PageStatus.exported]))
        .group_by(Page.book_id)
    )
    for row in approved_result:
        if row.book_id in counts:
            counts[row.book_id]["approved"] = row.n

    return [_book_dict(b, counts.get(b.id, {})) for b in books]


@router.post("", status_code=201)
async def create_book(body: BookIn, db: AsyncSession = Depends(get_db)):
    book = Book(
        title=body.title,
        theme=body.theme,
        audience=body.audience,
        positioning=body.positioning,
        emoji=body.emoji,
        target_page_count=body.target_page_count,
    )
    db.add(book)
    await db.flush()

    sg_data = body.style_guide or StyleGuideIn()
    sg = StyleGuide(book_id=book.id, **sg_data.model_dump())
    db.add(sg)
    await db.commit()
    await db.refresh(book)
    book.style_guide = sg
    return _book_dict(book)


@router.get("/{book_id}")
async def get_book(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Book).options(selectinload(Book.style_guide)).where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(404, "Book not found")
    return _book_dict(book)


@router.patch("/{book_id}")
async def update_book(book_id: str, body: BookUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Book).options(selectinload(Book.style_guide)).where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(404, "Book not found")

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(book, field, val)
    book.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(book)
    return _book_dict(book)


@router.put("/{book_id}/style-guide")
async def upsert_style_guide(book_id: str, body: StyleGuideIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Book).options(selectinload(Book.style_guide)).where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(404, "Book not found")

    if book.style_guide:
        for field, val in body.model_dump().items():
            setattr(book.style_guide, field, val)
        book.style_guide.updated_at = datetime.utcnow()
    else:
        sg = StyleGuide(book_id=book_id, **body.model_dump())
        db.add(sg)

    await db.commit()
    await db.refresh(book)
    return _sg_dict(book.style_guide)


@router.delete("/{book_id}", status_code=204)
async def delete_book(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Book)
        .options(
            selectinload(Book.pages).selectinload(Page.versions),
            selectinload(Book.inspiration_images),
        )
        .where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(404, "Book not found")
    # delete page-version storage objects
    for page in book.pages:
        for v in page.versions:
            for key in (v.image_path, v.svg_path):
                if key:
                    storage.delete_object(key)
    # delete inspiration storage objects
    for img in book.inspiration_images:
        if img.image_path:
            storage.delete_object(img.image_path)
    # Null any page reference pointing at this book's inspiration images before the
    # cascade delete, so the page→inspiration_image FK can't be violated by delete ordering.
    await db.execute(
        update(Page).where(Page.book_id == book_id).values(reference_image_id=None)
    )
    await db.delete(book)
    await db.commit()
