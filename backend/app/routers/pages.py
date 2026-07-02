from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Book, InspirationImage, Page, PageStatus, PageVersion, TextLayer
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


class ReorderIn(BaseModel):
    page_ids: list[str]


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
    reference_image_id: Optional[str] = None


class VersionUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None


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

def _reference_url(page: Page) -> str | None:
    img = getattr(page, "_reference_image", None)
    return storage.public_url(img.image_path) if img and img.image_path else None


async def _attach_reference(page: Page, db: AsyncSession) -> None:
    """Load the page's reference InspirationImage onto page._reference_image (or None)."""
    from app.models import InspirationImage
    page._reference_image = (
        await db.get(InspirationImage, page.reference_image_id)
        if page.reference_image_id else None
    )


async def _attach_references(pages: list[Page], db: AsyncSession) -> None:
    """Batched sibling of _attach_reference for multi-page responses (list/reorder).

    One IN(...) query for all distinct reference_image_ids instead of one query
    per page — ce-review #7 (N+1 in list_pages)."""
    from app.models import InspirationImage
    ids = {p.reference_image_id for p in pages if p.reference_image_id}
    if not ids:
        for p in pages:
            p._reference_image = None
        return
    rows = (await db.execute(select(InspirationImage).where(InspirationImage.id.in_(ids)))).scalars().all()
    by_id = {img.id: img for img in rows}
    for p in pages:
        p._reference_image = by_id.get(p.reference_image_id)


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
        "reference_image_id": page.reference_image_id,
        "reference_image_url": _reference_url(page),
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


async def _eligible_reference_or_400(image_id: str, page: Page, db: AsyncSession) -> InspirationImage:
    img = await db.get(InspirationImage, image_id)
    if img is None:
        raise HTTPException(400, "Reference image not found")
    if img.book_id is not None and img.book_id != page.book_id:
        raise HTTPException(400, "Reference image is not available for this book")
    return img


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/book/{book_id}")
async def list_pages(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.book_id == book_id)
        .order_by(Page.sort_order)
    )
    pages = result.scalars().all()
    await _attach_references(pages, db)
    return [_page_dict(p) for p in pages]


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
    await _attach_reference(page, db)
    return _page_dict(page)


@router.patch("/book/{book_id}/reorder")
async def reorder_pages(book_id: str, body: ReorderIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.book_id == book_id)
    )
    pages = {p.id: p for p in result.scalars().all()}
    if set(body.page_ids) != set(pages.keys()) or len(body.page_ids) != len(pages):
        raise HTTPException(400, "page_ids must be exactly the book's pages")
    for idx, pid in enumerate(body.page_ids):
        pages[pid].sort_order = idx
    await db.commit()
    ordered = [pages[pid] for pid in body.page_ids]
    await _attach_references(ordered, db)
    return [_page_dict(p) for p in ordered]


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
    await _attach_reference(page, db)
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
    await _attach_reference(page, db)
    return _page_dict(page)


@router.post("/{page_id}/versions/{version_id}/use-as-reference")
async def use_version_as_reference(page_id: str, version_id: str, db: AsyncSession = Depends(get_db)):
    """Copy a version's image into a new, independent inspiration image scoped to
    this page's book, and set it as the page's sticky reference — one click,
    no manual download/re-upload. The copy is deliberate: never reuse the
    version's own storage key, since delete_version assumes each version's
    image_path is exclusively its own."""
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

    data = storage.get_bytes(pv.image_path)
    ext = pv.image_path.rsplit(".", 1)[-1] if "." in pv.image_path else "png"
    new_key = f"inspiration/{uuid.uuid4()}.{ext}"
    storage.put_bytes(new_key, data, "image/png")

    img = InspirationImage(book_id=page.book_id, image_path=new_key)
    db.add(img)
    await db.flush()

    page.reference_image_id = img.id
    page.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(page)
    await _attach_reference(page, db)
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


@router.patch("/{page_id}/versions/{version_id}")
async def update_version(page_id: str, version_id: str, body: VersionUpdate,
                         db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.versions)).where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    pv = next((v for v in page.versions if v.id == version_id), None)
    if pv is None:
        raise HTTPException(404, "Version not found")
    for field, val in body.model_dump(exclude_none=True).items():
        setattr(pv, field, val)
    await db.commit()
    await db.refresh(pv)
    return _version_dict(page, pv)


@router.delete("/{page_id}/versions/{version_id}", status_code=204)
async def delete_version(page_id: str, version_id: str,
                         db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page).options(selectinload(Page.versions)).where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    pv = next((v for v in page.versions if v.id == version_id), None)
    if pv is None:
        raise HTTPException(404, "Version not found")
    if page.image_path and pv.image_path == page.image_path:
        raise HTTPException(409, "Cannot delete the current version — restore another first")
    # Invariant: each version has a unique image_path (generation writes distinct v{num} paths;
    # restore only copies the reference onto the page, never creates a shared path),
    # so deleting a non-current version never removes a file still referenced by another.
    for key in (pv.image_path, pv.svg_path):
        if key:
            storage.delete_object(key)
    await db.delete(pv)
    await db.commit()


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

    data = body.model_dump(exclude_none=True)
    ref_provided = "reference_image_id" in body.model_fields_set
    data.pop("reference_image_id", None)  # handled explicitly below
    for field, val in data.items():
        setattr(page, field, val)
    if ref_provided:
        if body.reference_image_id is not None:
            await _eligible_reference_or_400(body.reference_image_id, page, db)
        page.reference_image_id = body.reference_image_id
    page.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(page)
    await _attach_reference(page, db)
    return _page_dict(page)


@router.delete("/{page_id}", status_code=204)
async def delete_page(page_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.versions), selectinload(Page.generation_jobs))
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")
    for v in page.versions:
        if v.image_path:
            storage.delete_object_best_effort(v.image_path)
        if v.svg_path:
            storage.delete_object_best_effort(v.svg_path)
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
