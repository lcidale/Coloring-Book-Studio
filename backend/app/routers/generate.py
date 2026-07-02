"""
Generation router: builds prompts, calls image gen, runs print checks.
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from typing import Optional

from app.database import get_db
from app.models import Book, Page, PageStatus, StyleGuide
from app.routers.pages import _eligible_reference_or_400
from app.services.prompt_builder import build_prompt
from app.services.image_gen import generate_line_art
from app.services.image_proc import analyse, cleanup
from app.services.print_spec import target_border_px, target_px_dimensions
from app.services.vectorize import vectorize_page
from app.services.versioning import record_version

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))

router = APIRouter()


class GenerateRequest(BaseModel):
    auto_cleanup: bool = True   # threshold/despeckle/trim/DPI after generation
    vectorize: bool = True      # trace cleaned raster to SVG
    reference_image_id: Optional[str] = None


@router.post("/{page_id}")
async def generate_page(
    page_id: str,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Synchronous generation (kept for direct/scripted use). The non-blocking path
    the UI uses is POST /api/pages/{id}/generate (see routers/jobs.py).
    """
    result = await db.execute(
        select(Page)
        .options(
            selectinload(Page.versions),
            selectinload(Page.book).selectinload(Book.style_guide),
        )
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    if not page.concept:
        raise HTTPException(400, "Page has no concept — add a concept before generating")

    sg: StyleGuide | None = page.book.style_guide if page.book else None
    target_dpi = sg.target_dpi if sg else 300
    width_px, height_px = target_px_dimensions(sg)
    border_px = target_border_px(sg, target_dpi)
    built = build_prompt(page.concept, sg)
    positive = page.prompt or built[0]
    negative = page.negative_prompt or built[1]

    # Save prompts on the page
    page.prompt = positive
    page.negative_prompt = negative
    page.status = PageStatus.generated

    # Derived from the max surviving version_num, not the row count — a deleted
    # middle version must never free up a number that collides with a survivor's
    # storage key.
    version_num = max((v.version_num for v in page.versions), default=0) + 1

    # Resolve effective reference image (shared eligibility rule — ce-review #9)
    effective_ref_id = body.reference_image_id or page.reference_image_id
    reference_image_key = None
    if effective_ref_id:
        ref = await _eligible_reference_or_400(effective_ref_id, page, db)
        reference_image_key = ref.image_path

    # Generate
    try:
        rel_path = await generate_line_art(
            positive_prompt=positive,
            negative_prompt=negative,
            book_id=page.book_id,
            page_id=page_id,
            version=version_num,
            width=width_px,
            height=height_px,
            db=db,  # resolve provider+model from the global AppSettings
            reference_image_key=reference_image_key,
        )
    except Exception as exc:
        raise HTTPException(502, f"Image generation failed: {exc}")

    abs_path = STORAGE_DIR / rel_path

    # Raster cleanup: threshold -> despeckle -> trim -> stamp DPI
    if body.auto_cleanup:
        cleanup(abs_path, target_dpi=target_dpi, border_px=border_px)

    # Analyse
    report = analyse(abs_path, target_dpi=target_dpi)

    # Vectorize
    svg_rel: str | None = None
    if body.vectorize:
        svg_abs = abs_path.with_suffix(".svg")
        preview_abs = abs_path.with_name(abs_path.stem + "_preview.png")
        vectorize_page(abs_path, svg_abs, preview_png_path=preview_abs)
        svg_rel = str(svg_abs.relative_to(STORAGE_DIR))

    record_version(db, page, version_num, rel_path, svg_rel, positive, report)
    page.status = PageStatus.review

    await db.commit()
    await db.refresh(page)

    return {
        "page_id": page_id,
        "version": version_num,
        "image_url": f"/storage/{rel_path}",
        "svg_url": f"/storage/{svg_rel}" if svg_rel else None,
        "prompt": positive,
        "negative_prompt": negative,
        "print_check": {
            "passed": report.passed,
            "dpi": report.dpi,
            "width_px": report.width_px,
            "height_px": report.height_px,
            "is_pure_bw": report.is_pure_bw,
            "gray_pixel_pct": report.gray_pixel_pct,
            "thin_line_warning": report.thin_line_warning,
            "issues": report.issues,
        },
    }


@router.post("/{page_id}/build-prompt")
async def build_prompt_only(page_id: str, db: AsyncSession = Depends(get_db)):
    """Preview the assembled prompt without generating an image."""
    result = await db.execute(
        select(Page)
        .options(
            selectinload(Page.book).selectinload(Book.style_guide)
        )
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    sg = page.book.style_guide if page.book else None
    positive, negative = build_prompt(page.concept or "", sg)
    return {"positive": positive, "negative": negative}
