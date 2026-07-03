import pytest
from app.services import image_gen


def test_mime_for_key():
    assert image_gen._mime_for_key("inspiration/x.png") == "image/png"
    assert image_gen._mime_for_key("inspiration/x.jpg") == "image/jpeg"
    assert image_gen._mime_for_key("inspiration/x.webp") == "image/webp"


def test_aspect_ratio_bucket_maps_page_size_to_nearest_supported_value():
    # 8.5x11 (the current generate_line_art default) is closer to 3:4 (0.75)
    # than any other Gemini-supported bucket.
    assert image_gen._aspect_ratio_bucket(2550, 3300) == "3:4"
    # 7.5x10 (the actual design content area after a 0.5in margin) is exactly 3:4.
    assert image_gen._aspect_ratio_bucket(2250, 3000) == "3:4"
    # Sanity: a literally square input maps to 1:1.
    assert image_gen._aspect_ratio_bucket(1000, 1000) == "1:1"
    # Landscape input maps to a landscape bucket.
    assert image_gen._aspect_ratio_bucket(1920, 1080) == "16:9"


async def test_generate_gemini_requests_the_correct_aspect_ratio(monkeypatch):
    """The root cause of 'I keep getting square images': _generate_gemini never
    told Gemini what aspect ratio to generate, so the model defaulted to 1:1
    regardless of the width/height the caller asked for."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

    from google import genai
    from google.genai import types

    captured = {}

    class FakePart:
        inline_data = type("Blob", (), {"data": b"\x89PNG\r\n\x1a\n" + b"0" * 8})()

    class FakeContent:
        parts = [FakePart()]

    class FakeCandidate:
        content = FakeContent()

    class FakeResponse:
        candidates = [FakeCandidate()]

    class FakeModels:
        async def generate_content(self, *, model, contents, config):
            captured["config"] = config
            return FakeResponse()

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        def __init__(self, api_key=None):
            self.aio = FakeAio()

    monkeypatch.setattr(genai, "Client", FakeClient)

    await image_gen._generate_gemini(
        "a fox", "", width=2550, height=3300, model="gemini-2.5-flash-image"
    )

    config = captured["config"]
    assert isinstance(config, types.GenerateContentConfig)
    assert config.image_config is not None, "must set image_config so Gemini isn't left to default to square"
    assert config.image_config.aspect_ratio == "3:4"


async def test_generate_gemini_prompt_tells_model_to_keep_content_contained(monkeypatch):
    """Full-bleed generation (margin_in=0) removed the white-padding cushion
    that used to hide elements the AI drew too close to its own canvas edge.
    Since that can no longer be fixed by post-processing, the reinforcement
    text sent on every Gemini call must ask the model to keep everything
    inside the frame — regardless of whether the page already has a saved
    prompt (this reinforcement is appended fresh on every call, unlike
    UNIVERSAL_POSITIVE which is only baked in when a prompt is first built)."""
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-test")

    from google import genai

    captured = {}

    class FakePart:
        inline_data = type("Blob", (), {"data": b"\x89PNG\r\n\x1a\n" + b"0" * 8})()

    class FakeContent:
        parts = [FakePart()]

    class FakeCandidate:
        content = FakeContent()

    class FakeResponse:
        candidates = [FakeCandidate()]

    class FakeModels:
        async def generate_content(self, *, model, contents, config):
            captured["contents"] = contents
            return FakeResponse()

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        def __init__(self, api_key=None):
            self.aio = FakeAio()

    monkeypatch.setattr(genai, "Client", FakeClient)

    await image_gen._generate_gemini(
        "a fox", "", width=2550, height=3300, model="gemini-2.5-flash-image"
    )

    prompt_sent = captured["contents"].lower()
    assert "bleed" in prompt_sent or "run off" in prompt_sent or "run past" in prompt_sent
    assert "contained" in prompt_sent or "whole" in prompt_sent or "complete" in prompt_sent


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
