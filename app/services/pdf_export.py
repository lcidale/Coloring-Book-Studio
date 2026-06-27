"""
Assembles approved pages into a print-ready PDF.
Text layers are composited at export time — never embedded in the AI image.
"""
from __future__ import annotations
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

from app.models import Book, Page, TextLayer, StyleGuide


def export_book_pdf(
    book: Book,
    pages: list[Page],
    storage_dir: Path,
    out_path: Path,
) -> Path:
    """
    Build a print-ready PDF from approved pages.
    Text layers are drawn on top of each page image before embedding in the PDF.
    """
    sg: StyleGuide | None = book.style_guide
    trim_w = sg.trim_width_in if sg else 8.5
    trim_h = sg.trim_height_in if sg else 11.0
    bleed = sg.bleed_in if sg else 0.125
    dpi = sg.target_dpi if sg else 300

    page_w_pt = (trim_w + 2 * bleed) * 72  # points (72 pt/inch)
    page_h_pt = (trim_h + 2 * bleed) * 72

    c = rl_canvas.Canvas(str(out_path), pagesize=(page_w_pt, page_h_pt))

    for page in pages:
        if not page.image_path:
            continue

        img_path = storage_dir / page.image_path
        composited = _composite_text(img_path, page.text_layers, dpi)

        # Write composited image to a temp path
        tmp_path = img_path.parent / "_export_tmp.png"
        composited.save(tmp_path, format="PNG", dpi=(dpi, dpi))

        c.drawImage(str(tmp_path), 0, 0, width=page_w_pt, height=page_h_pt)
        c.showPage()

        tmp_path.unlink(missing_ok=True)

    c.save()
    return out_path


def _composite_text(
    image_path: Path,
    text_layers: list[TextLayer],
    dpi: int,
) -> Image.Image:
    """Draw text layers onto the image. Returns the composited PIL Image."""
    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for layer in text_layers:
        if not layer.visible or not layer.content.strip():
            continue

        font_size_px = int(layer.font_size_pt * dpi / 72)
        try:
            font = ImageFont.truetype(f"{layer.font_name}.ttf", font_size_px)
        except (IOError, OSError):
            font = ImageFont.load_default()

        x = int(layer.x_pct * w)
        y = int(layer.y_pct * h)

        # Center text horizontally on x
        bbox = draw.textbbox((0, 0), layer.content, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw // 2, y), layer.content, fill=0, font=font)

    return img
