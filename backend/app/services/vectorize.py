"""
Vectorization: trace a cleaned pure-B&W raster line drawing into clean SVG with
vtracer (binary mode, tuned for line art), and render SVG -> PNG/PDF via PyMuPDF
at a requested DPI.

No system libraries are required: vtracer ships a self-contained wheel and
PyMuPDF bundles MuPDF, so there is no cairo/pango dependency.

File I/O is routed through the storage service so that switching
STORAGE_BACKEND=r2 transparently reads/writes from Cloudflare R2.
The low-level helpers (trace_to_svg, render_svg_to_*) still operate on local
Path objects for compatibility with PyMuPDF/vtracer. The storage-aware wrapper
``vectorize_page_by_key`` fetches input from storage, runs the pipeline, and
uploads outputs back to storage.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import vtracer

from app.services import storage as _storage

_STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage"))

# vtracer parameters tuned for clean black-on-white line art.
#   colormode="binary"  -> two-color (black/white) tracing, no color layers
#   filter_speckle      -> drop tiny blobs left after raster cleanup
#   mode="spline"       -> smooth Bezier curves for organic line art
#   path/corner/length  -> simplification tuned so lines stay crisp but compact
_LINE_ART_PARAMS = dict(
    colormode="binary",
    hierarchical="stacked",
    mode="spline",
    filter_speckle=4,
    corner_threshold=60,
    length_threshold=4.0,
    splice_threshold=45,
    path_precision=6,
)


def trace_to_svg(raster_path: Path, svg_path: Path, **overrides) -> Path:
    """
    Trace a cleaned B&W raster into an SVG of vector paths.

    Returns the SVG path. Writes a pure-path SVG (no raster <image> tags).
    """
    raster_path = Path(raster_path)
    svg_path = Path(svg_path)
    svg_path.parent.mkdir(parents=True, exist_ok=True)

    params = {**_LINE_ART_PARAMS, **overrides}
    vtracer.convert_image_to_svg_py(str(raster_path), str(svg_path), **params)
    return svg_path


def svg_path_count(svg_path: Path) -> int:
    """Count <path> elements in an SVG (used for fallback heuristics / checks)."""
    text = Path(svg_path).read_text(encoding="utf-8", errors="ignore")
    return text.count("<path")


def render_svg_to_pdf(svg_path: Path, pdf_path: Path) -> Path:
    """
    Render an SVG to a single-page vector PDF via PyMuPDF.

    The SVG is converted to a PDF page preserving vectors (no rasterization),
    so it scales crisply to any print size.
    """
    import fitz  # PyMuPDF

    svg_path = Path(svg_path)
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    svg_bytes = svg_path.read_bytes()
    # PyMuPDF parses SVG as a "story"/document; convert it to PDF bytes.
    doc = fitz.open(stream=svg_bytes, filetype="svg")
    pdf_bytes = doc.convert_to_pdf()
    doc.close()
    Path(pdf_path).write_bytes(pdf_bytes)
    return pdf_path


def render_svg_to_png(svg_path: Path, png_path: Path, dpi: int = 300) -> Path:
    """
    Rasterize an SVG to PNG at the requested DPI via PyMuPDF (for previews).
    """
    import fitz  # PyMuPDF

    svg_path = Path(svg_path)
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(stream=svg_path.read_bytes(), filetype="svg")
    page = doc[0]
    zoom = dpi / 72.0  # PyMuPDF base unit is 72 DPI
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(str(png_path))
    doc.close()
    return png_path


def vectorize_page(
    raster_path: Path,
    svg_path: Path,
    preview_png_path: Path | None = None,
    preview_dpi: int = 150,
) -> Path:
    """
    Convenience pipeline: trace raster -> SVG, optionally render a preview PNG.
    Returns the SVG path.

    Callers pass absolute local paths; this function does not touch storage
    directly.  Use ``vectorize_page_by_key`` for the storage-aware variant.
    """
    trace_to_svg(raster_path, svg_path)
    if preview_png_path is not None:
        render_svg_to_png(svg_path, preview_png_path, dpi=preview_dpi)
    return svg_path


def vectorize_page_by_key(
    raster_key: str,
    svg_key: str,
    preview_key: str | None = None,
    preview_dpi: int = 150,
) -> str:
    """
    Storage-aware vectorization pipeline.

    Fetches the raster from storage by key, runs the trace + optional preview,
    then uploads SVG (and preview PNG) back to storage.

    For the local backend: reads/writes resolve to STORAGE_DIR, identical to
    calling ``vectorize_page`` with absolute paths derived from STORAGE_DIR.

    For the r2 backend: downloads the raster to a temp dir, runs vtracer/PyMuPDF
    locally, uploads outputs to R2, then cleans up the temp dir.

    Returns the SVG storage key.
    """
    if _storage.STORAGE_BACKEND == "local":
        # Local path shortcut — avoid unnecessary copies.
        raster_abs = _STORAGE_DIR / raster_key
        svg_abs = _STORAGE_DIR / svg_key
        preview_abs = (_STORAGE_DIR / preview_key) if preview_key else None
        vectorize_page(raster_abs, svg_abs, preview_abs, preview_dpi)
        return svg_key

    # R2 (or any non-local) backend: stage everything in a temp directory.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        raster_local = tmp_path / Path(raster_key).name
        raster_local.write_bytes(_storage.get_bytes(raster_key))

        svg_local = tmp_path / Path(svg_key).name
        preview_local = (tmp_path / Path(preview_key).name) if preview_key else None

        vectorize_page(raster_local, svg_local, preview_local, preview_dpi)

        _storage.put_file(svg_key, svg_local, "image/svg+xml")
        if preview_key and preview_local and preview_local.exists():
            _storage.put_file(preview_key, preview_local, "image/png")

    return svg_key
