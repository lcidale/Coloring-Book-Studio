"""
Tests for backend/app/services/pdf_export.py

Covers:
- export_book_pdf(): N approved pages -> N-page PDF with selectable text
- Zero approved pages (no usable artwork) raises ValueError
- PDF dimensions match trim + bleed spec
- Text layers appear in the PDF (vector, not raster)
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import fitz  # PyMuPDF

from app.services.pdf_export import PT_PER_INCH, _content_box_pt, export_book_pdf
from app.services.vectorize import trace_to_svg
from tests.conftest import make_pure_bw_png
import app.services.storage as _storage_mod


# ---------------------------------------------------------------------------
# Helpers to build mock ORM objects
# ---------------------------------------------------------------------------

def _make_style_guide(
    trim_w: float = 8.5,
    trim_h: float = 11.0,
    bleed: float = 0.125,
    margin: float = 0.5,
    binding_gutter: float = 0.0,
    binding_edge: str = "left",
) -> MagicMock:
    sg = MagicMock()
    sg.trim_width_in = trim_w
    sg.trim_height_in = trim_h
    sg.bleed_in = bleed
    sg.margin_in = margin
    sg.target_dpi = 300
    sg.binding_gutter_in = binding_gutter
    sg.binding_edge = binding_edge
    return sg


def _make_book(title: str = "Test Book", sg: MagicMock | None = None) -> MagicMock:
    book = MagicMock()
    book.title = title
    book.style_guide = sg
    return book


def _make_page(
    storage_dir: Path,
    book_id: str = "book1",
    page_id: str = "page1",
    with_svg: bool = True,
    with_text: bool = False,
) -> MagicMock:
    """
    Create a page mock backed by real files in storage_dir.
    If with_svg=True, traces a synthetic PNG to SVG and points the page at it.
    """
    # Create the raster
    raster_dir = storage_dir / "books" / book_id / "pages" / page_id
    raster_dir.mkdir(parents=True, exist_ok=True)
    raster = raster_dir / "v001.png"
    make_pure_bw_png(raster)

    page = MagicMock()
    page.image_path = str(raster.relative_to(storage_dir))

    if with_svg:
        svg_path = raster_dir / "v001.svg"
        trace_to_svg(raster, svg_path)
        version = MagicMock()
        version.svg_path = str(svg_path.relative_to(storage_dir))
        page.versions = [version]
    else:
        page.versions = []

    # Text layers
    if with_text:
        layer = MagicMock()
        layer.content = "Page Title"
        layer.font_name = "Helvetica"
        layer.font_size_pt = 14
        layer.x_pct = 0.5
        layer.y_pct = 0.95
        layer.text_anchor = "middle"
        layer.visible = True
        page.text_layers = [layer]
    else:
        text_layer = MagicMock()
        text_layer.visible = False
        text_layer.content = ""
        page.text_layers = [text_layer]

    return page


# ---------------------------------------------------------------------------
# Fixture: point the storage module at the test's temp directory
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_storage_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Point app.services.storage.STORAGE_DIR at tmp_path/storage for the duration
    of each test.  pdf_export.py calls _storage.exists() / _storage.get_bytes()
    which resolve keys under STORAGE_DIR, so this ensures storage keys written
    by _make_page() are found at runtime.

    Returns the storage root so individual tests can use it if needed; but
    because the fixture is autouse, tests only need to accept tmp_path themselves
    (which pytest provides) and call _make_page(storage_root).
    """
    storage_root = tmp_path / "storage"
    storage_root.mkdir(exist_ok=True)
    monkeypatch.setattr(_storage_mod, "STORAGE_DIR", storage_root)
    return storage_root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExportBookPdf:
    def test_one_page_produces_single_page_pdf(self, tmp_path: Path):
        storage = tmp_path / "storage"
        book = _make_book(sg=_make_style_guide())
        page = _make_page(storage)

        out = tmp_path / "out.pdf"
        export_book_pdf(book, [page], storage, out)

        doc = fitz.open(str(out))
        assert doc.page_count == 1
        doc.close()

    def test_three_pages_produces_three_page_pdf(self, tmp_path: Path):
        storage = tmp_path / "storage"
        book = _make_book(sg=_make_style_guide())
        pages = [
            _make_page(storage, page_id="p1"),
            _make_page(storage, page_id="p2"),
            _make_page(storage, page_id="p3"),
        ]

        out = tmp_path / "out.pdf"
        export_book_pdf(book, pages, storage, out)

        doc = fitz.open(str(out))
        assert doc.page_count == 3
        doc.close()

    def test_zero_pages_raises_value_error(self, tmp_path: Path):
        storage = tmp_path / "storage"
        book = _make_book(sg=_make_style_guide())
        out = tmp_path / "out.pdf"
        with pytest.raises(ValueError, match="No pages"):
            export_book_pdf(book, [], storage, out)

    def test_page_without_artwork_skipped(self, tmp_path: Path):
        """A page with no image_path and no svg gives no usable artwork; ValueError."""
        storage = tmp_path / "storage"
        book = _make_book(sg=_make_style_guide())

        empty_page = MagicMock()
        empty_page.image_path = None
        empty_page.versions = []
        empty_page.text_layers = []

        out = tmp_path / "out.pdf"
        with pytest.raises(ValueError):
            export_book_pdf(book, [empty_page], storage, out)

    def test_pdf_page_dimensions_match_trim_plus_bleed(self, tmp_path: Path):
        """PDF page size must equal (trim + 2*bleed) × 72 pt/in."""
        storage = tmp_path / "storage"
        trim_w, trim_h, bleed = 8.5, 11.0, 0.125
        sg = _make_style_guide(trim_w=trim_w, trim_h=trim_h, bleed=bleed)
        book = _make_book(sg=sg)
        page = _make_page(storage)

        out = tmp_path / "out.pdf"
        export_book_pdf(book, [page], storage, out)

        doc = fitz.open(str(out))
        pdf_page = doc[0]
        expected_w = (trim_w + 2 * bleed) * 72
        expected_h = (trim_h + 2 * bleed) * 72
        # Allow ±1 pt tolerance for floating-point rounding
        assert abs(pdf_page.rect.width - expected_w) <= 1.5
        assert abs(pdf_page.rect.height - expected_h) <= 1.5
        doc.close()

    def test_pdf_with_text_layers_contains_text(self, tmp_path: Path):
        """PDF built from a page with a text layer must contain extractable text."""
        storage = tmp_path / "storage"
        book = _make_book(sg=_make_style_guide())
        page = _make_page(storage, with_text=True)

        out = tmp_path / "out.pdf"
        export_book_pdf(book, [page], storage, out)

        doc = fitz.open(str(out))
        pdf_page = doc[0]
        text = pdf_page.get_text()
        # "Page Title" was set in the layer; it should appear as selectable text.
        assert "Page Title" in text, (
            "Text layer content must be present as selectable PDF text"
        )
        doc.close()

    def test_output_is_valid_pdf(self, tmp_path: Path):
        storage = tmp_path / "storage"
        book = _make_book(sg=_make_style_guide())
        page = _make_page(storage)
        out = tmp_path / "out.pdf"
        export_book_pdf(book, [page], storage, out)

        raw = out.read_bytes()
        assert raw[:4] == b"%PDF", "Output must start with PDF magic bytes"

    def test_no_style_guide_uses_defaults(self, tmp_path: Path):
        """export_book_pdf must work even when book.style_guide is None."""
        storage = tmp_path / "storage"
        book = _make_book(sg=None)
        page = _make_page(storage)
        out = tmp_path / "out.pdf"
        export_book_pdf(book, [page], storage, out)
        doc = fitz.open(str(out))
        assert doc.page_count == 1
        doc.close()

    def test_raster_fallback_when_no_svg(self, tmp_path: Path):
        """When no SVG is persisted, pdf_export falls back to tracing the raster."""
        storage = tmp_path / "storage"
        book = _make_book(sg=_make_style_guide())
        page = _make_page(storage, with_svg=False)  # no SVG, has raster

        out = tmp_path / "out.pdf"
        export_book_pdf(book, [page], storage, out)

        doc = fitz.open(str(out))
        assert doc.page_count == 1
        doc.close()


# ---------------------------------------------------------------------------
# _content_box_pt() — binding gutter placement
# ---------------------------------------------------------------------------

class TestContentBoxPt:
    def test_no_gutter_matches_uniform_margin_inset(self):
        """With binding_gutter_in=0, the content box is the plain
        bleed+margin inset on all four sides (pre-gutter behavior)."""
        x0, y0, w, h = _content_box_pt(8.5, 11.0, 0.125, 0.5, 0.0, "left")
        inset = (0.125 + 0.5) * PT_PER_INCH
        page_w = (8.5 + 2 * 0.125) * PT_PER_INCH
        page_h = (11.0 + 2 * 0.125) * PT_PER_INCH
        assert x0 == pytest.approx(inset)
        assert y0 == pytest.approx(inset)
        assert w == pytest.approx(page_w - 2 * inset)
        assert h == pytest.approx(page_h - 2 * inset)

    def test_left_gutter_shifts_content_right_without_growing_page(self):
        """A left-edge gutter reserves extra space only on the left — the
        right/top/bottom edges are untouched (full bleed there), and the
        overall page size (computed separately from trim+bleed) doesn't change."""
        base_x0, base_y0, base_w, base_h = _content_box_pt(8.5, 11.0, 0.125, 0.0, 0.0, "left")
        gx0, gy0, gw, gh = _content_box_pt(8.5, 11.0, 0.125, 0.0, 0.5, "left")

        gutter_pt = 0.5 * PT_PER_INCH
        assert gx0 == pytest.approx(base_x0 + gutter_pt)
        assert gw == pytest.approx(base_w - gutter_pt)
        assert gy0 == pytest.approx(base_y0)
        assert gh == pytest.approx(base_h)

    def test_top_gutter_shifts_content_down(self):
        base_x0, base_y0, base_w, base_h = _content_box_pt(8.5, 11.0, 0.125, 0.0, 0.0, "top")
        gx0, gy0, gw, gh = _content_box_pt(8.5, 11.0, 0.125, 0.0, 0.5, "top")

        gutter_pt = 0.5 * PT_PER_INCH
        assert gy0 == pytest.approx(base_y0 + gutter_pt)
        assert gh == pytest.approx(base_h - gutter_pt)
        assert gx0 == pytest.approx(base_x0)
        assert gw == pytest.approx(base_w)
