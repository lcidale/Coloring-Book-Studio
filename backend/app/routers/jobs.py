"""
Async generation jobs.

``POST /api/pages/{id}/generate`` enqueues a background job that runs the full
generation pipeline (build prompt -> generate raster -> cleanup -> vectorize ->
persist a page version) and returns ``{job_id, status}``. ``GET /api/jobs/{id}``
returns the job's status/result. The pipeline never blocks the request.
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import SessionLocal, get_db
from app.models import (
    Book,
    GenerationJob,
    JobStatus,
    Page,
    PageStatus,
    PageVersion,
    StyleGuide,
)
from app.services.image_gen import generate_line_art
from app.services.image_proc import analyse, cleanup
from app.services.prompt_builder import build_prompt
from app.services.vectorize import vectorize_page

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))

router = APIRouter()


class GenerateRequest(BaseModel):
    auto_cleanup: bool = True   # threshold/despeckle/trim/DPI after generation
    vectorize: bool = True      # trace cleaned raster to SVG


def _job_dict(job: GenerationJob) -> dict:
    return {
        "job_id": job.id,
        "page_id": job.page_id,
        "status": job.status.value if isinstance(job.status, JobStatus) else job.status,
        "error": job.error,
        "result_version": job.result_version,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.post("/pages/{page_id}/generate", status_code=202)
async def enqueue_generation(
    page_id: str,
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(404, "Page not found")
    if not page.concept:
        raise HTTPException(400, "Page has no concept — add a concept before generating")

    job = GenerationJob(page_id=page_id, status=JobStatus.queued)
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _run_pipeline,
        job.id,
        page_id,
        body.auto_cleanup,
        body.vectorize,
    )
    return {"job_id": job.id, "status": job.status.value}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(GenerationJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_dict(job)


async def _run_pipeline(
    job_id: str,
    page_id: str,
    auto_cleanup: bool,
    do_vectorize: bool,
) -> None:
    """Run the generation pipeline in its own DB session (request session is gone)."""
    async with SessionLocal() as db:
        job = await db.get(GenerationJob, job_id)
        if job is None:
            return
        job.status = JobStatus.running
        job.started_at = datetime.utcnow()
        await db.commit()

        try:
            version_num = await _generate(db, page_id, auto_cleanup, do_vectorize)
            job.status = JobStatus.done
            job.result_version = version_num
            job.finished_at = datetime.utcnow()
            await db.commit()
        except Exception as exc:  # noqa: BLE001 — record any failure on the job
            await db.rollback()
            job = await db.get(GenerationJob, job_id)
            if job is not None:
                job.status = JobStatus.failed
                job.error = str(exc)
                job.finished_at = datetime.utcnow()
                await db.commit()


async def _generate(
    db: AsyncSession,
    page_id: str,
    auto_cleanup: bool,
    do_vectorize: bool,
) -> int:
    """The actual pipeline. Returns the new version number."""
    result = await db.execute(
        select(Page)
        .options(
            selectinload(Page.versions),
            selectinload(Page.book).selectinload(Book.style_guide),
        )
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if page is None:
        raise ValueError("Page not found")

    sg: StyleGuide | None = page.book.style_guide if page.book else None
    target_dpi = sg.target_dpi if sg else 300
    built = build_prompt(page.concept, sg)
    positive = page.prompt or built[0]
    negative = page.negative_prompt or built[1]

    page.prompt = positive
    page.negative_prompt = negative
    page.status = PageStatus.generated

    version_num = len(page.versions) + 1

    rel_path = await generate_line_art(
        positive_prompt=positive,
        negative_prompt=negative,
        book_id=page.book_id,
        page_id=page_id,
        version=version_num,
        db=db,  # resolve provider+model from the global AppSettings
    )
    abs_path = STORAGE_DIR / rel_path

    if auto_cleanup:
        cleanup(abs_path, target_dpi=target_dpi)

    report = analyse(abs_path, target_dpi=target_dpi)

    svg_rel: str | None = None
    if do_vectorize:
        svg_abs = abs_path.with_suffix(".svg")
        preview_abs = abs_path.with_name(abs_path.stem + "_preview.png")
        vectorize_page(abs_path, svg_abs, preview_png_path=preview_abs)
        svg_rel = str(svg_abs.relative_to(STORAGE_DIR))

    pv = PageVersion(
        page_id=page_id,
        version_num=version_num,
        image_path=str(rel_path),
        svg_path=svg_rel,
        prompt=positive,
    )
    db.add(pv)

    page.image_path = str(rel_path)
    page.image_dpi = report.dpi
    page.image_width_px = report.width_px
    page.image_height_px = report.height_px
    page.is_pure_bw = report.is_pure_bw
    page.print_check_notes = "; ".join(report.issues) if report.issues else "Passed"
    page.status = PageStatus.review

    await db.commit()
    return version_num
