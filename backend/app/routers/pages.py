from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Book, Page, PageStatus, TextLayer

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PageIn(BaseModel):
    concept: str
    sort_order: int = 0


class PageUpdate(BaseModel):
    concept: Optional[str] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    status: Optional[PageStatus] = None
    critic_notes: Optional[str] = None
    print_check_notes: Optional[str] = None
    leslie_notes: Optional[str] = None
    sort_order: Optional[int] = None


class TextLayerIn(BaseModel):
    label: str
    content: str = ""
    font_name: str = "Helvetica"
    font_size_pt: int = 12
    x_pct: float = 0.5
    y_pct: float = 0.95
    text_anchor: str = "middle"  # start | middle | end
    visible: bool = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _page_dict(page: Page) -> dict:
    return {
        "id": page.id,
        "book_id": page.book_id,
        "sort_order": page.sort_order,
        "concept": page.concept,
        "prompt": page.prompt,
        "negative_prompt": page.negative_prompt,
        "status": page.status,
        "image_path": f"/storage/{page.image_path}" if page.image_path else None,
        "image_dpi": page.image_dpi,
        "image_width_px": page.image_width_px,
        "image_height_px": page.image_height_px,
        "is_pure_bw": page.is_pure_bw,
        "critic_notes": page.critic_notes,
        "print_check_notes": page.print_check_notes,
        "leslie_notes": page.leslie_notes,
        "created_at": page.created_at.isoformat(),
        "updated_at": page.updated_at.isoformat(),
        "text_layers": [_tl_dict(tl) for tl in page.text_layers],
        "version_count": len(page.versions),
    }


def _tl_dict(tl: TextLayer) -> dict:
    return {
        "id": tl.id,
        "label": tl.label,
        "content": tl.content,
        "font_name": tl.font_name,
        "font_size_pt": tl.font_size_pt,
        "x_pct": tl.x_pct,
        "y_pct": tl.y_pct,
        "text_anchor": tl.text_anchor,
        "visible": tl.visible,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/book/{book_id}")
async def list_pages(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.book_id == book_id)
        .order_by(Page.sort_order)
    )
    return [_page_dict(p) for p in result.scalars().all()]


@router.post("/book/{book_id}", status_code=201)
async def create_page(book_id: str, body: PageIn, db: AsyncSession = Depends(get_db)):
    book = await db.get(Book, book_id)
    if not book:
        raise HTTPException(404, "Book not found")

    page = Page(book_id=book_id, concept=body.concept, sort_order=body.sort_order)
    db.add(page)
    await db.commit()
    # Re-load with relationships eagerly so _page_dict doesn't lazy-load in async (MissingGreenlet).
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.id == page.id)
    )
    page = result.scalar_one()
    return _page_dict(page)


@router.get("/{page_id}")
async def get_page(page_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    return _page_dict(page)


@router.patch("/{page_id}")
async def update_page(page_id: str, body: PageUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    for field, val in body.model_dump(exclude_none=True).items():
        setattr(page, field, val)
    page.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(page)
    return _page_dict(page)


@router.delete("/{page_id}", status_code=204)
async def delete_page(page_id: str, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(404, "Page not found")
    await db.delete(page)
    await db.commit()


# ── Text Layers ───────────────────────────────────────────────────────────────

@router.post("/{page_id}/text-layers", status_code=201)
async def add_text_layer(page_id: str, body: TextLayerIn, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(404, "Page not found")
    tl = TextLayer(page_id=page_id, **body.model_dump())
    db.add(tl)
    await db.commit()
    await db.refresh(tl)
    return _tl_dict(tl)


@router.patch("/{page_id}/text-layers/{layer_id}")
async def update_text_layer(
    page_id: str, layer_id: str, body: TextLayerIn, db: AsyncSession = Depends(get_db)
):
    tl = await db.get(TextLayer, layer_id)
    if not tl or tl.page_id != page_id:
        raise HTTPException(404, "Text layer not found")
    for field, val in body.model_dump().items():
        setattr(tl, field, val)
    await db.commit()
    await db.refresh(tl)
    return _tl_dict(tl)


@router.delete("/{page_id}/text-layers/{layer_id}", status_code=204)
async def delete_text_layer(page_id: str, layer_id: str, db: AsyncSession = Depends(get_db)):
    tl = await db.get(TextLayer, layer_id)
    if not tl or tl.page_id != page_id:
        raise HTTPException(404, "Text layer not found")
    await db.delete(tl)
    await db.commit()
