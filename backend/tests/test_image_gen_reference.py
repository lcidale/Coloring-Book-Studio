import pytest
from app.services import image_gen

pytestmark = pytest.mark.asyncio


def test_mime_for_key():
    assert image_gen._mime_for_key("inspiration/x.png") == "image/png"
    assert image_gen._mime_for_key("inspiration/x.jpg") == "image/jpeg"
    assert image_gen._mime_for_key("inspiration/x.webp") == "image/webp"


async def test_generate_line_art_passes_reference_to_gemini(monkeypatch, tmp_path):
    # storage.get_bytes returns fake reference bytes; capture what _generate_gemini receives
    from app.services import storage
    monkeypatch.setattr(storage, "STORAGE_BACKEND", "local")
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    monkeypatch.setattr(image_gen, "STORAGE_DIR", tmp_path)
    storage.put_bytes("inspiration/ref.png", b"REFBYTES")

    captured = {}

    async def fake_gemini(pos, neg, w, h, model, reference=None):
        captured["reference"] = reference
        return b"\x89PNG\r\n\x1a\n" + b"0" * 8  # fake png bytes

    monkeypatch.setattr(image_gen, "_generate_gemini", fake_gemini)

    async def fake_resolve(provider, model, db):
        return "gemini", "gemini-2.5-flash-image"
    monkeypatch.setattr(image_gen, "_resolve_provider_model", fake_resolve)

    await image_gen.generate_line_art(
        positive_prompt="p", negative_prompt="n", book_id="b", page_id="pg",
        version=1, reference_image_key="inspiration/ref.png",
    )
    assert captured["reference"] == (b"REFBYTES", "image/png")
