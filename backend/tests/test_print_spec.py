"""
Tests for print_spec: computing generation canvas size and border width
(in pixels) from a book's style guide, with sane defaults when unset.
"""
from __future__ import annotations

from app.models import StyleGuide
from app.services.print_spec import target_border_px, target_px_dimensions


class TestTargetPxDimensions:
    def test_defaults_to_letter_size_at_300_dpi_when_no_style_guide(self):
        assert target_px_dimensions(None) == (2550, 3300)

    def test_scales_with_style_guide_trim_and_dpi(self):
        sg = StyleGuide(trim_width_in=6.0, trim_height_in=9.0, target_dpi=150)
        assert target_px_dimensions(sg) == (900, 1350)


class TestTargetBorderPx:
    def test_defaults_to_half_inch_at_given_dpi_when_no_style_guide(self):
        assert target_border_px(None, dpi=300) == 150

    def test_scales_with_style_guide_margin(self):
        sg = StyleGuide(margin_in=0.25)
        assert target_border_px(sg, dpi=300) == 75
