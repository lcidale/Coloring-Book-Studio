import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Book, Page, PageStatus
from app.services.pdf_export import export_book_pdf

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))

router = APIRouter()


@router.post("/book/{book_id}/pdf")
async def export_pdf(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Book)
        .options(selectinload(Book.style_guide))
        .where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(404, "Book not found")

    pages_result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers))
        .where(
            Page.book_id == book_id,
            Page.status.in_([PageStatus.approved, PageStatus.print_ready, PageStatus.exported]),
            Page.image_path.isnot(None),
        )
        .order_by(Page.sort_order)
    )
    pages = pages_result.scalars().all()

    if not pages:
        raise HTTPException(400, "No approved pages with images to export")

    export_dir = STORAGE_DIR / "books" / book_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    out_path = export_dir / f"{book.title.replace(' ', '_')}_print_ready.pdf"

    export_book_pdf(book, list(pages), STORAGE_DIR, out_path)

    # Mark pages as exported
    for page in pages:
        page.status = PageStatus.exported
    await db.commit()

    return FileResponse(
        path=str(out_path),
        media_type="application/pdf",
        filename=out_path.name,
    )
