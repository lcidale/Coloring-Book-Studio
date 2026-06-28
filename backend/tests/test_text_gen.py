"""
Tests for backend/app/services/text_gen.py.

SDKs are lazily imported inside dispatch branches, so we test by
monkeypatching text_gen.complete rather than the underlying SDK clients.
All tests are async (pytest-asyncio in "auto" mode per pyproject.toml).
"""
from __future__ import annotations

import pytest

import app.services.text_gen as text_gen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_async_complete(return_value: str = "stub result"):
    """Return an async stub for text_gen.complete that records its last call."""
    calls: list[dict] = []

    async def _stub(provider: str, model: str, system: str, user: str) -> str:
        calls.append(
            {"provider": provider, "model": model, "system": system, "user": user}
        )
        return return_value

    _stub.calls = calls  # type: ignore[attr-defined]
    return _stub


# ---------------------------------------------------------------------------
# refine_concept
# ---------------------------------------------------------------------------

async def test_refine_concept_calls_complete_with_given_provider_and_model(
    monkeypatch: pytest.MonkeyPatch,
):
    """refine_concept forwards provider/model to complete() and returns its text."""
    stub = _make_async_complete("A rich forest scene with a fox and mushrooms.")
    monkeypatch.setattr(text_gen, "complete", stub)

    result = await text_gen.refine_concept(
        concept="fox in forest",
        style_guide=None,
        provider="claude",
        model="claude-sonnet-4-6",
    )

    assert result == "A rich forest scene with a fox and mushrooms."
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["provider"] == "claude"
    assert call["model"] == "claude-sonnet-4-6"
    # The concept text must appear in the user message sent to complete().
    assert "fox in forest" in call["user"]


async def test_refine_concept_with_gemini_provider(monkeypatch: pytest.MonkeyPatch):
    """refine_concept works with gemini provider."""
    stub = _make_async_complete("Gemini refined concept.")
    monkeypatch.setattr(text_gen, "complete", stub)

    result = await text_gen.refine_concept(
        concept="underwater city",
        style_guide=None,
        provider="gemini",
        model="gemini-2.5-flash",
    )

    assert result == "Gemini refined concept."
    assert stub.calls[0]["provider"] == "gemini"
    assert stub.calls[0]["model"] == "gemini-2.5-flash"


async def test_refine_concept_incorporates_style_hints(monkeypatch: pytest.MonkeyPatch):
    """When a style_guide with line_weight/detail_level is given, hints appear in system."""
    stub = _make_async_complete("refined")
    monkeypatch.setattr(text_gen, "complete", stub)

    class FakeStyleGuide:
        line_weight = "thick"
        detail_level = "minimal"
        motifs = "stars"

    await text_gen.refine_concept(
        concept="castle",
        style_guide=FakeStyleGuide(),
        provider="claude",
        model="claude-sonnet-4-6",
    )

    system_text = stub.calls[0]["system"]
    assert "thick" in system_text
    assert "minimal" in system_text
    assert "stars" in system_text


# ---------------------------------------------------------------------------
# write_prompt
# ---------------------------------------------------------------------------

async def test_write_prompt_calls_complete_with_given_provider_and_model(
    monkeypatch: pytest.MonkeyPatch,
):
    """write_prompt forwards provider/model to complete() and returns its text."""
    stub = _make_async_complete("black and white coloring book, dragon flying over mountains")
    monkeypatch.setattr(text_gen, "complete", stub)

    result = await text_gen.write_prompt(
        concept="dragon over mountains",
        style_guide=None,
        provider="gemini",
        model="gemini-2.5-flash",
    )

    assert result == "black and white coloring book, dragon flying over mountains"
    assert len(stub.calls) == 1
    call = stub.calls[0]
    assert call["provider"] == "gemini"
    assert call["model"] == "gemini-2.5-flash"
    assert "dragon over mountains" in call["user"]


async def test_write_prompt_does_not_return_negative_prompt(
    monkeypatch: pytest.MonkeyPatch,
):
    """The system prompt instructs the model NOT to include negatives."""
    stub = _make_async_complete("positive only prompt")
    monkeypatch.setattr(text_gen, "complete", stub)

    await text_gen.write_prompt(
        concept="butterfly garden",
        style_guide=None,
        provider="claude",
        model="claude-sonnet-4-6",
    )

    system_text = stub.calls[0]["system"]
    # The system prompt should explicitly tell the model not to include negatives.
    assert "negative" in system_text.lower()


async def test_write_prompt_with_style_guide_hints(monkeypatch: pytest.MonkeyPatch):
    """Style guide hints appear in the system prompt for write_prompt too."""
    stub = _make_async_complete("prompt")
    monkeypatch.setattr(text_gen, "complete", stub)

    class FakeStyleGuide:
        line_weight = "thin"
        detail_level = "intricate"
        motifs = ""

    await text_gen.write_prompt(
        concept="mandala",
        style_guide=FakeStyleGuide(),
        provider="claude",
        model="claude-sonnet-4-6",
    )

    system_text = stub.calls[0]["system"]
    assert "thin" in system_text
    assert "intricate" in system_text


# ---------------------------------------------------------------------------
# complete() — unconfigured provider raises a clear error
# ---------------------------------------------------------------------------

async def test_complete_raises_for_unconfigured_claude(
    monkeypatch: pytest.MonkeyPatch,
):
    """complete() raises ValueError naming ANTHROPIC_API_KEY when Claude is unconfigured."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        await text_gen.complete(
            provider="claude",
            model="claude-sonnet-4-6",
            system="system",
            user="user",
        )


async def test_complete_raises_for_unconfigured_gemini(
    monkeypatch: pytest.MonkeyPatch,
):
    """complete() raises ValueError naming GEMINI_API_KEY when Gemini is unconfigured."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await text_gen.complete(
            provider="gemini",
            model="gemini-2.5-flash",
            system="system",
            user="user",
        )


# ---------------------------------------------------------------------------
# complete() — unknown provider
# ---------------------------------------------------------------------------

async def test_complete_raises_for_unknown_provider():
    """complete() raises ValueError for a provider not in the registry."""
    with pytest.raises(ValueError, match="Unknown text provider"):
        await text_gen.complete(
            provider="openai",
            model="gpt-4o",
            system="system",
            user="user",
        )
