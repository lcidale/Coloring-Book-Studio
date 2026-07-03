"""
Tests for backend/app/services/prompt_builder.py

Covers:
- UNIVERSAL_POSITIVE contains clean-line-art directives
- UNIVERSAL_NEGATIVE contains color/gray/shading exclusions
- build_prompt(): concept appears in positive; style guide fields flow through
- build_prompt() with None style_guide uses defaults
- Motifs injected when present
- Suffix/prefix injected
- Negative prompt extended by style guide additions
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.prompt_builder import (
    UNIVERSAL_NEGATIVE,
    UNIVERSAL_POSITIVE,
    build_prompt,
)


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------

class TestUniversalConstants:
    def test_positive_contains_bw_directive(self):
        pos = UNIVERSAL_POSITIVE.lower()
        assert "black and white" in pos or "black-and-white" in pos

    def test_positive_contains_no_shading(self):
        pos = UNIVERSAL_POSITIVE.lower()
        assert "no shading" in pos or "no fill" in pos

    def test_positive_contains_line_art(self):
        assert "line art" in UNIVERSAL_POSITIVE.lower() or "line drawing" in UNIVERSAL_POSITIVE.lower()

    def test_positive_mentions_300_dpi(self):
        assert "300" in UNIVERSAL_POSITIVE

    def test_positive_requires_content_fully_contained_in_frame(self):
        """Full-bleed generation (margin_in=0) means the deterministic
        crop-to-content-bbox step no longer adds a white cushion — if the AI's
        own composition draws elements touching its canvas edge, they come out
        looking cropped/bleeding off the page. The prompt must tell the model
        to keep everything contained, since post-processing can't fix this."""
        pos = UNIVERSAL_POSITIVE.lower()
        assert "bleed" in pos or "run off" in pos or "run past" in pos
        assert "contained" in pos or "whole" in pos or "complete" in pos

    def test_negative_excludes_color(self):
        assert "color" in UNIVERSAL_NEGATIVE.lower() or "colour" in UNIVERSAL_NEGATIVE.lower()

    def test_negative_excludes_gray(self):
        neg = UNIVERSAL_NEGATIVE.lower()
        assert "gray" in neg or "grey" in neg

    def test_negative_excludes_shading(self):
        assert "shading" in UNIVERSAL_NEGATIVE.lower()

    def test_negative_excludes_gradient(self):
        assert "gradient" in UNIVERSAL_NEGATIVE.lower()

    def test_negative_excludes_watermark(self):
        assert "watermark" in UNIVERSAL_NEGATIVE.lower()


# ---------------------------------------------------------------------------
# build_prompt() — no style guide
# ---------------------------------------------------------------------------

class TestBuildPromptNoStyleGuide:
    def test_returns_two_strings(self):
        pos, neg = build_prompt("a cat sitting on a mat", None)
        assert isinstance(pos, str)
        assert isinstance(neg, str)

    def test_concept_in_positive(self):
        concept = "a sleeping dragon on a mountain"
        pos, _ = build_prompt(concept, None)
        assert concept.strip() in pos

    def test_universal_positive_in_output(self):
        pos, _ = build_prompt("test concept", None)
        # At least the core B&W directive must be present
        assert "black and white" in pos.lower() or "coloring book" in pos.lower()

    def test_universal_negative_in_output(self):
        _, neg = build_prompt("test concept", None)
        assert "color" in neg.lower() or "colour" in neg.lower()

    def test_default_medium_line_weight(self):
        pos, _ = build_prompt("concept", None)
        assert "medium" in pos.lower()

    def test_default_moderate_detail(self):
        pos, _ = build_prompt("concept", None)
        assert "moderate" in pos.lower()

    def test_empty_concept_still_builds(self):
        """Empty concept must not raise."""
        pos, neg = build_prompt("", None)
        assert isinstance(pos, str)


# ---------------------------------------------------------------------------
# build_prompt() — with style guide
# ---------------------------------------------------------------------------

def _make_sg(**kwargs) -> MagicMock:
    sg = MagicMock()
    sg.positive_prefix = kwargs.get("positive_prefix", "")
    sg.positive_suffix = kwargs.get("positive_suffix", "")
    sg.negative_prompt = kwargs.get("negative_prompt", "")
    sg.line_weight = kwargs.get("line_weight", "medium")
    sg.detail_level = kwargs.get("detail_level", "moderate")
    sg.white_space = kwargs.get("white_space", "balanced")
    sg.motifs = kwargs.get("motifs", "")
    return sg


class TestBuildPromptWithStyleGuide:
    def test_positive_prefix_prepended(self):
        sg = _make_sg(positive_prefix="children's book style")
        pos, _ = build_prompt("a bunny", sg)
        assert "children's book style" in pos

    def test_positive_suffix_appended(self):
        sg = _make_sg(positive_suffix="whimsical illustrations")
        pos, _ = build_prompt("a bunny", sg)
        assert "whimsical illustrations" in pos

    def test_negative_prompt_extended(self):
        sg = _make_sg(negative_prompt="no animals")
        _, neg = build_prompt("a bunny", sg)
        assert "no animals" in neg

    def test_motifs_included(self):
        sg = _make_sg(motifs="stars and moons")
        pos, _ = build_prompt("night sky", sg)
        assert "stars and moons" in pos

    def test_empty_motifs_not_included(self):
        sg = _make_sg(motifs="  ")  # whitespace-only
        pos, _ = build_prompt("night sky", sg)
        # Should not see "including motifs" fragment
        assert "including motifs" not in pos

    def test_thin_line_weight(self):
        sg = _make_sg(line_weight="thin")
        pos, _ = build_prompt("flowers", sg)
        assert "thin" in pos.lower() or "delicate" in pos.lower()

    def test_thick_line_weight(self):
        sg = _make_sg(line_weight="thick")
        pos, _ = build_prompt("flowers", sg)
        assert "thick" in pos.lower() or "bold" in pos.lower()

    def test_intricate_detail_level(self):
        sg = _make_sg(detail_level="intricate")
        pos, _ = build_prompt("mandala", sg)
        assert "intricate" in pos.lower()

    def test_generous_white_space(self):
        sg = _make_sg(white_space="generous")
        pos, _ = build_prompt("open field", sg)
        assert "generous" in pos.lower() or "open" in pos.lower()

    def test_style_guide_negative_merged_with_universal(self):
        """The style guide's negative prompt must be combined with UNIVERSAL_NEGATIVE."""
        sg = _make_sg(negative_prompt="no background texture")
        _, neg = build_prompt("landscape", sg)
        # Universal terms must still be present
        assert "color" in neg.lower() or "colour" in neg.lower()
        # Style-guide term must also be present
        assert "no background texture" in neg

    def test_concept_position_in_prompt(self):
        """Concept should appear after any prefix but before the universal terms."""
        sg = _make_sg(positive_prefix="PREFIX")
        concept = "UNIQUE_CONCEPT_STRING"
        pos, _ = build_prompt(concept, sg)
        prefix_idx = pos.index("PREFIX")
        concept_idx = pos.index(concept)
        universal_idx = pos.index("coloring book") if "coloring book" in pos else len(pos)
        assert prefix_idx < concept_idx <= universal_idx
