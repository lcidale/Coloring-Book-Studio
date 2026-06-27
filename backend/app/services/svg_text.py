"""
Editable vector text layers.

Builds an SVG ``<text>`` layer from a page's TextLayer rows and merges it ABOVE
the line-art SVG. Text always stays real, selectable SVG ``<text>`` — it is never
rasterized into the AI image.
"""
from __future__ import annotations

import re
from xml.sax.saxutils import escape

from app.models import TextLayer

# Map our stored PIL/PDF font names to web-safe SVG font families so the text
# renders consistently across viewers and PyMuPDF.
_FONT_MAP = {
    "Helvetica": "Helvetica, Arial, sans-serif",
    "Arial": "Arial, Helvetica, sans-serif",
    "Times": "'Times New Roman', Times, serif",
    "Times New Roman": "'Times New Roman', Times, serif",
    "Courier": "'Courier New', Courier, monospace",
}

_VALID_ANCHORS = {"start", "middle", "end"}


def _svg_dimensions(svg: str) -> tuple[float, float]:
    """Extract (width, height) in user units from an SVG string.

    Prefers the viewBox; falls back to width/height attributes; finally to a
    sensible US-letter-at-300-DPI default so positioning never divides by zero.
    """
    vb = re.search(r'viewBox\s*=\s*["\']\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)', svg)
    if vb:
        return float(vb.group(3)), float(vb.group(4))

    w = re.search(r'\bwidth\s*=\s*["\']([\d.]+)', svg)
    h = re.search(r'\bheight\s*=\s*["\']([\d.]+)', svg)
    if w and h:
        return float(w.group(1)), float(h.group(1))

    return 2550.0, 3300.0


def build_text_svg_elements(
    text_layers: list[TextLayer],
    page_width: float,
    page_height: float,
    page_height_pt: float | None = None,
) -> str:
    """
    Return an SVG fragment (a ``<g>`` group of ``<text>`` nodes) for the visible
    text layers, positioned in the page's user-unit coordinate space.

    Font size is interpreted in points relative to the *physical* page height
    (``page_height_pt``, e.g. 11in = 792pt) and mapped into the SVG's own
    coordinate units, so text stays correctly proportioned no matter what raw
    pixel dimensions the traced SVG happens to use. When ``page_height_pt`` is
    unknown, the SVG height is assumed to already be in points.
    """
    # Units of SVG coordinate space per typographic point.
    units_per_pt = (page_height / page_height_pt) if page_height_pt else 1.0

    elements: list[str] = []
    for layer in text_layers:
        if not layer.visible or not (layer.content or "").strip():
            continue

        x = layer.x_pct * page_width
        y = layer.y_pct * page_height
        font_units = layer.font_size_pt * units_per_pt
        family = _FONT_MAP.get(layer.font_name, f"{layer.font_name}, sans-serif")
        anchor = layer.text_anchor if layer.text_anchor in _VALID_ANCHORS else "middle"

        elements.append(
            f'<text x="{x:.2f}" y="{y:.2f}" '
            f'font-family="{escape(family, {chr(34): "&quot;"})}" '
            f'font-size="{font_units:.2f}" '
            f'text-anchor="{anchor}" '
            f'fill="#000000">{escape(layer.content)}</text>'
        )

    if not elements:
        return ""
    return '<g class="text-layer">\n  ' + "\n  ".join(elements) + "\n</g>"


def merge_text_into_svg(
    line_art_svg: str,
    text_layers: list[TextLayer],
    page_height_pt: float | None = None,
) -> str:
    """
    Merge a text layer ABOVE the line-art SVG.

    The line-art markup is preserved verbatim; the ``<text>`` group is inserted
    just before the closing ``</svg>`` so it paints on top of the art. If there
    are no visible text layers, the line-art SVG is returned unchanged.

    ``page_height_pt`` is the physical page height in points (e.g. trim height in
    inches × 72); font sizes are scaled into the SVG's coordinate space relative
    to it.
    """
    page_w, page_h = _svg_dimensions(line_art_svg)
    fragment = build_text_svg_elements(
        text_layers, page_w, page_h, page_height_pt=page_height_pt
    )
    if not fragment:
        return line_art_svg

    idx = line_art_svg.rfind("</svg>")
    if idx == -1:
        # Malformed input — append a wrapper rather than lose the text.
        return line_art_svg + fragment
    return line_art_svg[:idx] + fragment + "\n" + line_art_svg[idx:]


def render_text_only_svg(
    text_layers: list[TextLayer],
    page_width: float,
    page_height: float,
    page_height_pt: float | None = None,
) -> str:
    """Standalone SVG document containing only the text layer (for previews)."""
    fragment = build_text_svg_elements(
        text_layers, page_width, page_height, page_height_pt=page_height_pt
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{page_width:.2f}" height="{page_height:.2f}" '
        f'viewBox="0 0 {page_width:.2f} {page_height:.2f}">\n'
        f'{fragment}\n</svg>'
    )
