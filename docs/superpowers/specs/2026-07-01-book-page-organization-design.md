# Design: Book & Page Organization + Version History

**Date:** 2026-07-01
**Status:** Approved (brainstorming complete)
**Author:** Leslie + Claude

## Problem

Leslie wants to organize coloring-book work by book, name and reorder pages within a
book, and keep every iteration of a page along with the prompt that produced it.

Investigation found that the **backend already models all of this**. The gap is entirely
in the **frontend UI**: the capabilities exist in the database and API but are not surfaced.

Confirmed state before this work:

- `Book` has `title` + `PATCH /api/books/{id}` — but no rename/delete UI.
- `Page` has an explicit `sort_order` + generic `PATCH /api/pages/{id}` — but no reorder or
  delete UI, and only a long `concept` brief (no short name).
- `PageVersion` already captures `version_num`, `image_path`, `svg_path`, `prompt`, `notes`
  on every regenerate; old versions are never deleted — but the frontend never fetches them,
  and there is no view/copy/restore/label/delete UI.

## Goals

1. Rename and delete a book from the UI.
2. Give each page a short **title**, displayed with an auto page number derived from order.
3. Reorder pages by drag-and-drop; delete pages.
4. Browse every version of a page with its exact prompt, and: copy a prompt, restore a
   version as current, label/annotate a version, delete a version.

## Non-goals (YAGNI)

- Manual reordering of the book library itself (books stay sorted by `updated_at`).
- Manual version snapshots outside of the existing regenerate flow.
- Branching/merging of version trees. Versions remain a flat sequential list per page.
- Renaming books changing anything about their pages.

## Naming & numbering scheme (conventions)

- **Book** = the project, identified by `emoji` + `title` (e.g. "📖 Woodland Friends").
  Renaming a book never touches its pages.
- **Page display name** = `p.NN — Title`.
  - `NN` is **derived from order, not stored**: the 1-based position of the page within its
    book's `sort_order`, zero-padded to two digits (`p.03`). Reordering instantly renumbers
    all pages.
  - `Title` is the new short field. If blank, fall back to the first line / first ~40 chars
    of `concept`.
- **Version** = `v1, v2, v3…` — `version_num` is sequential, immutable, and never reused.
  - The **current** version is the one whose `image_path` matches the page's live `image_path`.
  - **Restore** makes an older version current by copying its image + prompt + metadata onto
    the page. It does **not** renumber or delete anything — history stays intact.

## Backend changes

All additive. Follows the existing no-Alembic pattern: SQLAlchemy models are the source of
truth, `create_all()` handles fresh DBs, and idempotent entries in `_COLUMN_MIGRATIONS`
(`backend/app/database.py`) add columns to existing SQLite and Postgres databases on startup.

### Schema

| Model | Field | Type | Notes |
|-------|-------|------|-------|
| `Page` | `title` | `String(200)`, nullable | Short page name. Added to Create/Update/Out schemas. |
| `PageVersion` | `label` | `String(120)`, nullable | Short annotation chip. `notes` (existing) stays for longer text. |
| `PageVersion` | `dpi` | `Integer`, nullable | Print metadata captured at generation time. |
| `PageVersion` | `width_px` | `Integer`, nullable | |
| `PageVersion` | `height_px` | `Integer`, nullable | |
| `PageVersion` | `is_pure_bw` | `Boolean`, nullable | |

The four `PageVersion` print-metadata columns make **Restore** faithful for print. They are
populated at generation time going forward (the values are already computed during
`analyse()`); versions created before this change show them as unknown/null.

### Endpoints

| Method + path | Behavior |
|---------------|----------|
| `POST /api/pages/{page_id}/versions/{version_id}/restore` | Copies the version's `image_path`, `prompt`, and the four print-metadata fields onto the page as current. Returns the updated page. |
| `PATCH /api/pages/{page_id}/versions/{version_id}` | Updates `label` and/or `notes`. |
| `DELETE /api/pages/{page_id}/versions/{version_id}` | Deletes the version row + its storage object (image, and svg if present). **Blocked (409) if it is the current version** — the user must restore another version first, so the page's live image is never orphaned. |
| `PATCH /api/pages/book/{book_id}/reorder` | Body: ordered list of page ids. Rewrites `sort_order` contiguously (0..n-1) in a single request. Avoids issuing N PATCHes on every drag. |

Book delete (`DELETE /api/books/{id}`) and page delete (`DELETE /api/pages/{id}`) already
exist and cascade-delete children; they only need frontend wiring.

The generation flow (`generate.py`, `jobs.py`) is extended so that when it creates a
`PageVersion`, it also records `dpi`, `width_px`, `height_px`, and `is_pure_bw` from the
`analyse()` result.

## Frontend changes

### a. Book library — `frontend/src/features/books/BooksPage.tsx`

- Each book card gets a `⋯` dropdown menu:
  - **Rename** → opens a dialog reusing the create-book form, pre-filled with current values,
    saving via the existing `useUpdateBook()` hook.
  - **Delete** → confirmation dialog, then `useDeleteBook()`.

### b. Book detail — `frontend/src/features/books/BookDetailPage.tsx`

- The page grid becomes **drag-to-reorder** using `@dnd-kit`. On drop, the new order is sent
  once via `useReorderPages()` (the bulk endpoint); numbers relabel live.
- Cards display `p.NN — Title` (number derived from position, title with concept fallback).
- Each page card gets a `⋯` menu:
  - **Rename** → inline edit of the page `title`.
  - **Delete** → confirmation dialog, then `useDeletePage()`.

### c. Page editor — `frontend/src/features/editor/PageEditorPage.tsx`

- A short **Title** field at the top, saved via the extended `useUpdatePage()`.
- A new **Versions panel** beside the image:
  - Thumbnails of every iteration, newest first; the current version is badged.
  - Each row exposes: the exact `prompt` (expandable) with a **Copy prompt** button that
    loads it into the editor's prompt field for regeneration; an editable **label**;
    **Restore as current**; and **Delete** (disabled for the current version).

### d. API client — `frontend/src/lib/api.ts`

- Add a `PageVersion` TypeScript interface and a `versions: PageVersion[]` field on `Page`
  (the existing `GET /api/pages/{id}` already returns versions).
- New/extended hooks: `useDeleteBook`, `useDeletePage`, `useReorderPages`,
  `useRestoreVersion`, `useUpdateVersion`, `useDeleteVersion`; extend `useUpdatePage` to
  accept `title` and `sort_order`.

### e. New shadcn/ui components

- `dropdown-menu` (Radix) for the `⋯` menus.
- `alert-dialog` (Radix) for delete confirmations.
- `@dnd-kit/core` + `@dnd-kit/sortable` for drag-to-reorder.

## Component boundaries

- **Reorder** is isolated behind the bulk `reorder` endpoint and a single `useReorderPages`
  hook — the drag UI never mutates individual `sort_order` values directly.
- **Version actions** live in a self-contained `VersionsPanel` component that takes a
  `pageId` + `versions[]` and calls the version hooks; the editor doesn't know their internals.
- **Rename/delete** for books and pages reuse existing hooks (`useUpdateBook`,
  `useDeleteBook`, `useDeletePage`) so mutation logic stays in one place (`api.ts`).

## Testing

- **Backend (pytest):** restore copies image + prompt + metadata correctly; delete of the
  current version returns 409; delete of a non-current version removes row + storage object;
  reorder rewrites `sort_order` to contiguous 0..n-1; label/notes patch persists; new
  `Page.title` round-trips through create/update/get.
- **Frontend (Vitest/RTL):** reorder handler computes the new order and calls the bulk hook
  once; VersionsPanel actions (copy prompt, restore, label edit, delete-disabled-for-current);
  book rename dialog pre-fills and saves; delete confirmation flows.
  Run with `--pool=forks --no-file-parallelism` (known worker-timeout flake workaround).

## Rollout

Additive schema + endpoints deploy safely (column migrations are idempotent; existing rows
get null for new fields). No data migration required. Existing versions simply display
unknown print-metadata until regenerated.
