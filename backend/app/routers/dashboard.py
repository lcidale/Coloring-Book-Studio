from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Book, Page, PageStatus

router = APIRouter()


# ── Static agents registry ─────────────────────────────────────────────────────

_AGENTS = [
    {
        "name": "Concept Agent",
        "description": "Book ideas, niche, audience, positioning",
        "icon": "💡",
        "status": "Ready",
    },
    {
        "name": "Prompt Engineer",
        "description": "Turns ideas into AI image prompts",
        "icon": "✏️",
        "status": "Ready",
    },
    {
        "name": "Line Art Generator",
        "description": "Generates clean black & white line art",
        "icon": "🖼",
        "status": "Active",
    },
    {
        "name": "Page Critic",
        "description": "Reviews pages for print quality",
        "icon": "🔍",
        "status": "Ready",
    },
    {
        "name": "Publishing Prep",
        "description": "KDP, Etsy, print-ready export",
        "icon": "📦",
        "status": "Ready",
    },
]


# ── Relative time helper ───────────────────────────────────────────────────────

def _relative_time(dt: datetime) -> str:
    now = datetime.utcnow()
    diff = now - dt
    total_seconds = int(diff.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s ago"
    if total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes}m ago"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}h ago"
    days = total_seconds // 86400
    if days == 1:
        return "Yesterday"
    return f"{days}d ago"


# ── Kind mapping ───────────────────────────────────────────────────────────────

def _kind_from_status(status: PageStatus) -> str:
    if status == PageStatus.approved:
        return "approved"
    if status in (PageStatus.review, PageStatus.revision):
        return "flagged"
    if status == PageStatus.generated:
        return "generated"
    if status == PageStatus.exported:
        return "exported"
    return "style"


def _text_from_page(page: Page, book_title: str) -> str:
    concept = page.concept.strip() or "Page"
    # Capitalize first letter
    concept = concept[0].upper() + concept[1:] if concept else "Page"

    status = page.status
    if status == PageStatus.approved:
        return f"{concept} passed quality check"
    if status == PageStatus.review:
        return f"{concept} sent for review"
    if status == PageStatus.revision:
        return f"{concept} flagged for revision"
    if status == PageStatus.generated:
        return f"{concept} generated for {book_title}"
    if status == PageStatus.exported:
        return f"{concept} exported from {book_title}"
    if status == PageStatus.print_ready:
        return f"{concept} marked print-ready in {book_title}"
    if status == PageStatus.prompt:
        return f"Prompt built for {concept}"
    return f"{concept} added to {book_title}"


# ── Dashboard endpoints ────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    # active_books = total book count
    books_result = await db.execute(select(func.count(Book.id)))
    active_books = books_result.scalar() or 0

    # pages_this_week = pages created in last 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    week_result = await db.execute(
        select(func.count(Page.id)).where(Page.created_at >= week_ago)
    )
    pages_this_week = week_result.scalar() or 0

    # print_ready_pages = pages in print_ready or exported
    ready_result = await db.execute(
        select(func.count(Page.id)).where(
            Page.status.in_([PageStatus.print_ready, PageStatus.exported])
        )
    )
    print_ready_pages = ready_result.scalar() or 0

    return {
        "active_books": active_books,
        "pages_this_week": pages_this_week,
        "print_ready_pages": print_ready_pages,
    }


@router.get("/dashboard/activity")
async def get_activity(limit: int = 8, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.book))
        .order_by(Page.updated_at.desc())
        .limit(limit)
    )
    pages = result.scalars().all()

    items = []
    for page in pages:
        book_title = page.book.title if page.book else "Unknown Book"
        items.append({
            "text": _text_from_page(page, book_title),
            "kind": _kind_from_status(page.status),
            "when": _relative_time(page.updated_at),
        })
    return items


@router.get("/dashboard/agents")
async def get_agents():
    return _AGENTS


@router.get("/dashboard/print-readiness")
async def get_print_readiness(db: AsyncSession = Depends(get_db)):
    # Get all books that have at least one page
    books_result = await db.execute(
        select(Book).options(selectinload(Book.pages)).order_by(Book.updated_at.desc())
    )
    books = books_result.scalars().all()

    rows = []
    for book in books:
        pages = book.pages
        if not pages:
            continue
        total_count = len(pages)
        ready_count = sum(
            1 for p in pages if p.status in (PageStatus.print_ready, PageStatus.exported)
        )
        rows.append({
            "book_id": book.id,
            "title": book.title,
            "ready_count": ready_count,
            "total_count": total_count,
        })
    return rows


# ── Per-book status summary ───────────────────────────────────────────────────

@router.get("/books/{book_id}/status-summary")
async def get_book_status_summary(book_id: str, db: AsyncSession = Depends(get_db)):
    # Verify book exists
    book_result = await db.execute(select(Book).where(Book.id == book_id))
    book = book_result.scalar_one_or_none()
    if not book:
        raise HTTPException(404, "Book not found")

    # Count pages per status
    counts_result = await db.execute(
        select(Page.status, func.count(Page.id).label("n"))
        .where(Page.book_id == book_id)
        .group_by(Page.status)
    )
    counts = {row.status: row.n for row in counts_result}

    return {
        "idea": counts.get(PageStatus.idea, 0),
        "prompt": counts.get(PageStatus.prompt, 0),
        "generated": counts.get(PageStatus.generated, 0),
        "review": counts.get(PageStatus.review, 0),
        "revision": counts.get(PageStatus.revision, 0),
        "approved": counts.get(PageStatus.approved, 0),
        "print_ready": counts.get(PageStatus.print_ready, 0),
        "exported": counts.get(PageStatus.exported, 0),
    }
