"""
Vector embedding service — semantic search over coloring-book pages.

Postgres + pgvector path
------------------------
- ``embed_text(text)``       → calls Mistral ``mistral-embed`` API → list[float]
- ``upsert_page_embedding``  → stores / updates a PageEmbedding row
- ``search_similar``         → cosine-distance ANN via pgvector ``<=>`` operator

SQLite / no-credentials path (graceful degradation)
----------------------------------------------------
All public functions are safe to import on any dialect; the vector operations
raise a clear ``RuntimeError`` when called in an environment where they cannot
work (SQLite dialect, or ``MISTRAL_API_KEY`` not set).

Environment variables
---------------------
``MISTRAL_API_KEY`` — required for live embedding calls.
``EMBEDDING_DIM``   — override dimension (default 1024, matches mistral-embed).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import IS_POSTGRES
from app.models import EMBEDDING_DIM, Page, PageEmbedding

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_postgres(operation: str) -> None:
    """Raise a clear error when a Postgres-only operation is called on SQLite."""
    if not IS_POSTGRES:
        raise RuntimeError(
            f"{operation} requires a Postgres database with pgvector. "
            "Set DATABASE_URL to a postgresql+asyncpg:// URL to enable vector features."
        )


def _require_mistral() -> str:
    """Return the Mistral API key or raise a descriptive error."""
    key = os.getenv("MISTRAL_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "Embeddings not configured: set the MISTRAL_API_KEY environment variable "
            "to enable semantic-search features."
        )
    return key


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def embed_text(text: str) -> list[float]:
    """
    Embed *text* using the Mistral ``mistral-embed`` model.

    Returns a list of floats with length ``EMBEDDING_DIM`` (1024).

    Raises
    ------
    RuntimeError
        If ``MISTRAL_API_KEY`` is not set.
    """
    api_key = _require_mistral()

    # Import lazily so the module can be imported without mistralai installed.
    try:
        from mistralai import Mistral  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "mistralai package is not installed. "
            "Add it to your dependencies (uv add mistralai) to use embedding features."
        ) from exc

    client = Mistral(api_key=api_key)
    response = await client.embeddings.create_async(
        model="mistral-embed",
        inputs=[text],
    )
    return response.data[0].embedding


def _build_embed_text(page: Page) -> str:
    """Concatenate concept + prompt into the text to embed for a page."""
    parts = []
    if page.concept:
        parts.append(page.concept.strip())
    if page.prompt:
        parts.append(page.prompt.strip())
    return " | ".join(parts) if parts else page.concept or ""


async def upsert_page_embedding(db: AsyncSession, page: Page) -> PageEmbedding:
    """
    Compute and persist (insert-or-update) the embedding for *page*.

    Skips re-embedding if the stored ``embedded_text`` is identical to what
    would be embedded now (idempotent on unchanged pages).

    Raises
    ------
    RuntimeError
        On SQLite (IS_POSTGRES is False) or when MISTRAL_API_KEY is missing.
    """
    _require_postgres("upsert_page_embedding")

    text_to_embed = _build_embed_text(page)

    # Check for an existing row.
    result = await db.execute(
        select(PageEmbedding).where(PageEmbedding.page_id == page.id)
    )
    existing: PageEmbedding | None = result.scalar_one_or_none()

    if existing is not None and existing.embedded_text == text_to_embed:
        # Nothing changed — skip the API call.
        return existing

    vector = await embed_text(text_to_embed)

    if existing is None:
        existing = PageEmbedding(page_id=page.id)
        db.add(existing)

    existing.embedding = vector
    existing.embedded_text = text_to_embed
    await db.commit()
    await db.refresh(existing)
    return existing


async def search_similar(
    db: AsyncSession,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """
    Find pages whose embeddings are closest to the embedding of *query*
    using pgvector cosine distance (``<=>``).

    Returns a list of dicts::

        [{"page_id": str, "distance": float}, ...]

    sorted ascending by distance (most similar first).

    Raises
    ------
    RuntimeError
        On SQLite or when MISTRAL_API_KEY is missing.
    """
    _require_postgres("search_similar")

    query_vector = await embed_text(query)

    # pgvector cosine distance operator: <=>
    # We use text() to keep this readable and avoid vendor-specific column expressions
    # while still being compatible with async SQLAlchemy.
    from sqlalchemy import text  # noqa: PLC0415

    # Build query: SELECT page_id, embedding <=> :vec AS distance FROM page_embeddings
    # WHERE embedding IS NOT NULL ORDER BY distance LIMIT :limit
    sql = text(
        "SELECT page_id, embedding <=> :vec AS distance "
        "FROM page_embeddings "
        "WHERE embedding IS NOT NULL "
        "ORDER BY distance "
        "LIMIT :limit"
    )
    rows = await db.execute(sql, {"vec": str(query_vector), "limit": limit})
    return [{"page_id": row.page_id, "distance": float(row.distance)} for row in rows]
