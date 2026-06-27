"""
Tests for backend/app/services/vectorize.py

Covers:
- trace_to_svg(): synthetic B&W image -> SVG containing <path>, no <image> tags
- svg_path_count(): counting <path> elements
- render_svg_to_pdf(): produces a non-empty PDF bytes blob
- render_svg_to_png(): produces a non-empty PNG at the requested scale
- vectorize_page(): convenience pipeline produces SVG and optional preview PNG
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.vectorize import (
    render_svg_to_pdf,
    render_svg_to_png,
    svg_path_count,
    trace_to_svg,
    vectorize_page,
)
from tests.conftest import make_pure_bw_png


# ---------------------------------------------------------------------------
# trace_to_svg()
# ---------------------------------------------------------------------------

class TestTraceToSvg:
    def test_produces_svg_file(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        dst = tmp_path / "art.svg"
        result = trace_to_svg(src, dst)
        assert result == dst
        assert dst.exists()
        assert dst.stat().st_size > 0

    def test_svg_contains_path_elements(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        dst = tmp_path / "art.svg"
        trace_to_svg(src, dst)
        svg_text = dst.read_text(encoding="utf-8")
        assert "<path" in svg_text, "Traced SVG must contain at least one <path> element"

    def test_svg_has_no_embedded_raster(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        dst = tmp_path / "art.svg"
        trace_to_svg(src, dst)
        svg_text = dst.read_text(encoding="utf-8")
        assert "<image" not in svg_text.lower(), (
            "Traced SVG must not contain embedded raster <image> tags"
        )

    def test_svg_is_valid_xml_opening(self, tmp_path: Path):
        """SVG must open with an <svg tag."""
        src = make_pure_bw_png(tmp_path / "art.png")
        dst = tmp_path / "art.svg"
        trace_to_svg(src, dst)
        text = dst.read_text(encoding="utf-8").strip()
        assert "<svg" in text[:500], "Output must start with an SVG element"

    def test_creates_parent_dirs(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        dst = tmp_path / "nested" / "deep" / "art.svg"
        trace_to_svg(src, dst)
        assert dst.exists()


# ---------------------------------------------------------------------------
# svg_path_count()
# ---------------------------------------------------------------------------

class TestSvgPathCount:
    def test_counts_paths(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        dst = tmp_path / "art.svg"
        trace_to_svg(src, dst)
        count = svg_path_count(dst)
        assert count >= 1, "Traced image with content must have at least 1 <path>"

    def test_empty_svg_returns_zero(self, tmp_path: Path):
        empty = tmp_path / "empty.svg"
        empty.write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>')
        assert svg_path_count(empty) == 0


# ---------------------------------------------------------------------------
# render_svg_to_pdf()
# ---------------------------------------------------------------------------

MINIMAL_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
    '<rect x="10" y="10" width="180" height="180" fill="black"/>'
    '</svg>'
)


class TestRenderSvgToPdf:
    def test_produces_pdf_bytes(self, tmp_path: Path):
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(MINIMAL_SVG, encoding="utf-8")
        pdf_file = tmp_path / "out.pdf"
        result = render_svg_to_pdf(svg_file, pdf_file)
        assert result == pdf_file
        assert pdf_file.exists()
        data = pdf_file.read_bytes()
        assert len(data) > 100, "PDF output must be non-empty"
        assert data[:4] == b"%PDF", "Output must be a valid PDF (starts with %PDF)"

    def test_from_traced_svg(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        svg = tmp_path / "art.svg"
        trace_to_svg(src, svg)
        pdf = tmp_path / "art.pdf"
        render_svg_to_pdf(svg, pdf)
        assert pdf.read_bytes()[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# render_svg_to_png()
# ---------------------------------------------------------------------------

class TestRenderSvgToPng:
    def test_produces_png_file(self, tmp_path: Path):
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(MINIMAL_SVG, encoding="utf-8")
        png_file = tmp_path / "out.png"
        result = render_svg_to_png(svg_file, png_file, dpi=72)
        assert result == png_file
        assert png_file.exists()
        assert png_file.stat().st_size > 0

    def test_higher_dpi_gives_larger_image(self, tmp_path: Path):
        """Rendering at 300 DPI must produce a larger PNG than at 72 DPI."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text(MINIMAL_SVG, encoding="utf-8")

        lo = tmp_path / "lo.png"
        hi = tmp_path / "hi.png"
        render_svg_to_png(svg_file, lo, dpi=72)
        render_svg_to_png(svg_file, hi, dpi=300)

        from PIL import Image
        lo_img = Image.open(lo)
        hi_img = Image.open(hi)
        assert hi_img.width > lo_img.width, (
            "300 DPI render should be wider than 72 DPI render"
        )

    def test_from_traced_svg(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        svg = tmp_path / "art.svg"
        trace_to_svg(src, svg)
        png = tmp_path / "preview.png"
        render_svg_to_png(svg, png, dpi=150)
        assert png.stat().st_size > 0


# ---------------------------------------------------------------------------
# vectorize_page() convenience wrapper
# ---------------------------------------------------------------------------

class TestVectorizePage:
    def test_returns_svg_path(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        svg = tmp_path / "art.svg"
        result = vectorize_page(src, svg)
        assert result == svg
        assert svg.exists()

    def test_optional_preview_png_created(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        svg = tmp_path / "art.svg"
        preview = tmp_path / "preview.png"
        vectorize_page(src, svg, preview_png_path=preview, preview_dpi=72)
        assert preview.exists()
        assert preview.stat().st_size > 0

    def test_no_preview_when_not_requested(self, tmp_path: Path):
        src = make_pure_bw_png(tmp_path / "art.png")
        svg = tmp_path / "art.svg"
        preview = tmp_path / "preview.png"
        vectorize_page(src, svg)  # preview_png_path not provided
        assert not preview.exists()
