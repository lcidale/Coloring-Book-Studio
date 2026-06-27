"""Assets router — Canva cover/marketing asset endpoints.

Endpoints:
    POST /api/assets/books/{book_id}/cover
        Create (and optionally export) a Canva cover design for the book.
        Returns 404 if the book does not exist.
        Returns 503 if CANVA_ACCESS_TOKEN is not configured.

    GET  /api/assets/books/{book_id}
        Return stored asset references for the book.
        (Stub: always returns an empty list until a persistence layer is wired.)
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Book
from app.services import canva as canva_svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class CoverRequest(BaseModel):
    """Body for POST /api/assets/books/{book_id}/cover."""

    subtitle: str = ""
    brand_template_id: Optional[str] = None
    export_format: Optional[str] = None  # 'pdf' | 'png' | None (skip export)


class CoverResponse(BaseModel):
    """Successful cover-creation response."""

    book_id: str
    design_id: str
    edit_url: str
    view_url: str
    export: Optional[dict[str, Any]] = None  # present when export_format is set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_book_or_404(book_id: str, db: AsyncSession) -> Book:
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/books/{book_id}/cover", response_model=CoverResponse)
async def create_cover(
    book_id: str,
    body: CoverRequest = CoverRequest(),
    db: AsyncSession = Depends(get_db),
):
    """Create a Canva cover design for the book.

    - Validates that the book exists (404 if not).
    - Calls Canva Connect API to create the design (503 if not configured).
    - If *export_format* is supplied also runs the async export and returns
      the download URL(s).
    """
    book = await _get_book_or_404(book_id, db)

    try:
        cover = await canva_svc.create_cover(
            book_title=book.title,
            subtitle=body.subtitle,
            brand_template_id=body.brand_template_id,
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "not configured" in msg.lower():
            raise HTTPException(
                status_code=503,
                detail="Canva integration is not configured. "
                       "Set CANVA_ACCESS_TOKEN in the server environment.",
            ) from exc
        raise HTTPException(status_code=502, detail=msg) from exc

    export_data: dict[str, Any] | None = None
    if body.export_format:
        try:
            export_data = await canva_svc.export_asset(
                design_id=cover["design_id"],
                format=body.export_format,
            )
        except RuntimeError as exc:
            msg = str(exc)
            if "not configured" in msg.lower():
                raise HTTPException(status_code=503, detail=msg) from exc
            raise HTTPException(status_code=502, detail=msg) from exc

    return CoverResponse(
        book_id=book_id,
        design_id=cover["design_id"],
        edit_url=cover["edit_url"],
        view_url=cover["view_url"],
        export=export_data,
    )


@router.get("/books/{book_id}")
async def list_assets(
    book_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return stored Canva asset references for the book.

    Currently a stub — returns an empty list.  When a persistence layer is
    added (e.g. a CanvaAsset model), replace the stub body.
    """
    await _get_book_or_404(book_id, db)
    return {"book_id": book_id, "assets": []}
