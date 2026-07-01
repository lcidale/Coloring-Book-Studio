# Inspiration Images (reference mood board) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user upload external image files (e.g. ChatGPT coloring pages) and browse them as reference/mood-board material, both app-wide and scoped to a specific book.

**Architecture:** A new `InspirationImage` table (nullable `book_id`: null = global, set = book-scoped) + a self-contained `inspiration` FastAPI router (upload/list/patch/delete) reusing the existing `storage` service, plus a reusable React `InspirationGallery` component mounted on the `/inspiration` page (with a scope filter) and as a section on the book detail page.

**Tech Stack:** FastAPI + async SQLAlchemy + Pydantic (Python 3.12/uv). React 19 + Vite + Tailwind 4 + shadcn/ui + TanStack Query. Multipart uploads via `python-multipart` (already a dep). Tests: pytest, Vitest/RTL.

## Global Constraints

- **No Alembic.** `InspirationImage` is a brand-new *table*, created automatically by `Base.metadata.create_all()` on startup (SQLite + Postgres) — do NOT add it to `_COLUMN_MIGRATIONS` (that mechanism is only for adding columns to existing tables).
- **Backend tests:** `export PATH="$HOME/.local/bin:$HOME/.local/node-v24.18.0-darwin-arm64/bin:$PATH"` then `uv run --directory backend pytest`. Use the existing conftest `client` fixture (isolated DB + tmp storage + faked generation). `asyncio_mode="auto"`.
- **Frontend tests:** `pnpm --dir frontend test --run --pool=forks --no-file-parallelism` (worker-timeout workaround). Tests live in `__tests__/` dirs. Vitest `globals: true`, jsdom, `@`→`src`.
- **Frontend "green" = the build passes,** not just `tsc --noEmit`: run `pnpm --dir frontend build` (its `tsc -b` is stricter — `noUnusedLocals`, includes tests). Remove unused imports; cast incomplete test mocks via `as unknown as <T>`.
- **Storage keys:** inspiration files live under `inspiration/<uuid>.<ext>`. Read/write via `app.services.storage` (`put_bytes`, `get_bytes`, `exists`, `public_url`, `delete_object`). Serialize `image_path` to a URL with `storage.public_url(key)`.
- **Reference-only:** inspiration images never enter the print PDF and never feed the generator in THIS plan (that is a separate plan).
- **Allowed image types:** `image/png`→`png`, `image/jpeg`→`jpg`, `image/webp`→`webp`, `image/gif`→`gif`. Reject anything else with 400.

### Shared contract (names used across tasks — do not drift)

- Model: `InspirationImage` (`backend/app/models.py`) — `id`, `book_id` (nullable FK), `image_path`, `caption` (nullable), `created_at`; relationship `Book.inspiration_images` (cascade all, delete-orphan).
- Router (`backend/app/routers/inspiration.py`), mounted at `/api/inspiration`:
  - `POST /api/inspiration` (multipart: `files: list[UploadFile]`, `book_id: Form(None)`, `caption: Form(None)`) → 201, list of dicts
  - `GET /api/inspiration?book_id=<all|global|BOOKID>` → list of dicts (newest first)
  - `PATCH /api/inspiration/{id}` (body `InspirationUpdate{caption?, book_id?}`, set-aware) → dict
  - `DELETE /api/inspiration/{id}` → 204
  - serializer `_dict(img)` → `{id, book_id, image_url, caption, created_at}`
- Frontend (`frontend/src/lib/api.ts`): `interface InspirationImage {id; book_id: string|null; image_url: string|null; caption: string|null; created_at: string}`; hooks `useInspiration(scope)`, `useUploadInspiration()`, `useUpdateInspiration()`, `useDeleteInspiration()`.
- Component: `frontend/src/features/inspiration/InspirationGallery.tsx` — prop `{ scope: string }` (`"all" | "global" | bookId`).
- Page: `frontend/src/features/inspiration/InspirationPage.tsx` — mounted at `/inspiration`.

---

## Task 1: `InspirationImage` model + Book relationship

**Files:**
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_inspiration_model.py`

**Interfaces:**
- Produces: `InspirationImage` model; `Book.inspiration_images` relationship.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_inspiration_model.py
from app.models import Book, InspirationImage


async def test_inspiration_row_roundtrips_and_book_relationship(db_session):
    book = Book(title="B")
    db_session.add(book)
    await db_session.flush()
    img = InspirationImage(book_id=book.id, image_path="inspiration/x.png", caption="hi")
    glob = InspirationImage(book_id=None, image_path="inspiration/y.png")
    db_session.add_all([img, glob])
    await db_session.commit()

    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    loaded = (await db_session.execute(
        select(Book).options(selectinload(Book.inspiration_images)).where(Book.id == book.id)
    )).scalar_one()
    assert [i.image_path for i in loaded.inspiration_images] == ["inspiration/x.png"]
    assert glob.book_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_inspiration_model.py -v`
Expected: FAIL — `cannot import name 'InspirationImage'`.

- [ ] **Step 3: Add the model + relationship**

In `backend/app/models.py`, add the relationship to `class Book` (after the `pages` relationship):

```python
    inspiration_images: Mapped[List["InspirationImage"]] = relationship(
        "InspirationImage", back_populates="book", cascade="all, delete-orphan"
    )
```

Add the model (place it after `PageVersion`):

```python
class InspirationImage(Base):
    """Reference / mood-board image. Global when book_id is NULL."""
    __tablename__ = "inspiration_images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    book_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("books.id"), nullable=True)
    image_path: Mapped[str] = mapped_column(String)          # storage key: inspiration/<uuid>.<ext>
    caption: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    book: Mapped[Optional["Book"]] = relationship("Book", back_populates="inspiration_images")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --directory backend pytest tests/test_inspiration_model.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_inspiration_model.py
git commit -m "feat(db): InspirationImage model + Book.inspiration_images relationship"
```

---

## Task 2: Inspiration router — upload + list, mounted in main.py

**Files:**
- Create: `backend/app/routers/inspiration.py`
- Modify: `backend/app/main.py:14,44` (import + include_router)
- Test: `backend/tests/test_inspiration_api.py`

**Interfaces:**
- Consumes: `InspirationImage` (Task 1); `storage.put_bytes/public_url`.
- Produces: `POST /api/inspiration`, `GET /api/inspiration`, `_dict(img)`, `InspirationUpdate` schema (used in Task 3).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_inspiration_api.py
import io
from httpx import AsyncClient
from app.services import storage as storage_svc


def _png_bytes() -> bytes:
    # Minimal valid-enough PNG header bytes; content isn't parsed by the API.
    return b"\x89PNG\r\n\x1a\n" + b"0" * 32


async def _make_book(client: AsyncClient) -> str:
    return (await client.post("/api/books", json={"title": "B"})).json()["id"]


async def test_upload_creates_rows_and_stores_files(client: AsyncClient):
    book_id = await _make_book(client)
    files = [
        ("files", ("a.png", io.BytesIO(_png_bytes()), "image/png")),
        ("files", ("b.png", io.BytesIO(_png_bytes()), "image/png")),
    ]
    r = await client.post("/api/inspiration", files=files, data={"book_id": book_id, "caption": "moody"})
    assert r.status_code == 201
    rows = r.json()
    assert len(rows) == 2
    for row in rows:
        assert row["book_id"] == book_id
        assert row["caption"] == "moody"
        assert row["image_url"]
        # the stored key is the tail of the public url; confirm the object exists
    # Both files are stored
    listed = (await client.get("/api/inspiration?book_id=" + book_id)).json()
    assert len(listed) == 2


async def test_upload_rejects_non_image(client: AsyncClient):
    files = [("files", ("notes.txt", io.BytesIO(b"hello"), "text/plain"))]
    r = await client.post("/api/inspiration", files=files)
    assert r.status_code == 400


async def test_list_filters_global_and_all(client: AsyncClient):
    book_id = await _make_book(client)
    png = lambda name: ("files", (name, io.BytesIO(_png_bytes()), "image/png"))
    await client.post("/api/inspiration", files=[png("g.png")])                     # global
    await client.post("/api/inspiration", files=[png("b.png")], data={"book_id": book_id})
    all_rows = (await client.get("/api/inspiration")).json()
    assert len(all_rows) == 2
    global_rows = (await client.get("/api/inspiration?book_id=global")).json()
    assert len(global_rows) == 1 and global_rows[0]["book_id"] is None
    book_rows = (await client.get(f"/api/inspiration?book_id={book_id}")).json()
    assert len(book_rows) == 1 and book_rows[0]["book_id"] == book_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/test_inspiration_api.py -v`
Expected: FAIL — 404 (route not mounted).

- [ ] **Step 3: Create the router**

```python
# backend/app/routers/inspiration.py
from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Book, InspirationImage
from app.services import storage

router = APIRouter()

# content-type -> file extension for allowed image uploads
_ALLOWED_TYPES: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


class InspirationUpdate(BaseModel):
    caption: Optional[str] = None
    book_id: Optional[str] = None


def _dict(img: InspirationImage) -> dict:
    return {
        "id": img.id,
        "book_id": img.book_id,
        "image_url": storage.public_url(img.image_path) if img.image_path else None,
        "caption": img.caption,
        "created_at": img.created_at.isoformat() if img.created_at else None,
    }


@router.post("", status_code=201)
async def upload_inspiration(
    files: list[UploadFile] = File(...),
    book_id: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    if book_id:
        if not await db.get(Book, book_id):
            raise HTTPException(404, "Book not found")

    # Validate every file's type BEFORE storing any, so a bad file in the batch
    # doesn't leave orphaned objects from earlier files.
    payloads: list[tuple[str, bytes, str]] = []  # (ext, data, content_type)
    for f in files:
        ext = _ALLOWED_TYPES.get(f.content_type or "")
        if not ext:
            raise HTTPException(400, f"Unsupported image type: {f.content_type}")
        payloads.append((ext, await f.read(), f.content_type or "application/octet-stream"))

    created: list[InspirationImage] = []
    for ext, data, content_type in payloads:
        key = f"inspiration/{uuid.uuid4()}.{ext}"
        storage.put_bytes(key, data, content_type)
        img = InspirationImage(book_id=book_id or None, image_path=key, caption=caption)
        db.add(img)
        created.append(img)
    await db.commit()
    for img in created:
        await db.refresh(img)
    return [_dict(i) for i in created]


@router.get("")
async def list_inspiration(book_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(InspirationImage)
    if book_id in (None, "", "all"):
        pass
    elif book_id == "global":
        stmt = stmt.where(InspirationImage.book_id.is_(None))
    else:
        stmt = stmt.where(InspirationImage.book_id == book_id)
    stmt = stmt.order_by(InspirationImage.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_dict(i) for i in rows]
```

- [ ] **Step 4: Mount the router in main.py**

In `backend/app/main.py`, add `inspiration` to the routers import (line 14):

```python
from app.routers import books, pages, generate, export, dashboard, jobs, documents, settings, assets, inspiration
```

And add the include (after the `assets` include, line ~44):

```python
app.include_router(inspiration.router, prefix="/api/inspiration", tags=["inspiration"])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_inspiration_api.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/inspiration.py backend/app/main.py backend/tests/test_inspiration_api.py
git commit -m "feat(api): inspiration upload + list endpoints"
```

---

## Task 3: Inspiration PATCH (caption / reassign) + DELETE (with storage cleanup)

**Files:**
- Modify: `backend/app/routers/inspiration.py`
- Test: `backend/tests/test_inspiration_api.py` (extend)

**Interfaces:**
- Consumes: `_dict`, `InspirationUpdate`, `storage.delete_object`.
- Produces: `PATCH /api/inspiration/{id}`, `DELETE /api/inspiration/{id}`.

- [ ] **Step 1: Write the failing tests**

```python
# append to backend/tests/test_inspiration_api.py
async def _upload_one_global(client: AsyncClient) -> dict:
    files = [("files", ("g.png", io.BytesIO(_png_bytes()), "image/png"))]
    return (await client.post("/api/inspiration", files=files)).json()[0]


async def test_patch_caption_and_reassign_book(client: AsyncClient):
    book_id = await _make_book(client)
    img = await _upload_one_global(client)
    # set caption + attach to a book
    r = await client.patch(f"/api/inspiration/{img['id']}", json={"caption": "great", "book_id": book_id})
    assert r.status_code == 200
    assert r.json()["caption"] == "great"
    assert r.json()["book_id"] == book_id
    # explicit null clears book_id (back to global)
    r2 = await client.patch(f"/api/inspiration/{img['id']}", json={"book_id": None})
    assert r2.json()["book_id"] is None
    # caption unchanged by the book_id-only patch
    assert r2.json()["caption"] == "great"


async def test_patch_reassign_unknown_book_404(client: AsyncClient):
    img = await _upload_one_global(client)
    r = await client.patch(f"/api/inspiration/{img['id']}", json={"book_id": "nope"})
    assert r.status_code == 404


async def test_delete_removes_row_and_storage(client: AsyncClient):
    img = await _upload_one_global(client)
    # the stored key is the tail of the image_url path
    key = "inspiration/" + img["image_url"].rsplit("/inspiration/", 1)[1]
    assert storage_svc.exists(key)
    r = await client.delete(f"/api/inspiration/{img['id']}")
    assert r.status_code == 204
    assert not storage_svc.exists(key)
    assert len((await client.get("/api/inspiration")).json()) == 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run --directory backend pytest tests/test_inspiration_api.py -k "patch or delete_removes" -v`
Expected: FAIL — routes not defined (405/404).

- [ ] **Step 3: Implement PATCH + DELETE**

Append to `backend/app/routers/inspiration.py`:

```python
@router.patch("/{image_id}")
async def update_inspiration(image_id: str, body: InspirationUpdate, db: AsyncSession = Depends(get_db)):
    img = await db.get(InspirationImage, image_id)
    if not img:
        raise HTTPException(404, "Inspiration image not found")
    fields = body.model_fields_set  # distinguish explicit null from omitted
    if "caption" in fields:
        img.caption = body.caption
    if "book_id" in fields:
        if body.book_id is not None and not await db.get(Book, body.book_id):
            raise HTTPException(404, "Book not found")
        img.book_id = body.book_id
    await db.commit()
    await db.refresh(img)
    return _dict(img)


@router.delete("/{image_id}", status_code=204)
async def delete_inspiration(image_id: str, db: AsyncSession = Depends(get_db)):
    img = await db.get(InspirationImage, image_id)
    if not img:
        raise HTTPException(404, "Inspiration image not found")
    if img.image_path:
        storage.delete_object(img.image_path)
    await db.delete(img)
    await db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_inspiration_api.py -v`
Expected: PASS (all inspiration API tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/inspiration.py backend/tests/test_inspiration_api.py
git commit -m "feat(api): inspiration patch (caption/reassign) + delete with storage cleanup"
```

---

## Task 4: Delete a book also deletes its inspiration storage objects

**Files:**
- Modify: `backend/app/routers/books.py` (`delete_book`)
- Test: `backend/tests/test_inspiration_api.py` (extend)

**Interfaces:**
- Consumes: `Book.inspiration_images`, `storage.delete_object`.

Context: `delete_book` already eager-loads `Book.pages → Page.versions` and deletes version storage objects. Extend it to also load `Book.inspiration_images` and delete their storage objects before the cascade removes the rows.

- [ ] **Step 1: Write the failing test**

```python
# append to backend/tests/test_inspiration_api.py
async def test_delete_book_removes_inspiration_storage(client: AsyncClient):
    book_id = await _make_book(client)
    files = [("files", ("b.png", io.BytesIO(_png_bytes()), "image/png"))]
    img = (await client.post("/api/inspiration", files=files, data={"book_id": book_id})).json()[0]
    key = "inspiration/" + img["image_url"].rsplit("/inspiration/", 1)[1]
    assert storage_svc.exists(key)

    r = await client.delete(f"/api/books/{book_id}")
    assert r.status_code == 204
    assert not storage_svc.exists(key), "book delete must remove its inspiration files"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --directory backend pytest tests/test_inspiration_api.py -k delete_book_removes_inspiration -v`
Expected: FAIL — the inspiration file still exists after book delete.

- [ ] **Step 3: Extend `delete_book`**

In `backend/app/routers/books.py`, update the `delete_book` handler's eager-load to also fetch inspiration images, and delete their storage objects. Ensure `Page`, `PageVersion`, `InspirationImage` and `selectinload` are imported (add `InspirationImage` to the `from app.models import ...` line). The handler becomes:

```python
@router.delete("/{book_id}", status_code=204)
async def delete_book(book_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Book)
        .options(
            selectinload(Book.pages).selectinload(Page.versions),
            selectinload(Book.inspiration_images),
        )
        .where(Book.id == book_id)
    )
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(404, "Book not found")
    # delete page-version storage objects
    for page in book.pages:
        for v in page.versions:
            for key in (v.image_path, v.svg_path):
                if key:
                    storage.delete_object(key)
    # delete inspiration storage objects
    for img in book.inspiration_images:
        if img.image_path:
            storage.delete_object(img.image_path)
    await db.delete(book)
    await db.commit()
```

(If `books.py` does not yet import `storage`, add `from app.services import storage`. It should already import it from the prior storage-cleanup work — verify and only add if missing.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_inspiration_api.py -v`
Expected: PASS.

- [ ] **Step 5: Full backend suite**

Run: `uv run --directory backend pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/books.py backend/tests/test_inspiration_api.py
git commit -m "feat(api): delete book also removes its inspiration storage objects"
```

---

## Task 5: Frontend API layer — types + hooks

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/lib/__tests__/api.test.tsx` (extend)

**Interfaces:**
- Produces: `InspirationImage` type; `useInspiration`, `useUploadInspiration`, `useUpdateInspiration`, `useDeleteInspiration`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/lib/__tests__/api.test.tsx`, mirroring the existing `useVersions` test's fetch-mock + wrapper style:

```tsx
describe("useInspiration", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(
      JSON.stringify([{ id: "i1", book_id: null, image_url: "/storage/inspiration/x.png", caption: null, created_at: "" }]),
      { status: 200, headers: { "content-type": "application/json" } },
    )))
  })
  it("fetches inspiration for a scope", async () => {
    const { result } = renderHook(() => useInspiration("global"), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.[0].id).toBe("i1")
    expect(fetch).toHaveBeenCalledWith("/api/inspiration?book_id=global", expect.anything())
  })
})
```

(Match the file's existing `wrapper`/import conventions; `useInspiration` must be imported.)

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/lib/__tests__/api.test.tsx`
Expected: FAIL — `useInspiration` not exported.

- [ ] **Step 3: Add the type + hooks**

In `frontend/src/lib/api.ts` add the type and a new "Inspiration" section:

```ts
export interface InspirationImage {
  id: string
  book_id: string | null
  image_url: string | null
  caption: string | null
  created_at: string
}

// ── Inspiration ──────────────────────────────────────────────────────────────

export function useInspiration(scope: string) {
  // scope: "all" | "global" | <bookId>
  return useQuery<InspirationImage[]>({
    queryKey: ["inspiration", scope],
    queryFn: () => apiFetch<InspirationImage[]>(`/inspiration?book_id=${encodeURIComponent(scope)}`),
    enabled: !!scope,
  })
}

export function useUploadInspiration() {
  const qc = useQueryClient()
  return useMutation<InspirationImage[], Error, { files: File[]; bookId?: string | null; caption?: string }>({
    mutationFn: async ({ files, bookId, caption }) => {
      // Multipart: build FormData and let the browser set the boundary — do NOT
      // route through apiFetch (it forces Content-Type: application/json).
      const fd = new FormData()
      files.forEach((f) => fd.append("files", f))
      if (bookId) fd.append("book_id", bookId)
      if (caption) fd.append("caption", caption)
      const res = await fetch(`/api/inspiration`, { method: "POST", body: fd })
      if (!res.ok) throw new Error(`API ${res.status}: ${await res.text().catch(() => res.statusText)}`)
      return res.json() as Promise<InspirationImage[]>
    },
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["inspiration"] }) },
  })
}

export function useUpdateInspiration() {
  const qc = useQueryClient()
  return useMutation<InspirationImage, Error, { id: string; caption?: string; book_id?: string | null }>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<InspirationImage>(`/inspiration/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["inspiration"] }) },
  })
}

export function useDeleteInspiration() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => apiFetch<void>(`/inspiration/${id}`, { method: "DELETE" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["inspiration"] }) },
  })
}
```

- [ ] **Step 4: Run test + typecheck**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/lib/__tests__/api.test.tsx`
Run: `pnpm --dir frontend exec tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/lib/__tests__/api.test.tsx
git commit -m "feat(web): inspiration API types + hooks"
```

---

## Task 6: `InspirationGallery` component + `/inspiration` page

**Files:**
- Create: `frontend/src/features/inspiration/InspirationGallery.tsx`
- Create: `frontend/src/features/inspiration/InspirationPage.tsx`
- Modify: `frontend/src/App.tsx` (replace `InspirationPlaceholder` route with `InspirationPage`)
- Test: `frontend/src/features/inspiration/__tests__/InspirationGallery.test.tsx`

**Interfaces:**
- Consumes: `useInspiration`, `useUploadInspiration`, `useUpdateInspiration`, `useDeleteInspiration`, `useBooks`, `pageImageSrc`; `AlertDialog*`, `Dialog*` (existing ui components).
- Produces: `<InspirationGallery scope={...} />`, `<InspirationPage />`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/features/inspiration/__tests__/InspirationGallery.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { InspirationGallery } from "../InspirationGallery"

const IMAGES = [
  { id: "i1", book_id: null, image_url: "/storage/inspiration/a.png", caption: "calm forest", created_at: "" },
  { id: "i2", book_id: null, image_url: "/storage/inspiration/b.png", caption: null, created_at: "" },
]

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.startsWith("/api/inspiration") && (!init || init.method === undefined || init.method === "GET"))
      return new Response(JSON.stringify(IMAGES), { status: 200, headers: { "content-type": "application/json" } })
    if (url === "/api/books")
      return new Response(JSON.stringify([]), { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

function renderGallery(scope = "global") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}><InspirationGallery scope={scope} /></QueryClientProvider>,
  )
}

describe("InspirationGallery", () => {
  it("renders inspiration images with captions", async () => {
    renderGallery()
    expect(await screen.findByText("calm forest")).toBeInTheDocument()
    expect(screen.getAllByRole("img").length).toBe(2)
  })

  it("deletes an image", async () => {
    renderGallery()
    await screen.findByText("calm forest")
    await userEvent.click(screen.getAllByRole("button", { name: /delete inspiration/i })[0])
    // confirm in the alert dialog
    await userEvent.click(await screen.findByRole("button", { name: /^delete$/i }))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/inspiration/i1", expect.objectContaining({ method: "DELETE" })),
    )
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/inspiration/`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `InspirationGallery`**

```tsx
// frontend/src/features/inspiration/InspirationGallery.tsx
import { useRef, useState } from "react"
import {
  useInspiration, useUploadInspiration, useUpdateInspiration, useDeleteInspiration,
  useBooks, pageImageSrc, type InspirationImage,
} from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle,
  AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction,
} from "@/components/ui/alert-dialog"

export function InspirationGallery({ scope }: { scope: string }) {
  const { data: images = [], isLoading } = useInspiration(scope)
  const upload = useUploadInspiration()
  const del = useDeleteInspiration()
  const fileRef = useRef<HTMLInputElement>(null)

  // When embedded in a book (scope is a book id), new uploads attach to that book.
  const uploadBookId = scope !== "all" && scope !== "global" ? scope : null

  function onFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (files.length) upload.mutate({ files, bookId: uploadBookId })
    if (fileRef.current) fileRef.current.value = ""
  }

  return (
    <div className="space-y-4">
      <div>
        <input ref={fileRef} type="file" accept="image/*" multiple hidden onChange={onFiles} aria-label="Upload inspiration images" />
        <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
          {upload.isPending ? "Uploading…" : "Upload images"}
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : images.length === 0 ? (
        <p className="text-sm text-muted-foreground">No inspiration yet — upload images to get started.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
          {images.map((img) => (
            <ImageCard key={img.id} img={img} onDelete={() => del.mutate(img.id)} deleting={del.isPending} />
          ))}
        </div>
      )}
    </div>
  )
}

function ImageCard({ img, onDelete, deleting }: { img: InspirationImage; onDelete: () => void; deleting: boolean }) {
  const update = useUpdateInspiration()
  const { data: books = [] } = useBooks()
  return (
    <div className="rounded-lg border p-2">
      {img.image_url && (
        <img src={pageImageSrc(img.image_url)} alt={img.caption ?? "inspiration"} className="aspect-square w-full object-contain" />
      )}
      <input
        aria-label={`Caption for ${img.id}`}
        defaultValue={img.caption ?? ""}
        placeholder="add a caption…"
        className="mt-1 w-full bg-transparent text-xs outline-none"
        onBlur={(e) => { if (e.target.value !== (img.caption ?? "")) update.mutate({ id: img.id, caption: e.target.value }) }}
      />
      <div className="mt-1 flex items-center gap-2">
        <select
          aria-label={`Assign ${img.id} to book`}
          className="min-w-0 flex-1 bg-transparent text-xs"
          value={img.book_id ?? ""}
          onChange={(e) => update.mutate({ id: img.id, book_id: e.target.value || null })}
        >
          <option value="">Global</option>
          {books.map((b) => <option key={b.id} value={b.id}>{b.emoji} {b.title}</option>)}
        </select>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button size="sm" variant="outline" aria-label={`Delete inspiration ${img.id}`} disabled={deleting}>✕</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this image?</AlertDialogTitle>
              <AlertDialogDescription>This removes the image permanently.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={onDelete}>Delete</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}
```

(Match `Button`'s available props to the existing `button.tsx`. If the `select` clashes with the project's styling conventions, keep it simple — a native `<select>` is acceptable here.)

- [ ] **Step 4: Implement `InspirationPage` and wire the route**

```tsx
// frontend/src/features/inspiration/InspirationPage.tsx
import { useState } from "react"
import { useBooks } from "@/lib/api"
import { InspirationGallery } from "./InspirationGallery"

export function InspirationPage() {
  const { data: books = [] } = useBooks()
  const [scope, setScope] = useState("all")
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">Inspiration</h1>
        <select aria-label="Filter inspiration" className="text-sm" value={scope} onChange={(e) => setScope(e.target.value)}>
          <option value="all">All</option>
          <option value="global">Global</option>
          {books.map((b) => <option key={b.id} value={b.id}>{b.emoji} {b.title}</option>)}
        </select>
      </div>
      <InspirationGallery scope={scope} />
    </div>
  )
}
```

In `frontend/src/App.tsx`: import `InspirationPage` and replace the `/inspiration` route element (currently `<InspirationPlaceholder />`) with `<InspirationPage />`. Leave the other placeholder routes untouched. If `InspirationPlaceholder` becomes unused, remove its definition/import to keep the strict build clean.

- [ ] **Step 5: Run tests + typecheck + build**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/inspiration/ src/lib/`
Run: `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build`
Expected: PASS, build exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/inspiration/ frontend/src/App.tsx
git commit -m "feat(web): inspiration gallery component + /inspiration page"
```

---

## Task 7: Inspiration section on the book detail page

**Files:**
- Modify: `frontend/src/features/books/BookDetailPage.tsx`
- Test: `frontend/src/features/books/__tests__/BookDetailPage.test.tsx` (extend)

**Interfaces:**
- Consumes: `<InspirationGallery scope={bookId} />`.

- [ ] **Step 1: Write the failing test**

Extend the existing `BookDetailPage.test.tsx`. Ensure its fetch mock returns `[]` for `/api/inspiration...` (so the gallery renders its empty state without error), then assert the Inspiration section heading renders:

```tsx
// add to the existing BookDetailPage fetch mock's URL handling:
//   if (url.startsWith("/api/inspiration")) return json([])
// and a new test:
it("shows an Inspiration section", async () => {
  renderPage()
  expect(await screen.findByRole("heading", { name: /inspiration/i })).toBeInTheDocument()
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/__tests__/BookDetailPage.test.tsx`
Expected: FAIL — no Inspiration heading.

- [ ] **Step 3: Add the section**

In `BookDetailPage.tsx`, import `InspirationGallery` from `@/features/inspiration/InspirationGallery`, and render a section below the page grid:

```tsx
<section className="mt-8">
  <h2 className="mb-3 text-lg font-semibold">Inspiration</h2>
  <InspirationGallery scope={bookId} />
</section>
```

(`bookId` is the book's id already available in the component from the route params / `useBook`. Use the existing variable name.)

- [ ] **Step 4: Run tests + typecheck + build**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/books/`
Run: `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build`
Expected: PASS, build exit 0.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/books/BookDetailPage.tsx frontend/src/features/books/__tests__/BookDetailPage.test.tsx
git commit -m "feat(web): inspiration section on book detail page"
```

---

## Task 8: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Backend suite** — `uv run --directory backend pytest -q` → all pass.
- [ ] **Step 2: Frontend suite** — `pnpm --dir frontend test --run --pool=forks --no-file-parallelism` → all pass.
- [ ] **Step 3: Typecheck + build** — `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build` → clean, exit 0.
- [ ] **Step 4: Manual smoke** — start backend + frontend; on `/inspiration` upload two images, see them in the grid, filter All/Global/book, add a caption, assign one to a book, delete one; open a book and confirm its Inspiration section shows book-scoped images and uploads attach to that book.
- [ ] **Step 5: Final commit (if any tweaks)** — `git add -A && git commit -m "chore: verification tweaks for inspiration images"`

---

## Self-Review (completed during authoring)

**Spec coverage:** upload (multi-file) → T2; global/book scope + list filter → T2; caption + reassign → T3; delete row+storage → T3; book-delete storage cleanup → T4; new table auto-migration → T1 (no `_COLUMN_MIGRATIONS`); frontend types/hooks → T5; reusable gallery + `/inspiration` page → T6; book-detail section → T7; content-type validation → T2; reference-only (no print/generator) → nothing added there, correct.

**Placeholders:** none — all code steps contain complete code; UI-wiring steps that reference an existing local variable (`bookId` in BookDetailPage) say so explicitly rather than guessing.

**Type consistency:** `InspirationImage` fields identical across T1 (model), T2 (`_dict`), T5 (TS type). Hook names (`useInspiration/useUploadInspiration/useUpdateInspiration/useDeleteInspiration`) consistent T5→T6→T7. `_dict` shape `{id, book_id, image_url, caption, created_at}` matches the TS interface. `scope` prop is `"all"|"global"|bookId` in both T6 and T7. `book_id` set-aware PATCH (model_fields_set) matches the frontend sending explicit `null` to clear.
