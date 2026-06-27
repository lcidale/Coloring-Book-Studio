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
from app.database import Base


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
    margin_in: Mapped[float] = mapped_column(Float, default=0.5)
    target_dpi: Mapped[int] = mapped_column(Integer, default=300)

    # Raw JSON for anything extra
    extra: Mapped[dict] = mapped_column(JSON, default=dict)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    book: Mapped["Book"] = relationship("Book", back_populates="style_guide")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    book_id: Mapped[str] = mapped_column(String, ForeignKey("books.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

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
    visible: Mapped[bool] = mapped_column(Boolean, default=True)

    page: Mapped["Page"] = relationship("Page", back_populates="text_layers")


class PageVersion(Base):
    """Immutable snapshot every time a new image is generated."""
    __tablename__ = "page_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    page_id: Mapped[str] = mapped_column(String, ForeignKey("pages.id"))
    version_num: Mapped[int] = mapped_column(Integer, default=1)
    image_path: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    page: Mapped["Page"] = relationship("Page", back_populates="versions")
