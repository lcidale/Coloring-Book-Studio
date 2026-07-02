"""
Computes the generation canvas size and cleanup border width, in pixels,
from a book's style guide (trim size, DPI, margin) — falling back to
letter-size defaults when no style guide is set.
"""
from __future__ import annotations

from app.models import StyleGuide

DEFAULT_TRIM_WIDTH_IN = 8.5
DEFAULT_TRIM_HEIGHT_IN = 11.0
DEFAULT_MARGIN_IN = 0.5
DEFAULT_DPI = 300


def target_px_dimensions(style_guide: StyleGuide | None) -> tuple[int, int]:
    """Return (width_px, height_px) for the generation canvas."""
    width_in = style_guide.trim_width_in if style_guide else DEFAULT_TRIM_WIDTH_IN
    height_in = style_guide.trim_height_in if style_guide else DEFAULT_TRIM_HEIGHT_IN
    dpi = style_guide.target_dpi if style_guide else DEFAULT_DPI
    return round(width_in * dpi), round(height_in * dpi)


def target_border_px(style_guide: StyleGuide | None, dpi: int) -> int:
    """Return the white-margin border width in pixels at the given DPI."""
    margin_in = style_guide.margin_in if style_guide else DEFAULT_MARGIN_IN
    return round(margin_in * dpi)
