from __future__ import annotations
import enum
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Text, Integer, Float, Enum, ForeignKey,
    DateTime, JSON, Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, IS_POSTGRES

# ---------------------------------------------------------------------------
# pgvector support — Postgres only.
# On SQLite the PageEmbedding model is defined but its Vector column falls back
# to a plain Text column so the table can still be created (it just won't be
# useful for ANN search).  All vector operations are guarded in vectors.py.
# ---------------------------------------------------------------------------
EMBEDDING_DIM = 1024  # Mistral mistral-embed output dimension

if IS_POSTGRES:
    try:
        from pgvector.sqlalchemy import Vector as _VectorType  # type: ignore[import]
        _EMBEDDING_COLUMN_TYPE = _VectorType(EMBEDDING_DIM)
    except ImportError:  # pgvector not installed — treat as text fallback
        _EMBEDDING_COLUMN_TYPE = Text  # type: ignore[assignment]
else:
    _EMBEDDING_COLUMN_TYPE = Text  # type: ignore[assignment]


def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime:
    return datetime.utcnow()


class PageStatus(str, enum.Enum):
    idea = "idea"
    prompt = "prompt"
    generated = "generated"
    review = "review"
    revision = "revision"
    approved = "approved"
    print_ready = "print_ready"
    exported = "exported"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200))
    theme: Mapped[str] = mapped_column(Text, default="")
    audience: Mapped[str] = mapped_column(String(200), default="")
    positioning: Mapped[str] = mapped_column(Text, default="")
    emoji: Mapped[str] = mapped_column(String(8), default="📖")
    target_page_count: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    style_guide: Mapped[Optional["StyleGuide"]] = relationship(
        "StyleGuide", back_populates="book", uselist=False, cascade="all, delete-orphan"
    )
    pages: Mapped[List["Page"]] = relationship(
        "Page", back_populates="book", cascade="all, delete-orphan", order_by="Page.sort_order"
    )
    inspiration_images: Mapped[List["InspirationImage"]] = relationship(
        "InspirationImage", back_populates="book", cascade="all, delete-orphan"
    )


class StyleGuide(Base):
    __tablename__ = "style_guides"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(String, ForeignKey("books.id"), unique=True)

    # Core style parameters
    line_weight: Mapped[str] = mapped_column(String(50), default="medium")  # thin | medium | thick | varied
    detail_level: Mapped[str] = mapped_column(String(50), default="moderate")  # minimal | moderate | intricate
    white_space: Mapped[str] = mapped_column(String(50), default="balanced")  # minimal | balanced | generous
    motifs: Mapped[str] = mapped_column(Text, default="")  # recurring visual elements

    # Prompt fragments injected into every page prompt
    positive_prefix: Mapped[str] = mapped_column(Text, default="")
    positive_suffix: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")

    # Print spec
    trim_width_in: Mapped[float] = mapped_column(Float, default=8.5)
    trim_height_in: Mapped[float] = mapped_column(Float, default=11.0)
    bleed_in: Mapped[float] = mapped_column(Float, default=0.125)
    # Deterministic safety margin, not a decorative border — see print_spec.py.
    margin_in: Mapped[float] = mapped_column(Float, default=0.125)
    target_dpi: Mapped[int] = mapped_column(Integer, default=300)

    # Binding clearance: an extra blank strip reserved on just one edge (in
    # addition to margin_in) so spiral/coil punches don't go through the art.
    # The opposite three edges are unaffected — full bleed there.
    binding_gutter_in: Mapped[float] = mapped_column(Float, default=0.0)
    binding_edge: Mapped[str] = mapped_column(String(10), default="left")  # left | right | top | bottom

    # Raw JSON for anything extra
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    book: Mapped["Book"] = relationship("Book", back_populates="style_guide")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(String, ForeignKey("books.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    reference_image_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("inspiration_images.id"), nullable=True
    )

    # Concept
    concept: Mapped[str] = mapped_column(Text, default="")   # human-readable page idea
    prompt: Mapped[str] = mapped_column(Text, default="")    # full assembled AI prompt
    negative_prompt: Mapped[str] = mapped_column(Text, default="")

    # Status
    status: Mapped[PageStatus] = mapped_column(Enum(PageStatus), default=PageStatus.idea)

    # Generated image (relative path from STORAGE_DIR)
    image_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    image_dpi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_width_px: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    image_height_px: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_pure_bw: Mapped[bool] = mapped_column(Boolean, default=False)

    # Review notes
    critic_notes: Mapped[str] = mapped_column(Text, default="")
    print_check_notes: Mapped[str] = mapped_column(Text, default="")
    leslie_notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    book: Mapped["Book"] = relationship("Book", back_populates="pages")
    text_layers: Mapped[List["TextLayer"]] = relationship(
        "TextLayer", back_populates="page", cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[List["GenerationJob"]] = relationship(
        "GenerationJob", cascade="all, delete-orphan"
    )
    versions: Mapped[List["PageVersion"]] = relationship(
        "PageVersion", back_populates="page", cascade="all, delete-orphan",
        order_by="PageVersion.created_at"
    )


class TextLayer(Base):
    """Text/labels stored separately — never embedded in the AI image."""
    __tablename__ = "text_layers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    page_id: Mapped[str] = mapped_column(String, ForeignKey("pages.id"))

    label: Mapped[str] = mapped_column(String(200))       # e.g. "page_title", "page_number", "caption"
    content: Mapped[str] = mapped_column(Text, default="")
    font_name: Mapped[str] = mapped_column(String(100), default="Helvetica")
    font_size_pt: Mapped[int] = mapped_column(Integer, default=12)
    x_pct: Mapped[float] = mapped_column(Float, default=0.5)   # 0-1 relative to page width
    y_pct: Mapped[float] = mapped_column(Float, default=0.95)  # 0-1 relative to page height
    text_anchor: Mapped[str] = mapped_column(String(20), default="middle")  # start | middle | end
    visible: Mapped[bool] = mapped_column(Boolean, default=True)

    page: Mapped["Page"] = relationship("Page", back_populates="text_layers")


class PageVersion(Base):
    """Immutable snapshot every time a new image is generated."""
    __tablename__ = "page_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    page_id: Mapped[str] = mapped_column(String, ForeignKey("pages.id"))
    version_num: Mapped[int] = mapped_column(Integer, default=1)
    image_path: Mapped[str] = mapped_column(String)
    svg_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # vectorized line art
    prompt: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    label: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    dpi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    width_px: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height_px: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_pure_bw: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    page: Mapped["Page"] = relationship("Page", back_populates="versions")


class InspirationImage(Base):
    """Reference / mood-board image. Global when book_id is NULL."""
    __tablename__ = "inspiration_images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    book_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("books.id"), nullable=True)
    image_path: Mapped[str] = mapped_column(String)          # storage key: inspiration/<uuid>.<ext>
    caption: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    book: Mapped[Optional["Book"]] = relationship("Book", back_populates="inspiration_images")


class GenerationJob(Base):
    """Async generation job tracking a single page-generation pipeline run."""
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    page_id: Mapped[str] = mapped_column(String, ForeignKey("pages.id"))
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class AppSettings(Base):
    """
    Global, single-row application settings.

    Holds the *global* image provider + model used for generation when a call
    does not pass an explicit provider/model.  Exactly one row exists; it is
    created on first access via the get-or-create helper in routers/settings.py
    with values seeded from the IMAGE_PROVIDER / model env defaults.
    """
    __tablename__ = "app_settings"

    # Fixed sentinel primary key — there is only ever one settings row.
    id: Mapped[str] = mapped_column(String, primary_key=True, default="global")

    image_provider: Mapped[str] = mapped_column(String(50), default="replicate")
    image_model: Mapped[str] = mapped_column(String(200), default="")

    concept_provider: Mapped[str] = mapped_column(String(50), default="")
    concept_model: Mapped[str] = mapped_column(String(200), default="")
    prompt_provider: Mapped[str] = mapped_column(String(50), default="")
    prompt_model: Mapped[str] = mapped_column(String(200), default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class PageEmbedding(Base):
    """
    Semantic embedding for a Page (concept + prompt text).

    On Postgres + pgvector: the ``embedding`` column is a real Vector(1024)
    that supports cosine-distance ANN search via the <=> operator.

    On SQLite: the column is stored as Text (serialised JSON list) so the
    table can be created and app boot succeeds, but search operations in
    vectors.py are no-ops / raise a clear error.
    """
    __tablename__ = "page_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    page_id: Mapped[str] = mapped_column(String, ForeignKey("pages.id"), unique=True, index=True)

    # Vector column type is resolved at import time: pgvector.sqlalchemy.Vector
    # on Postgres, Text on SQLite (see top of file).
    embedding: Mapped[Optional[object]] = mapped_column(
        _EMBEDDING_COLUMN_TYPE, nullable=True
    )

    # The text that was embedded (for cache-invalidation / debugging).
    embedded_text: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    page: Mapped["Page"] = relationship("Page")
