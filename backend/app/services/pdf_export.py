"""
Print-PDF assembly.

Assembles approved pages into a print-ready, multi-page, vector PDF via PyMuPDF.
Each output page is sized to trim + bleed and the line art is placed inside the
margin box. Line art comes from the vectorized SVG (traced raster), and text
layers are merged in as editable SVG ``<text>`` — vector throughout, never a
flattened raster.

No system libraries required: PyMuPDF bundles MuPDF (no cairo/pango).

File I/O is routed through the storage service so that switching
STORAGE_BACKEND=r2 transparently reads from and writes to Cloudflare R2.
The exported PDF is written locally first, then uploaded to storage, and the
local copy is removed when the r2 backend is active.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from app.models import Book, Page, StyleGuide
from app.services.svg_text import merge_text_into_svg
from app.services.vectorize import trace_to_svg
from app.services import storage as _storage

PT_PER_INCH = 72.0


def _content_box_pt(
    trim_w_in: float,
    trim_h_in: float,
    bleed_in: float,
    margin_in: float,
    binding_gutter_in: float = 0.0,
    binding_edge: str = "left",
) -> tuple[float, float, float, float]:
    """
    Compute the content box (x0, y0, width, height) in points, inset from the
    page edge by bleed + margin on all four sides, plus an extra
    ``binding_gutter_in`` reserved on just the ``binding_edge`` side for
    spiral/coil binding clearance. The other three edges are unaffected —
    full bleed there.
    """
    page_w_pt = (trim_w_in + 2 * bleed_in) * PT_PER_INCH
    page_h_pt = (trim_h_in + 2 * bleed_in) * PT_PER_INCH
    base_inset = (bleed_in + margin_in) * PT_PER_INCH
    gutter_pt = binding_gutter_in * PT_PER_INCH

    left = base_inset + (gutter_pt if binding_edge == "left" else 0.0)
    right = base_inset + (gutter_pt if binding_edge == "right" else 0.0)
    top = base_inset + (gutter_pt if binding_edge == "top" else 0.0)
    bottom = base_inset + (gutter_pt if binding_edge == "bottom" else 0.0)

    return left, top, page_w_pt - left - right, page_h_pt - top - bottom


def _svg_to_pdf_doc(svg: str) -> "fitz.Document":
    """Convert an SVG string to an in-memory single-page vector PDF document."""
    src = fitz.open(stream=svg.encode("utf-8"), filetype="svg")
    pdf_bytes = src.convert_to_pdf()
    src.close()
    return fitz.open(stream=pdf_bytes, filetype="pdf")


def _line_art_svg_for_page(page: Page, storage_dir: Path) -> str | None:
    """
    Resolve the line-art SVG for a page, reading through the storage service.

    Prefers a persisted SVG on the page's latest version; otherwise traces the
    page's cleaned raster on the fly. Returns the SVG string, or None if the
    page has no usable artwork.
    """
    svg_rel: str | None = None
    if page.versions:
        latest = page.versions[-1]
        svg_rel = getattr(latest, "svg_path", None)

    if svg_rel:
        if _storage.exists(svg_rel):
            return _storage.get_bytes(svg_rel).decode("utf-8", errors="ignore")

    # Fallback: trace the raster now.
    if not page.image_path:
        return None
    if not _storage.exists(page.image_path):
        return None

    # Fetch the raster bytes, write to a temp file, trace, return SVG text.
    raster_bytes = _storage.get_bytes(page.image_path)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_raster:
        tmp_raster_path = Path(tmp_raster.name)
    tmp_raster_path.write_bytes(raster_bytes)
    tmp_svg = Path(tempfile.mkstemp(suffix=".svg")[1])
    try:
        trace_to_svg(tmp_raster_path, tmp_svg)
        return tmp_svg.read_text(encoding="utf-8", errors="ignore")
    finally:
        tmp_svg.unlink(missing_ok=True)
        tmp_raster_path.unlink(missing_ok=True)


def export_book_pdf(
    book: Book,
    pages: list[Page],
    storage_dir: Path,
    out_path: Path,
) -> Path:
    """
    Build a print-ready vector PDF from approved pages.

    Each page = merged line-art SVG + editable text SVG, placed into a PyMuPDF
    page sized to trim + bleed with margins from the style guide. Raises
    ValueError if no page yields placeable artwork.

    The finished PDF is written to ``out_path`` locally.  It is also uploaded to
    storage under the key derived from ``out_path`` relative to ``storage_dir``
    so that switching STORAGE_BACKEND=r2 transparently stores the export in R2.
    Returns ``out_path`` (the local copy) so callers such as the export router
    can stream it back to the client via FileResponse regardless of backend.
    """
    sg: StyleGuide | None = book.style_guide
    trim_w = sg.trim_width_in if sg else 8.5
    trim_h = sg.trim_height_in if sg else 11.0
    bleed = sg.bleed_in if sg else 0.125
    margin = sg.margin_in if sg else 0.125
    binding_gutter = sg.binding_gutter_in if sg else 0.0
    binding_edge = sg.binding_edge if sg else "left"

    page_w_pt = (trim_w + 2 * bleed) * PT_PER_INCH
    page_h_pt = (trim_h + 2 * bleed) * PT_PER_INCH

    # Content box: inside the margin (margins measured from the trim edge, which
    # sits ``bleed`` in from the page edge), plus a binding gutter reserved on
    # just one edge — the other three stay full bleed.
    box_x0, box_y0, content_w, content_h = _content_box_pt(
        trim_w, trim_h, bleed, margin, binding_gutter, binding_edge
    )

    # Physical height of the content box in points — used to scale text point
    # sizes into the line-art SVG's coordinate space.
    content_h_pt = content_h

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    out = fitz.open()
    placed = 0

    for page in pages:
        line_art = _line_art_svg_for_page(page, storage_dir)
        if line_art is None:
            continue

        merged_svg = merge_text_into_svg(
            line_art, list(page.text_layers), page_height_pt=content_h_pt
        )
        art_doc = _svg_to_pdf_doc(merged_svg)
        try:
            art_page = art_doc[0]
            src_rect = art_page.rect

            # Fit the art into the content box preserving aspect ratio, centered.
            if src_rect.width <= 0 or src_rect.height <= 0:
                continue
            scale = min(content_w / src_rect.width, content_h / src_rect.height)
            draw_w = src_rect.width * scale
            draw_h = src_rect.height * scale
            x0 = box_x0 + (content_w - draw_w) / 2
            y0 = box_y0 + (content_h - draw_h) / 2
            target = fitz.Rect(x0, y0, x0 + draw_w, y0 + draw_h)

            new_page = out.new_page(width=page_w_pt, height=page_h_pt)
            # show_pdf_page embeds the source page as vector content (not raster).
            new_page.show_pdf_page(target, art_doc, 0)
            placed += 1
        finally:
            art_doc.close()

    if placed == 0:
        out.close()
        raise ValueError("No pages with usable artwork to export")

    out.save(str(out_path), garbage=4, deflate=True)
    out.close()

    # Upload the finished PDF to storage (no-op for local when source == dest).
    try:
        pdf_key = str(out_path.relative_to(storage_dir))
    except ValueError:
        # out_path is not under storage_dir — use the filename as the key.
        pdf_key = f"exports/{out_path.name}"
    _storage.put_file(pdf_key, out_path, "application/pdf")

    return out_path
