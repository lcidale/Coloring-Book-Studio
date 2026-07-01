# Design: Inspiration Image as a Generation Reference

**Date:** 2026-07-01
**Status:** Approved (brainstorming complete)
**Author:** Leslie + Claude
**Depends on:** `2026-07-01-inspiration-images-design.md` (Spec A — the inspiration gallery).
Build this only after Spec A ships.

## Problem

With the inspiration gallery (Spec A) in place, Leslie wants to point the AI generator at a
specific inspiration image when generating a page, so the output takes visual cues from that
reference. The active provider, Gemini "Nano Banana" (`gemini-2.5-flash-image`), accepts an
input image alongside the text prompt, so this is feasible on the path actually in use.

## Goals

1. A page can have a **sticky** reference: an inspiration image used on every regenerate
   until changed or cleared.
2. A single generation run can **override** the sticky reference with a different image
   (one-off, not remembered).
3. The reference picker offers only **eligible** images: those attached to the page's book,
   plus global ones.
4. When generating with Gemini, the referenced image is passed to the model as an input
   image; other providers ignore the reference gracefully.

## Non-goals (YAGNI)

- No per-**version** record of which reference produced each image. The prompt is already
  snapshotted per `PageVersion`; the reference lives on the page. (Addable later if wanted.)
- No multiple simultaneous references — exactly one reference image per generation.
- No reference support for replicate/fal (not configured; image-input support varies). The
  reference is silently ignored for non-Gemini providers, with a log line.
- No new "strength"/weight control for how strongly the reference is applied.

## Data model

Add one column to the existing `pages` table:

| Field | Type | Notes |
|-------|------|-------|
| `reference_image_id` | `String`, nullable, FK → `inspiration_images.id` | the page's sticky reference; `null` = none |

**Migration:** this is a *column added to an existing table*, so it is registered in
`_COLUMN_MIGRATIONS` in `backend/app/database.py` as `{"pages": {"reference_image_id": "VARCHAR"}}`.
The now-type-aware `_pg_alter_statements()` emits it correctly for Postgres; the SQLite path
already reads the map. Nullable, no default.

**Referential integrity on delete:** when an inspiration image is deleted (Spec A's
`DELETE /api/inspiration/{id}`), first set `reference_image_id = NULL` on any page that
points at it, then delete the image + its storage object. This keeps page references from
dangling and avoids FK violations on Postgres. (SQLite does not enforce FKs by default, but
the explicit null-out keeps both dialects correct.)

**Serialization:** `_page_dict` gains `reference_image_id` and a resolved
`reference_image_url` (the `public_url` of the referenced image, or `null`). Computing the
URL requires loading the referenced `InspirationImage`; the page GET/list queries add a
`selectinload`/join for it (or a lightweight lookup) so serialization stays async-safe.

## API changes

**Sticky reference — `PATCH /api/pages/{id}`:** extend `PageUpdate` with
`reference_image_id`. Setting it validates eligibility: the image must exist and be global
(`book_id IS NULL`) or belong to the page's `book_id`; otherwise 400. An explicit `null`
clears it. Because JSON `null` vs. omitted matters here, the handler uses Pydantic
`model_fields_set` (matching the pattern used for inspiration `PATCH` in Spec A) so an
explicit `null` clears while an omitted field leaves the value unchanged.

**Per-run override — generate endpoints:** both `POST /api/pages/{page_id}/generate`
(async, `jobs.py`) and the sync `POST /api/generate/{page_id}` (`generate.py`) extend their
request bodies with an optional `reference_image_id`. Resolution:
`effective_reference_id = body.reference_image_id if provided else page.reference_image_id`.
If an effective reference resolves, its `image_path` (storage key) is looked up and passed
into the pipeline; eligibility is validated the same way (400 on a foreign image).

## Generation pipeline

`generate_line_art(...)` in `backend/app/services/image_gen.py` gains an optional
`reference_image_key: Optional[str] = None`. When set:
- The **Gemini** path (`_generate_gemini`) fetches the reference bytes via
  `storage.get_bytes(reference_image_key)` and includes them as an image part in `contents`
  alongside the text prompt, using the google-genai `types.Part.from_bytes(data=..., mime_type=...)`
  (mime inferred from the key extension). The existing line-art positive/negative constraints
  are unchanged, so the output is still forced to pure B&W line art while taking visual cues
  from the reference.
- **replicate / fal** paths ignore `reference_image_key` and log a single info line that a
  reference was supplied but the provider does not support it.

The `jobs.py` `_generate` and `generate.py` handlers thread `reference_image_key` through to
`generate_line_art`. The shared `record_version` helper is unchanged (no per-version
reference persistence — see non-goals).

## Frontend

**API client (`frontend/src/lib/api.ts`):**
- `Page` gains `reference_image_id: string | null` and `reference_image_url: string | null`.
- `useUpdatePage` accepts `reference_image_id` (set/clear).
- `useGeneratePage` options gain an optional `reference_image_id` (per-run override).

**Page editor (`PageEditorPage.tsx`):**
- A **"Reference image"** control near the generate action: shows the current sticky
  reference thumbnail (from `reference_image_url`) if set, with **Change** / **Clear**.
  Change opens a picker listing eligible images — this book's inspiration + global — sourced
  from the Spec A hook `useInspiration(bookId)` merged with `useInspiration("global")` (or a
  single call to the eligibility-aware endpoint). Selecting one `PATCH`es the page's
  `reference_image_id`.
- On the Generate action, an optional **"use a different reference this time"** control that
  sets a one-run override passed into `useGeneratePage`; if untouched, the sticky reference
  is used automatically by the backend.

## Component boundaries

- The reference **picker** is a small component reused for both the sticky control and the
  per-run override; it takes the eligible-image list and an `onSelect` callback.
- Eligibility validation lives in one backend helper (`_eligible_reference_or_400(image_id,
  page, db)`) reused by the page `PATCH` and both generate endpoints.
- The pipeline change is isolated to `generate_line_art` + `_generate_gemini`; callers only
  pass an extra optional key.

## Testing

- **Backend (pytest):**
  - `_generate_gemini` includes the reference image as an input part when a key is given
    (assert via a mocked genai client capturing `contents`); no image part when none.
  - Sticky `reference_image_id` round-trips through `PATCH`/`GET`; setting a foreign book's
    image → 400; explicit `null` clears it.
  - Generate with a body override uses the override; without it, uses the page's sticky ref;
    a foreign override → 400. (Use the conftest `client` fixture; generation is faked by the
    fixture's `generate_line_art` monkeypatch — extend/monkeypatch so the reference key is
    observable, or unit-test `_generate_gemini` directly with a mocked client.)
  - Deleting an inspiration image nulls `reference_image_id` on pages that referenced it.
- **Frontend (Vitest/RTL, `--pool=forks --no-file-parallelism`):** the reference control
  renders the sticky thumbnail; the picker lists eligible images; selecting one calls
  `useUpdatePage` with `reference_image_id`; the generate override passes the id. Run
  `pnpm build` (strict `tsc -b`) before done.

## Rollout

Additive: one nullable column (idempotent startup migration for SQLite + Neon), optional
request-body fields, an optional pipeline argument, and additive UI. Existing generations
that pass no reference behave exactly as before. No data migration.
