from __future__ import annotations
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Book, Page, PageStatus, PageVersion, TextLayer
from app.services import storage
from app.services import text_gen, text_providers
from app.services.prompt_builder import build_prompt
from app.routers.settings import get_or_create_settings

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class PageIn(BaseModel):
    concept: str
    title: Optional[str] = None
    sort_order: int = 0


class PageUpdate(BaseModel):
    concept: Optional[str] = None
    title: Optional[str] = None
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
        "title": page.title,
        "concept": page.concept,
        "prompt": page.prompt,
        "negative_prompt": page.negative_prompt,
        "status": page.status,
        "image_path": storage.public_url(page.image_path) if page.image_path else None,
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


def _version_dict(page: Page, pv: PageVersion) -> dict:
    return {
        "id": pv.id,
        "page_id": pv.page_id,
        "version_num": pv.version_num,
        "image_url": storage.public_url(pv.image_path) if pv.image_path else None,
        "svg_url": storage.public_url(pv.svg_path) if pv.svg_path else None,
        "prompt": pv.prompt,
        "label": pv.label,
        "notes": pv.notes,
        "dpi": pv.dpi,
        "width_px": pv.width_px,
        "height_px": pv.height_px,
        "is_pure_bw": pv.is_pure_bw,
        "created_at": pv.created_at.isoformat() if pv.created_at else None,
        "is_current": bool(page.image_path) and pv.image_path == page.image_path,
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

    page = Page(book_id=book_id, concept=body.concept,
                title=body.title, sort_order=body.sort_order)
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


@router.post("/{page_id}/versions/{version_id}/restore")
async def restore_version(page_id: str, version_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    pv = next((v for v in page.versions if v.id == version_id), None)
    if pv is None:
        raise HTTPException(404, "Version not found")

    page.image_path = pv.image_path
    page.prompt = pv.prompt
    page.image_dpi = pv.dpi
    page.image_width_px = pv.width_px
    page.image_height_px = pv.height_px
    if pv.is_pure_bw is not None:
        page.is_pure_bw = pv.is_pure_bw
    page.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(page)
    return _page_dict(page)


@router.get("/{page_id}/versions")
async def list_versions(page_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.versions)).where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    ordered = sorted(page.versions, key=lambda v: v.version_num, reverse=True)
    return [_version_dict(page, v) for v in ordered]


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


# ── AI text helpers (no-save) ─────────────────────────────────────────────────

def _load_page_with_book(page_id: str):
    """Return a SQLAlchemy select that eagerly loads Page + book.style_guide."""
    return (
        select(Page)
        .options(
            selectinload(Page.text_layers),
            selectinload(Page.versions),
            selectinload(Page.book).selectinload(Book.style_guide),
        )
        .where(Page.id == page_id)
    )


@router.post("/{page_id}/refine-concept")
async def refine_concept_endpoint(page_id: str, db: AsyncSession = Depends(get_db)):
    """
    Propose a refined concept for the page WITHOUT persisting it.

    Returns ``{"refined_concept": "<text>"}`` on success.
    Raises 404 if the page does not exist.
    Raises 400 if the concept provider is not configured.
    """
    result = await db.execute(_load_page_with_book(page_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    settings = await get_or_create_settings(db)
    provider = settings.concept_provider or "gemini"

    if not text_providers.is_configured(provider):
        # Build a user-friendly message naming the missing key(s).
        entry = text_providers.get_provider(provider)
        if entry is None:
            raise HTTPException(400, f"Concept provider '{provider}' is not configured")
        # Look up required env key names from the raw catalogue via is_configured logic.
        # text_providers exposes is_configured but not env_keys directly; compose the
        # message from known patterns.
        _key_hints = {
            "claude": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY (or GOOGLE_API_KEY)",
        }
        key_hint = _key_hints.get(provider, "the required API key")
        raise HTTPException(
            400,
            f"Concept provider '{provider}' is not configured — set {key_hint}",
        )

    style_guide = page.book.style_guide if page.book else None
    model = settings.concept_model or text_providers.default_model(provider) or ""

    try:
        refined = await text_gen.refine_concept(page.concept, style_guide, provider, model)
    except Exception as exc:  # provider/SDK failure (e.g. invalid/expired key)
        raise HTTPException(502, f"Concept provider '{provider}' request failed") from exc
    return {"refined_concept": refined}


@router.post("/{page_id}/write-prompt")
async def write_prompt_endpoint(page_id: str, db: AsyncSession = Depends(get_db)):
    """
    Propose a positive + negative image prompt for the page WITHOUT persisting it.

    Returns ``{"positive": "<text>", "negative": "<text>"}`` on success.
    Raises 404 if the page does not exist.
    Raises 400 if the prompt provider is not configured.
    """
    result = await db.execute(_load_page_with_book(page_id))
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    settings = await get_or_create_settings(db)
    provider = settings.prompt_provider or "gemini"

    if not text_providers.is_configured(provider):
        _key_hints = {
            "claude": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY (or GOOGLE_API_KEY)",
        }
        key_hint = _key_hints.get(provider, "the required API key")
        raise HTTPException(
            400,
            f"Prompt provider '{provider}' is not configured — set {key_hint}",
        )

    style_guide = page.book.style_guide if page.book else None
    model = settings.prompt_model or text_providers.default_model(provider) or ""

    try:
        positive = await text_gen.write_prompt(page.concept, style_guide, provider, model)
    except Exception as exc:  # provider/SDK failure (e.g. invalid/expired key)
        raise HTTPException(502, f"Prompt provider '{provider}' request failed") from exc
    _, negative = build_prompt(page.concept, style_guide)
    return {"positive": positive, "negative": negative}


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
