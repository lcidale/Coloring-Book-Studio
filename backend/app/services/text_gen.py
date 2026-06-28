"""
Text-generation service.

Provides a low-level async dispatcher (``complete``) that calls either Gemini
or Claude, plus two coloring-book task wrappers built on top of it:

- ``refine_concept``  — deepen a vague page concept into a richer, drawable
  description.
- ``write_prompt``    — write the POSITIVE image-generation prompt for clean
  black-and-white line art (the caller pairs it with prompt_builder's
  UNIVERSAL_NEGATIVE).

SDKs are imported *lazily* inside dispatch branches so that importing this
module never requires ``google-genai`` or ``anthropic`` to be installed.
"""
from __future__ import annotations

import os
from typing import Optional

from app.services import text_providers


# ---------------------------------------------------------------------------
# Low-level dispatcher
# ---------------------------------------------------------------------------

async def complete(
    provider: str,
    model: str,
    system: str,
    user: str,
) -> str:
    """
    Call the given *provider* / *model* and return the text response.

    Parameters
    ----------
    provider:
        ``"gemini"`` or ``"claude"`` (case-insensitive match against the
        text_providers registry).
    model:
        A model id accepted by the provider (e.g. ``"gemini-2.5-flash"``).
    system:
        System / instruction text.
    user:
        User message text.

    Raises
    ------
    ValueError
        If the provider's API key is not configured, or the provider is
        unknown.
    """
    pid = provider.strip().lower() if provider else ""

    if pid == "gemini":
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "Gemini text provider is not configured: set GEMINI_API_KEY "
                "(or GOOGLE_API_KEY) in the environment."
            )
        from google import genai  # lazy import

        client = genai.Client(api_key=api_key)
        resp = await client.aio.models.generate_content(
            model=model,
            contents=f"{system}\n\n{user}",
        )
        # resp.text is Optional[str] (None on a safety/empty finish) — coalesce
        # so the -> str contract holds and callers never get None.
        return resp.text or ""

    if pid == "claude":
        if not text_providers.is_configured("claude"):
            raise ValueError(
                "Claude text provider is not configured: set "
                "ANTHROPIC_API_KEY in the environment."
            )
        from anthropic import AsyncAnthropic  # lazy import

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Claude text provider is not configured: set "
                "ANTHROPIC_API_KEY in the environment."
            )
        client = AsyncAnthropic(api_key=api_key)
        resp = await client.messages.create(
            model=model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(
            b.text
            for b in resp.content
            if getattr(b, "type", None) == "text"
        )

    raise ValueError(
        f"Unknown text provider {provider!r}. "
        f"Registered providers: gemini, claude."
    )


# ---------------------------------------------------------------------------
# Coloring-book task wrappers
# ---------------------------------------------------------------------------

def _style_hints(style_guide) -> str:
    """Build a concise hint string from an optional StyleGuide."""
    if style_guide is None:
        return ""
    parts = []
    lw = getattr(style_guide, "line_weight", None)
    if lw:
        parts.append(f"line weight: {lw}")
    dl = getattr(style_guide, "detail_level", None)
    if dl:
        parts.append(f"detail level: {dl}")
    motifs = getattr(style_guide, "motifs", None)
    if motifs and str(motifs).strip():
        parts.append(f"recurring motifs: {motifs.strip()}")
    return "; ".join(parts)


async def refine_concept(
    concept: str,
    style_guide,
    provider: str,
    model: str,
) -> str:
    """
    Deepen a vague page concept into a richer, more specific, drawable
    description suitable for a coloring-book page.

    The result is a concrete scene description (objects, composition, focal
    point) that remains IP-safe (no real brands, characters, or logos) and
    print-friendly.  The caller can feed this refined concept directly into
    ``write_prompt`` or into an image-generation call.

    Parameters
    ----------
    concept:
        The original (possibly brief) page idea from the user.
    style_guide:
        Optional StyleGuide object; line-weight / detail hints are folded in
        when present.
    provider, model:
        Forwarded verbatim to ``complete()``.

    Returns
    -------
    str
        The model's refined concept text.
    """
    hints = _style_hints(style_guide)
    style_note = f"\n\nStyle guide hints: {hints}" if hints else ""

    system = (
        "You are a creative director specialising in children's and adult "
        "coloring books.  Your task is to DEEPEN a page concept: take the "
        "user's idea and expand it into a richer, more specific, fully "
        "drawable scene description.\n\n"
        "Requirements:\n"
        "- Describe concrete objects, their arrangement, and a clear focal "
        "point.\n"
        "- Specify composition (foreground / midground / background elements "
        "if relevant).\n"
        "- Keep it IP-safe: no real brand names, trademarked characters, "
        "or copyrighted logos.\n"
        "- Keep it print-friendly: all elements must be drawable as clean "
        "black-and-white line art.\n"
        "- Output ONLY the refined scene description — no preamble, no "
        "bullet points, no meta-commentary."
        f"{style_note}"
    )

    return await complete(provider, model, system, concept)


async def write_prompt(
    concept: str,
    style_guide,
    provider: str,
    model: str,
) -> str:
    """
    Write the POSITIVE image-generation prompt for a coloring-book page.

    The prompt targets clean black-and-white line art with no color, no
    shading / grayscale, and no copyrighted references.  The caller is
    responsible for pairing the result with ``prompt_builder.UNIVERSAL_NEGATIVE``
    (this function does NOT return a negative prompt).

    Parameters
    ----------
    concept:
        The page concept (raw or pre-refined by ``refine_concept``).
    style_guide:
        Optional StyleGuide; line-weight / detail hints are incorporated when
        present.
    provider, model:
        Forwarded verbatim to ``complete()``.

    Returns
    -------
    str
        The positive image-generation prompt text.
    """
    hints = _style_hints(style_guide)
    style_note = f"\n\nStyle guide hints: {hints}" if hints else ""

    system = (
        "You are an expert at writing image-generation prompts for "
        "coloring-book line art.\n\n"
        "Your task: given a page concept, write ONLY the POSITIVE prompt "
        "for an image-generation model.\n\n"
        "Rules:\n"
        "- The output must be a single dense prompt string (no bullet "
        "points, no headers, no extra explanation).\n"
        "- Describe the scene in concrete visual terms.\n"
        "- Emphasise: clean black outlines only, no color, no shading, "
        "no grayscale fills, pure white background, coloring-book page.\n"
        "- Do NOT include any copyrighted character names, brand names, "
        "or trademarked imagery.\n"
        "- Do NOT include any negative prompt text (the caller handles "
        "negatives separately).\n"
        "- Output ONLY the prompt — nothing else."
        f"{style_note}"
    )

    return await complete(provider, model, system, concept)
