"""
Assembles the full AI prompt for a page by injecting the book's style guide.
The output is always: [style_prefix] + [page concept] + [style_suffix]
with a matching negative prompt.
"""
from __future__ import annotations
from app.models import StyleGuide

# These are appended to every prompt regardless of style guide
UNIVERSAL_POSITIVE = (
    "coloring book page, black and white line art only, clean outlines, "
    "no fill, no shading, no gray, pure white background, pure black lines, "
    "printable, high resolution, 300 DPI"
)

UNIVERSAL_NEGATIVE = (
    "color, grey, gray, shading, gradient, watercolor, pencil texture, "
    "noise, blur, photo, realistic, 3d render, painting, sketch marks, "
    "text, signature, watermark, copyright, frame, border"
)


def build_prompt(concept: str, style_guide: StyleGuide | None) -> tuple[str, str]:
    """
    Returns (positive_prompt, negative_prompt) for an image generation call.
    concept — the human-readable page idea
    style_guide — the book's style guide (optional, uses defaults if None)
    """
    parts = []

    if style_guide and style_guide.positive_prefix:
        parts.append(style_guide.positive_prefix.strip())

    parts.append(concept.strip())
    parts.append(UNIVERSAL_POSITIVE)

    # Line weight descriptor
    line_map = {
        "thin": "thin delicate lines, intricate detail",
        "medium": "medium line weight, balanced detail",
        "thick": "bold thick lines, strong outlines, suitable for younger colorists",
        "varied": "varied line weights, expressive outlines",
    }
    lw = (style_guide.line_weight if style_guide else "medium")
    parts.append(line_map.get(lw, "medium line weight"))

    # Detail level
    detail_map = {
        "minimal": "simple composition, lots of white space, easy to color",
        "moderate": "moderate detail, good areas to color, not overwhelming",
        "intricate": "highly detailed, intricate patterns, complex composition",
    }
    dl = (style_guide.detail_level if style_guide else "moderate")
    parts.append(detail_map.get(dl, "moderate detail"))

    # White space
    ws_map = {
        "minimal": "dense composition",
        "balanced": "balanced white space",
        "generous": "generous white space, open areas",
    }
    ws = (style_guide.white_space if style_guide else "balanced")
    parts.append(ws_map.get(ws, "balanced white space"))

    # Recurring motifs
    if style_guide and style_guide.motifs.strip():
        parts.append(f"including motifs: {style_guide.motifs.strip()}")

    if style_guide and style_guide.positive_suffix:
        parts.append(style_guide.positive_suffix.strip())

    positive = ", ".join(p for p in parts if p)

    # Negative prompt
    neg_parts = [UNIVERSAL_NEGATIVE]
    if style_guide and style_guide.negative_prompt.strip():
        neg_parts.append(style_guide.negative_prompt.strip())

    negative = ", ".join(neg_parts)

    return positive, negative
