"""
Tests for backend/app/services/svg_text.py

Covers:
- build_text_svg_elements(): correct <text> node count; hidden/empty layers omitted
- merge_text_into_svg(): text placed before </svg>; empty input unchanged
- render_text_only_svg(): produces standalone SVG with text nodes
- Text merges ABOVE the line art (appears after line-art content, before </svg>)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.svg_text import (
    build_text_svg_elements,
    merge_text_into_svg,
    render_text_only_svg,
)


# ---------------------------------------------------------------------------
# Helpers: fake TextLayer-like objects
# ---------------------------------------------------------------------------

def _make_layer(
    content: str = "Hello",
    font_name: str = "Helvetica",
    font_size_pt: int = 12,
    x_pct: float = 0.5,
    y_pct: float = 0.9,
    text_anchor: str = "middle",
    visible: bool = True,
    label: str = "title",
) -> MagicMock:
    """Return a MagicMock that quacks like a TextLayer ORM object."""
    layer = MagicMock()
    layer.content = content
    layer.font_name = font_name
    layer.font_size_pt = font_size_pt
    layer.x_pct = x_pct
    layer.y_pct = y_pct
    layer.text_anchor = text_anchor
    layer.visible = visible
    layer.label = label
    return layer


SIMPLE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" '
    'width="200" height="200" viewBox="0 0 200 200">'
    '<path d="M0 0 L200 200" stroke="black"/>'
    '</svg>'
)


# ---------------------------------------------------------------------------
# build_text_svg_elements()
# ---------------------------------------------------------------------------

class TestBuildTextSvgElements:
    def test_two_visible_layers_produce_two_text_nodes(self):
        layers = [_make_layer("Title"), _make_layer("Subtitle", y_pct=0.5)]
        fragment = build_text_svg_elements(layers, page_width=200, page_height=200)
        assert fragment.count("<text") == 2

    def test_hidden_layer_omitted(self):
        layers = [
            _make_layer("Visible", visible=True),
            _make_layer("Hidden", visible=False),
        ]
        fragment = build_text_svg_elements(layers, page_width=200, page_height=200)
        assert fragment.count("<text") == 1
        assert "Visible" in fragment
        assert "Hidden" not in fragment

    def test_empty_content_omitted(self):
        layers = [
            _make_layer("Real content"),
            _make_layer(""),          # empty content
            _make_layer("   "),       # whitespace-only
        ]
        fragment = build_text_svg_elements(layers, page_width=200, page_height=200)
        assert fragment.count("<text") == 1

    def test_no_visible_layers_returns_empty_string(self):
        layers = [_make_layer("x", visible=False)]
        fragment = build_text_svg_elements(layers, page_width=200, page_height=200)
        assert fragment == ""

    def test_empty_list_returns_empty_string(self):
        fragment = build_text_svg_elements([], page_width=200, page_height=200)
        assert fragment == ""

    def test_text_anchor_present_in_output(self):
        layer = _make_layer("Hello", text_anchor="start")
        fragment = build_text_svg_elements([layer], page_width=200, page_height=200)
        assert 'text-anchor="start"' in fragment

    def test_invalid_anchor_defaults_to_middle(self):
        layer = _make_layer("Hello", text_anchor="bogus_anchor")
        fragment = build_text_svg_elements([layer], page_width=200, page_height=200)
        assert 'text-anchor="middle"' in fragment

    def test_content_is_xml_escaped(self):
        layer = _make_layer("<script>alert(1)</script>")
        fragment = build_text_svg_elements([layer], page_width=200, page_height=200)
        assert "<script>" not in fragment
        assert "&lt;script&gt;" in fragment

    def test_font_family_mapped_for_known_fonts(self):
        layer = _make_layer("Hi", font_name="Helvetica")
        fragment = build_text_svg_elements([layer], page_width=200, page_height=200)
        assert "Helvetica" in fragment  # mapped to "Helvetica, Arial, sans-serif"
        assert "Arial" in fragment

    def test_x_y_position_computed_from_pct(self):
        """x_pct=0.5 on a 200-wide SVG should produce x="100.00"."""
        layer = _make_layer("Pos", x_pct=0.5, y_pct=0.5)
        fragment = build_text_svg_elements([layer], page_width=200, page_height=200)
        assert 'x="100.00"' in fragment
        assert 'y="100.00"' in fragment


# ---------------------------------------------------------------------------
# merge_text_into_svg()
# ---------------------------------------------------------------------------

class TestMergeTextIntoSvg:
    def test_text_appears_before_closing_svg_tag(self):
        layers = [_make_layer("Title")]
        merged = merge_text_into_svg(SIMPLE_SVG, layers)
        text_idx = merged.index("<text")
        svg_close_idx = merged.rindex("</svg>")
        assert text_idx < svg_close_idx, "Text group must appear before </svg>"

    def test_line_art_path_preserved(self):
        layers = [_make_layer("Title")]
        merged = merge_text_into_svg(SIMPLE_SVG, layers)
        assert '<path d="M0 0 L200 200"' in merged

    def test_two_text_nodes_in_merged_output(self):
        layers = [_make_layer("A"), _make_layer("B", y_pct=0.5)]
        merged = merge_text_into_svg(SIMPLE_SVG, layers)
        assert merged.count("<text") == 2

    def test_empty_layer_list_returns_unchanged_svg(self):
        merged = merge_text_into_svg(SIMPLE_SVG, [])
        assert merged == SIMPLE_SVG

    def test_all_hidden_layers_returns_unchanged_svg(self):
        layers = [_make_layer("x", visible=False)]
        merged = merge_text_into_svg(SIMPLE_SVG, layers)
        assert merged == SIMPLE_SVG

    def test_text_class_attribute_present(self):
        layers = [_make_layer("Title")]
        merged = merge_text_into_svg(SIMPLE_SVG, layers)
        assert 'class="text-layer"' in merged

    def test_svg_still_valid_after_merge(self):
        """Merged SVG must still open and close its <svg> tag."""
        layers = [_make_layer("Title")]
        merged = merge_text_into_svg(SIMPLE_SVG, layers)
        assert merged.count("<svg") == 1
        assert merged.count("</svg>") == 1

    def test_malformed_svg_without_closing_tag(self):
        """If </svg> is absent, function must not raise; text is appended."""
        malformed = '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/>'
        layers = [_make_layer("Fallback")]
        result = merge_text_into_svg(malformed, layers)
        assert "<text" in result  # text must still appear somewhere


# ---------------------------------------------------------------------------
# render_text_only_svg()
# ---------------------------------------------------------------------------

class TestRenderTextOnlySvg:
    def test_produces_standalone_svg(self):
        layers = [_make_layer("Standalone")]
        svg = render_text_only_svg(layers, page_width=200, page_height=200)
        assert svg.startswith("<svg")
        assert "</svg>" in svg

    def test_contains_text_node(self):
        layers = [_make_layer("Hello")]
        svg = render_text_only_svg(layers, page_width=200, page_height=200)
        assert "<text" in svg
        assert "Hello" in svg

    def test_two_layers_two_nodes(self):
        layers = [_make_layer("A"), _make_layer("B")]
        svg = render_text_only_svg(layers, page_width=200, page_height=200)
        assert svg.count("<text") == 2

    def test_empty_layers_produces_empty_text_group(self):
        """Empty text layers should produce an SVG with no <text> elements."""
        svg = render_text_only_svg([], page_width=200, page_height=200)
        assert "<svg" in svg
        assert "<text" not in svg
