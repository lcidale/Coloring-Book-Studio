"""
Generation router: builds prompts, calls image gen, runs print checks.
"""
from __future__ import annotations
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Page, PageStatus, PageVersion, StyleGuide
from app.services.prompt_builder import build_prompt
from app.services.image_gen import generate_line_art
from app.services.image_proc import analyse, threshold_to_pure_bw, set_dpi

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))

router = APIRouter()


class GenerateRequest(BaseModel):
    auto_threshold: bool = True   # convert to pure B&W after generation
    auto_set_dpi: bool = True     # stamp DPI metadata if missing


@router.post("/{page_id}")
async def generate_page(
    page_id: str,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Page)
        .options(
            selectinload(Page.versions),
            selectinload(Page.book).selectinload(Page.book.property.mapper.class_.style_guide),
        )
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    if not page.concept:
        raise HTTPException(400, "Page has no concept — add a concept before generating")

    sg: StyleGuide | None = page.book.style_guide if page.book else None
    positive, negative = build_prompt(page.concept, sg)

    # Save prompts on the page
    page.prompt = positive
    page.negative_prompt = negative
    page.status = PageStatus.generated

    # Version number
    version_num = len(page.versions) + 1

    # Generate
    try:
        rel_path = await generate_line_art(
            positive_prompt=positive,
            negative_prompt=negative,
            book_id=page.book_id,
            page_id=page_id,
            version=version_num,
        )
    except Exception as exc:
        raise HTTPException(502, f"Image generation failed: {exc}")

    abs_path = STORAGE_DIR / rel_path

    # Post-process
    if body.auto_threshold:
        threshold_to_pure_bw(abs_path)
    if body.auto_set_dpi:
        target_dpi = sg.target_dpi if sg else 300
        set_dpi(abs_path, target_dpi)

    # Analyse
    report = analyse(abs_path, target_dpi=sg.target_dpi if sg else 300)

    # Persist version snapshot
    pv = PageVersion(
        page_id=page_id,
        version_num=version_num,
        image_path=str(rel_path),
        prompt=positive,
    )
    db.add(pv)

    # Update page record
    page.image_path = str(rel_path)
    page.image_dpi = report.dpi
    page.image_width_px = report.width_px
    page.image_height_px = report.height_px
    page.is_pure_bw = report.is_pure_bw
    page.print_check_notes = "; ".join(report.issues) if report.issues else "Passed"
    page.status = PageStatus.review

    await db.commit()
    await db.refresh(page)

    return {
        "page_id": page_id,
        "version": version_num,
        "image_url": f"/storage/{rel_path}",
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
            selectinload(Page.book).selectinload(Page.book.property.mapper.class_.style_guide)
        )
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    sg = page.book.style_guide if page.book else None
    positive, negative = build_prompt(page.concept or "", sg)
    return {"positive": positive, "negative": negative}
