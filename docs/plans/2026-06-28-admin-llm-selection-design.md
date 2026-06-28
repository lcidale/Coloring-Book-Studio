# Design: Admin section + per-stage LLM selection

**Date:** 2026-06-28
**Status:** Approved (design) — pending spec review

## Goal

Let the operator choose, per pipeline stage, which LLM does the work:

1. **Concept model** — refines & deepens the page concept (new capability).
2. **Prompt model** — writes the image-generation prompt from the concept (new capability).
3. **Image generator** — generates the coloring page (already implemented).

All three are global settings, surfaced in one **Admin** page in the sidebar.

## Key decisions

- **Text providers:** Claude (Anthropic) + Gemini (Google). Each picker chooses **provider + specific model**.
- **Concept refinement:** manual **"Refine with AI"** button in the Page Editor; the LLM proposes a deepened concept that the user **accepts or discards** (never silently overwrites).
- **Prompt writing:** manual **"Write with AI"** button; fills the (editable) Prompt field. **Generate uses the saved prompt as-is** (falls back to the deterministic keyword builder only when the prompt is empty). This also fixes the existing bug where Generate discarded prompt edits.
- **Defaults:** both text stages default to **Gemini 2.5 Flash** (works with the existing `GEMINI_API_KEY` — no broken first-run). Claude is selectable and marked "recommended"; it activates once `ANTHROPIC_API_KEY` is set. Image generator default stays Gemini Nano Banana.
- **Negative-prompt safety rail stays hard-coded** — the LLM writes only the positive prompt; `prompt_builder.UNIVERSAL_NEGATIVE` (+ style-guide negatives) is always applied so "no color / no shading / no copyrighted IP" can't be dropped.
- **No new page** — the existing `/settings` page already has the image picker. Rename the sidebar item and page from "Settings" → "Admin" and add the two new sections.

## Existing code this builds on

- `backend/app/services/providers.py` — image provider registry (pattern to mirror for text).
- `backend/app/services/prompt_builder.py` — `build_prompt`, `UNIVERSAL_NEGATIVE` (kept as the safety rail).
- `backend/app/services/image_gen.py` — uses `google-genai` (`from google import genai`); the text service reuses the same SDK for Gemini.
- `backend/app/routers/settings.py` — `GET /api/providers`, `GET/PUT /api/settings`, `get_or_create_settings`, `_serialize`.
- `backend/app/routers/jobs.py` (`build_prompt` at ~L147) and `generate.py` (~L57) — the generation paths that currently overwrite `page.prompt`.
- `backend/app/models.py` — `AppSettings` (has `image_provider/model`).
- `frontend/src/features/settings/SettingsPage.tsx` — the existing picker (provider radios + model dropdown + configured badge + save).
- `frontend/src/App.tsx` — sidebar nav (footer item ⚙️ "Settings" → `/settings`) and routes.
- `frontend/src/features/editor/PageEditorPage.tsx` — Concept + Prompt editors (Concept now editable).

## Architecture

### Backend

**`services/text_providers.py`** (new) — mirrors `providers.py`:
- `claude` → models `claude-sonnet-4-6` (default, "recommended"), `claude-opus-4-8`; `env_keys = ("ANTHROPIC_API_KEY",)`.
- `gemini` → models `gemini-2.5-flash` (default), `gemini-2.5-pro`; `env_keys = ("GEMINI_API_KEY", "GOOGLE_API_KEY")`.
- `DEFAULT_PROVIDER = "gemini"`. Functions: `get_registry`, `is_configured`, `is_known_provider`, `is_valid_model`, `default_model`, `model_ids` (same surface as `providers.py`).

**`services/text_gen.py`** (new) — one dispatcher + two task helpers:
- `complete(provider, model, system, user) -> str`:
  - `gemini` → `google-genai` `generate_content` (reuse `image_gen`'s key resolution).
  - `claude` → `anthropic` SDK `messages.create(model, max_tokens, system, messages=[user])` → first text block. Use `model="claude-opus-4-8"` etc. with adaptive thinking off (simple completion). New dep: `anthropic`.
- `refine_concept(concept, style_guide, provider, model) -> str` — coloring-book system prompt; returns a deepened concept.
- `write_prompt(concept, style_guide, provider, model) -> str` — returns the **positive** prompt only (line-art, IP-safe). Caller pairs it with `prompt_builder` negatives.

**`models.py`** — `AppSettings` gains `concept_provider`, `concept_model`, `prompt_provider`, `prompt_model` (string columns).

**`routers/settings.py`**:
- `get_or_create_settings` seeds the four new fields from the text registry defaults on first create.
- `_serialize` adds the four fields + `image_configured` / `concept_configured` / `prompt_configured` flags.
- `SettingsUpdate` accepts the four new optional fields, validated against `text_providers` (unknown provider/invalid model → 400; provider change with no model → default model).
- New `GET /api/text-providers` → `text_providers.get_registry()`.

**`routers/pages.py`** (or a small `text` router):
- `POST /api/pages/{id}/refine-concept` → `text_gen.refine_concept(page.concept, style_guide, settings.concept_provider, settings.concept_model)` → `{ "refined_concept": str }`. Does **not** save. 400 if provider not configured (clear message naming the missing key).
- `POST /api/pages/{id}/write-prompt` → `text_gen.write_prompt(...)` → `{ "positive": str, "negative": str }` (negative from `prompt_builder`). Does **not** save. Same 400 behavior.

**`routers/jobs.py` + `generate.py`** — generation prompt resolution:
- `positive = page.prompt if page.prompt else build_prompt(...)[0]`
- `negative = page.negative_prompt if page.negative_prompt else build_prompt(...)[1]`
- Saved/AI/hand-edited prompts become authoritative; the keyword builder is the fallback for never-generated pages.

### Frontend

**`lib/api.ts`** — add `useTextProviders()`; extend `Settings` type + `useSettings`/`useUpdateSettings` with the four new fields and configured flags; add `useRefineConcept(pageId)` and `useWritePrompt(pageId)` mutations.

**Settings → Admin** (`features/settings/SettingsPage.tsx`, `App.tsx`):
- Rename sidebar footer item and page header "Settings" → "Admin".
- Refactor the inline image form into a reusable `<ProviderModelSection title description providers settingProviderKey settingModelKey>`; render three: **Concept Model**, **Prompt Model**, **Image Generation**. Concept/Prompt use `useTextProviders`; Image uses the existing `useProviders`.
- Keep the API-keys reference section; add `ANTHROPIC_API_KEY` to it.

**Page Editor** (`features/editor/PageEditorPage.tsx`):
- Concept block: **"Refine with AI"** button → `useRefineConcept` → show proposed concept in a review box → **Accept** sets `conceptDraft` + saves (existing PATCH) / **Discard** closes.
- Prompt block: **"Write with AI"** button → `useWritePrompt` → opens the prompt editor with `promptDraft = positive` (user edits/saves via existing flow).

### Dependencies & env

- Backend: add `anthropic` to `backend/pyproject.toml`. (`google-genai` already present.)
- Env: `ANTHROPIC_API_KEY` (local + Railway) to enable Claude. Until set, Claude shows "Not Configured" and Claude-backed refine/write returns a clear 400; Gemini default works out of the box.

## Testing

- **Backend (pytest):** text registry + configured flags; settings round-trip with the four new fields + validation; `refine-concept` and `write-prompt` endpoints with `text_gen.complete` monkeypatched; generation respects a saved prompt and falls back to the builder when empty.
- **Frontend (vitest/RTL):** Admin page renders three sections and saves each; Refine button shows the proposal and Accept applies it; Write button fills the prompt. LLM/API calls mocked.

## Out of scope (YAGNI)

- No auth on the Admin page (single-operator tool).
- No per-book / per-page model overrides — global settings only.
- Negative prompt stays hard-coded (not LLM-written).
- No OpenAI / third provider.
