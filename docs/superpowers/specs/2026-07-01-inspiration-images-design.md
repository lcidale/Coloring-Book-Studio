# Design: Inspiration Images (reference mood board)

**Date:** 2026-07-01
**Status:** Approved (brainstorming complete)
**Author:** Leslie + Claude

## Problem

Leslie has coloring-page images she created with ChatGPT that she wants to keep in the
app as **visual reference / mood-board material** while creating books. Today there is no
way to bring external images into the app: the `/inspiration` route is a placeholder, the
only file-upload endpoint is OCR (text only, no image storage), and page images can only
come from the generation pipeline. This adds a way to upload and browse reference images.

## Goals

1. Upload one or more image files (the ChatGPT images) into the app.
2. Browse them in a gallery, both app-wide and scoped to a specific book.
3. An inspiration image can be **global** (not tied to a book) or **attached to a book**,
   and can be moved between the two.
4. Add an optional short caption to an image; delete images.

## Non-goals (YAGNI — driven by "reference only" intent)

- Inspiration images are **never** included in the print PDF export.
- They do **not** feed the AI generator **in this spec**. Using an inspiration image as a
  visual reference for page generation is a separate, dependent feature — see the companion
  spec `2026-07-01-inspiration-generation-reference-design.md` (built after this one).
- No tags, folders, albums, notes-beyond-caption, or reordering. Just a flat gallery.
- No editing of the image itself (crop/rotate/etc.).

## Naming & scope conventions

- **Global** inspiration = `book_id IS NULL`.
- **Book-scoped** inspiration = `book_id = <book id>`.
- "Assign to book" sets `book_id`; "make global" clears it.

## Data model

New table `InspirationImage` (SQLAlchemy model in `backend/app/models.py`):

| Field | Type | Notes |
|-------|------|-------|
| `id` | `String` PK (uuid) | |
| `book_id` | `String` FK → `books.id`, **nullable** | `null` = global |
| `image_path` | `String` | storage key, e.g. `inspiration/<uuid>.png` |
| `caption` | `String(300)`, nullable | short optional label |
| `created_at` | `DateTime` | |

Relationship: `Book.inspiration_images` (one-to-many, `cascade="all, delete-orphan"`) so
deleting a book removes its attached inspiration rows. Because deleting a book must also
remove the underlying storage objects, `delete_book` will be extended to delete inspiration
image files too (mirroring the version-cleanup loop already there).

**Migration:** this is a brand-new *table*, which `Base.metadata.create_all()` creates on
startup for both SQLite and Postgres — no entry in `_COLUMN_MIGRATIONS` is needed (that
mechanism is only for adding *columns* to existing tables).

## Storage

Reuses `backend/app/services/storage.py` (local dev, R2 in prod). Uploaded bytes are written
via `storage.put_bytes(key, data, content_type)` under key `inspiration/<uuid>.<ext>`, where
`<ext>` is derived from the uploaded filename / content type (restricted to common image
types: png, jpg/jpeg, webp, gif). The public URL is produced by `storage.public_url(key)`.
Deletion uses `storage.delete_object(key)` (added in the prior feature).

## API — new `inspiration` router (`backend/app/routers/inspiration.py`)

Mounted under `/api/inspiration` in `app/main.py`.

| Method + path | Behavior |
|---------------|----------|
| `POST /api/inspiration` | Multipart form: one or more `files` (`list[UploadFile]`), optional `book_id`, optional `caption`. Validates content type is an allowed image type (else 400). If `book_id` is provided, 404 if that book doesn't exist. Stores each file, creates a row per file, returns the list of created dicts (201). |
| `GET /api/inspiration` | Query param `book_id`: omitted or `all` → every image; `global` → rows where `book_id IS NULL`; a book id → that book's images. Ordered by `created_at` desc. |
| `PATCH /api/inspiration/{id}` | Body `{caption?, book_id?}`. `caption` updates the label. `book_id` reassigns (a sentinel/explicit null moves it to global; a book id attaches it — 404 if that book doesn't exist). 404 if the image doesn't exist. |
| `DELETE /api/inspiration/{id}` | Deletes the storage object then the row. 204. 404 if missing. |

`book_id` reassignment semantics: `PATCH` accepts an explicit `book_id: null` to make an
image global and `book_id: "<id>"` to attach it. Because JSON `null` and "field omitted"
are indistinguishable under `exclude_none`, the PATCH handler uses Pydantic model fields
with `model_fields_set` (or a dedicated sentinel) so an explicitly-provided `null` clears
`book_id` while an omitted field leaves it unchanged. Caption uses the same set-awareness.

**Serializer** `_inspiration_dict(img)` → `{id, book_id, image_url, caption, created_at}`
where `image_url = storage.public_url(img.image_path)`.

## Frontend

**API client (`frontend/src/lib/api.ts`):**
- `interface InspirationImage { id; book_id: string | null; image_url: string; caption: string | null; created_at: string }`
- Hooks: `useInspiration(scope)` (scope = `"all" | "global" | bookId`), `useUploadInspiration()`
  (FormData multipart), `useUpdateInspiration()`, `useDeleteInspiration()`.

**Reusable component `frontend/src/features/inspiration/InspirationGallery.tsx`:**
- Props: `{ scope: "all" | "global" | string }` (a book id when embedded).
- Upload zone: drag-and-drop + file-picker, **multi-file**, image types only, with an
  optional caption applied to the batch; posts via `useUploadInspiration`.
- Grid of thumbnails (`image_url`), each with its caption, click-to-enlarge (simple lightbox
  / dialog), a delete action (confirm), and an "assign to book / make global" control that
  calls `useUpdateInspiration`.
- Empty state prompting the first upload.

**Two mount points:**
1. **`/inspiration`** — replaces `InspirationPlaceholder` in `App.tsx`. Renders
   `InspirationGallery` with a scope filter dropdown (All / Global / each book by title,
   from `useBooks()`), defaulting to All.
2. **Book detail (`BookDetailPage.tsx`)** — a new "Inspiration" section/tab rendering
   `<InspirationGallery scope={bookId} />`, so a book's references sit alongside its pages.

## Component boundaries

- `InspirationGallery` owns all gallery UI and talks only to the inspiration hooks; the two
  mount points differ only by the `scope` prop, keeping the surfaces DRY.
- Upload/list/patch/delete logic lives in the inspiration hooks in `api.ts`, mirroring the
  existing book/page/version hooks.
- The new router is self-contained; the only cross-cutting change is extending `delete_book`
  to also delete inspiration storage objects.

## Testing

- **Backend (pytest):** upload creates one row per file + writes storage objects (assert
  `storage.exists`); content-type validation rejects a non-image (400); `GET` filters by
  `all` / `global` / book id correctly; `PATCH` reassigns `book_id` (attach and explicit-null
  → global) and updates caption; `DELETE` removes row + storage object; deleting a book also
  removes its inspiration storage objects.
- **Frontend (Vitest/RTL, run with `--pool=forks --no-file-parallelism`):** gallery renders
  images for a scope; the scope filter switches the query; upload builds FormData and calls
  the endpoint; delete calls the endpoint. Run `pnpm build` (stricter `tsc -b`) before done.

## Rollout

Additive: a new table (auto-created) + a new router + additive frontend. No data migration.
No impact on generation, export, or existing endpoints beyond the `delete_book` storage
cleanup extension.
