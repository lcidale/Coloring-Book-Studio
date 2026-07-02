# Use Version as Reference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A one-click "Use as reference" button on any version in the editor's Versions panel that turns that version's image into the page's sticky reference, without a manual download/re-upload round trip.

**Architecture:** One new backend endpoint copies a version's image bytes into a new, independent `InspirationImage` (never reusing the version's own storage key, so deleting the source version later can't affect the reference), scopes it to the page's book, and sets it as the page's sticky reference in one call. One new frontend hook + button wire it into the existing Versions panel.

**Tech Stack:** FastAPI + async SQLAlchemy (Python 3.12/uv). React 19 + TanStack Query. Tests: pytest, Vitest/RTL.

## Global Constraints

- **Copy, never share, storage keys.** The new `InspirationImage` gets its own storage object at a fresh `inspiration/<uuid>.<ext>` key (mirrors `upload_inspiration`'s scheme in `backend/app/routers/inspiration.py`) — never point it at the version's existing `books/{book_id}/pages/{page_id}/vNNN.png` key. `delete_version` explicitly assumes each version's image_path is exclusively its own; violating that would let a later version-delete silently destroy the new reference's file.
- **Book-scoped, not global.** The new inspiration image gets `book_id = page.book_id`.
- **One click sets the reference immediately** — no second trip through the Reference picker required.
- **Backend tests:** `export PATH="$HOME/.local/bin:$HOME/.local/node-v24.18.0-darwin-arm64/bin:$PATH"` then `uv run --directory backend pytest`. Use the conftest `client` fixture. `asyncio_mode="auto"`.
- **Frontend tests:** `pnpm --dir frontend test --run --pool=forks --no-file-parallelism`. Tests live in `__tests__/` dirs.
- **Frontend "green" = `pnpm --dir frontend build` passes** (its `tsc -b` is stricter than `tsc --noEmit` — no unused imports).

### Shared contract (names used across tasks — do not drift)

- Endpoint: `POST /api/pages/{page_id}/versions/{version_id}/use-as-reference` → returns `_page_dict(page)` (same shape `GET /api/pages/{page_id}` returns, including `reference_image_id`/`reference_image_url`).
- Frontend hook: `useUseVersionAsReference(pageId: string)` in `frontend/src/lib/api.ts`, mutation input `versionId: string`, returns `Page`.
- New button in `frontend/src/features/editor/VersionsPanel.tsx`, per version row, label "Use as reference".

---

## Task 1: Backend endpoint

**Files:**
- Modify: `backend/app/routers/pages.py` (new route, placed after `restore_version`)
- Test: `backend/tests/test_reference_image.py`

**Interfaces:**
- Consumes: `_attach_reference(page, db)`, `_page_dict(page)` (both already exist in `pages.py`); `storage.get_bytes`, `storage.put_bytes` (`backend/app/services/storage.py`); `InspirationImage` model.
- Produces: `POST /api/pages/{page_id}/versions/{version_id}/use-as-reference`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_reference_image.py` (it already has `_book_page`, `_upload_inspiration` helpers and the `client` fixture):

```python
async def test_use_version_as_reference_sets_sticky_reference(client: AsyncClient):
    book_id, page = await _book_page(client)
    gen = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert gen.status_code == 200
    versions = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    v1_id = versions[0]["id"]

    r = await client.post(f"/api/pages/{page['id']}/versions/{v1_id}/use-as-reference")
    assert r.status_code == 200
    body = r.json()
    assert body["reference_image_id"] is not None
    assert body["reference_image_url"] is not None

    # the new inspiration image is scoped to this page's book
    listed = (await client.get(f"/api/inspiration?book_id={book_id}")).json()
    assert any(img["id"] == body["reference_image_id"] for img in listed)


async def test_use_version_as_reference_copies_bytes_independently(client: AsyncClient):
    """Deleting the SOURCE version afterward must not affect the new reference —
    proves the new inspiration image has its own storage object, not a shared key."""
    from app.services import storage as storage_svc

    book_id, page = await _book_page(client)
    gen1 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    gen2 = await client.post(f"/api/generate/{page['id']}", json={"auto_cleanup": False, "vectorize": False})
    assert gen1.status_code == 200 and gen2.status_code == 200
    versions = (await client.get(f"/api/pages/{page['id']}/versions")).json()
    v1_id = next(v["id"] for v in versions if v["version_num"] == 1)  # not current (v2 is)

    r = await client.post(f"/api/pages/{page['id']}/versions/{v1_id}/use-as-reference")
    assert r.status_code == 200
    ref_url = r.json()["reference_image_url"]
    ref_key = "inspiration/" + ref_url.rsplit("/inspiration/", 1)[1]
    assert storage_svc.exists(ref_key)

    del_resp = await client.delete(f"/api/pages/{page['id']}/versions/{v1_id}")
    assert del_resp.status_code == 204

    refreshed = (await client.get(f"/api/pages/{page['id']}")).json()
    assert refreshed["reference_image_id"] == r.json()["reference_image_id"], (
        "the reference must survive deletion of the source version"
    )
    assert storage_svc.exists(ref_key), "the new inspiration image's own file must be untouched"


async def test_use_version_as_reference_404_unknown_version(client: AsyncClient):
    _, page = await _book_page(client)
    r = await client.post(f"/api/pages/{page['id']}/versions/nope/use-as-reference")
    assert r.status_code == 404


async def test_use_version_as_reference_404_unknown_page(client: AsyncClient):
    r = await client.post("/api/pages/nope/versions/nope/use-as-reference")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --directory backend pytest tests/test_reference_image.py -k use_version_as_reference -v`
Expected: FAIL — 404/405 (route doesn't exist yet).

- [ ] **Step 3: Implement the endpoint**

In `backend/app/routers/pages.py`, add the route immediately after `restore_version` (after the line `return _page_dict(page)` that closes it, before the blank lines leading into `@router.get("/{page_id}/versions")`). Add `import uuid` to the top-level imports if not already present (check first — `pages.py` currently does not import `uuid`).

```python
@router.post("/{page_id}/versions/{version_id}/use-as-reference")
async def use_version_as_reference(page_id: str, version_id: str, db: AsyncSession = Depends(get_db)):
    """Copy a version's image into a new, independent inspiration image scoped to
    this page's book, and set it as the page's sticky reference — one click,
    no manual download/re-upload. The copy is deliberate: never reuse the
    version's own storage key, since delete_version assumes each version's
    image_path is exclusively its own."""
    result = await db.execute(
        select(Page)
        .options(selectinload(Page.text_layers), selectinload(Page.versions))
        .where(Page.id == page_id)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(404, "Page not found")

    pv = next((v for v in page.versions if v.id == version_id), None)
    if pv is None:
        raise HTTPException(404, "Version not found")

    data = storage.get_bytes(pv.image_path)
    ext = pv.image_path.rsplit(".", 1)[-1] if "." in pv.image_path else "png"
    new_key = f"inspiration/{uuid.uuid4()}.{ext}"
    storage.put_bytes(new_key, data, "image/png")

    img = InspirationImage(book_id=page.book_id, image_path=new_key)
    db.add(img)
    await db.flush()

    page.reference_image_id = img.id
    page.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(page)
    await _attach_reference(page, db)
    return _page_dict(page)
```

(`InspirationImage` is already imported in `pages.py`'s top-level `from app.models import ...` line — verify and use as-is. `uuid` needs adding to the imports at the top of the file: `import uuid` alongside the existing `from __future__ import annotations`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --directory backend pytest tests/test_reference_image.py -k use_version_as_reference -v`
Expected: PASS (all 4 new tests).

- [ ] **Step 5: Full backend suite**

Run: `uv run --directory backend pytest -q`
Expected: all pass, no regressions.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/pages.py backend/tests/test_reference_image.py
git commit -m "feat(api): one-click use-version-as-reference endpoint"
```

---

## Task 2: Frontend hook + button

**Files:**
- Modify: `frontend/src/lib/api.ts` (new hook, placed after `useRestoreVersion`)
- Modify: `frontend/src/features/editor/VersionsPanel.tsx` (new button per row)
- Test: `frontend/src/features/editor/__tests__/VersionsPanel.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `Page` type (both already in `api.ts`).
- Produces: `useUseVersionAsReference(pageId: string)` — `useMutation<Page, Error, string>` where the mutate argument is `versionId`.

- [ ] **Step 1: Write the failing test**

Read `frontend/src/features/editor/__tests__/VersionsPanel.test.tsx` first to match its existing fetch-mock/provider style exactly (it already mocks `useVersions`/`useRestoreVersion`/`useUpdateVersion`/`useDeleteVersion` via `vi.mock('@/lib/api', ...)` — confirm the exact mock shape before adding to it). Add:

```tsx
// Add "useUseVersionAsReference: vi.fn()" to the existing vi.mock('@/lib/api', () => ({...})) factory,
// and add a corresponding vi.mocked(api.useUseVersionAsReference).mockReturnValue(makeMutation())
// in the same setup block where the other version hooks are mocked (mirror useRestoreVersion's setup).

it("calls useUseVersionAsReference with the version id when clicked", async () => {
  const useAsRef = vi.fn()
  vi.mocked(api.useUseVersionAsReference).mockReturnValue({ mutate: useAsRef, isPending: false } as unknown as ReturnType<typeof api.useUseVersionAsReference>)
  renderPanel()
  await screen.findByText("v2")
  await userEvent.click(screen.getAllByRole("button", { name: /use as reference/i })[0])
  expect(useAsRef).toHaveBeenCalledWith("v2")
})
```

(Match the exact `renderPanel`/mock-versions fixture already present in the file — `v2` is the first/current version in the existing `VERSIONS` fixture per the file's established pattern; adjust the id literal to whatever that fixture actually uses if different from `"v2"`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/editor/__tests__/VersionsPanel.test.tsx`
Expected: FAIL — `useUseVersionAsReference` not exported / button not found.

- [ ] **Step 3: Add the hook to api.ts**

In `frontend/src/lib/api.ts`, add immediately after `useRestoreVersion`'s closing brace:

```ts
export function useUseVersionAsReference(pageId: string) {
  const qc = useQueryClient()
  return useMutation<Page, Error, string>({
    mutationFn: (versionId) =>
      apiFetch<Page>(`/pages/${pageId}/versions/${versionId}/use-as-reference`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (page) => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", page.book_id] })
      void qc.invalidateQueries({ queryKey: ["inspiration"] })
    },
  })
}
```

- [ ] **Step 4: Add the button to VersionsPanel.tsx**

In `frontend/src/features/editor/VersionsPanel.tsx`, add `useUseVersionAsReference` to the import from `@/lib/api`, instantiate it alongside the other version hooks, and add the button to the per-row action row:

```tsx
// import line becomes:
import { useVersions, useRestoreVersion, useUpdateVersion, useDeleteVersion, useUseVersionAsReference, pageImageSrc } from "@/lib/api"

// inside the component body, alongside the other hooks:
  const useAsReference = useUseVersionAsReference(pageId)

// inside the per-row action div, alongside the existing three buttons:
                <Button size="sm" variant="outline" disabled={useAsReference.isPending} onClick={() => useAsReference.mutate(v.id)}>Use as reference</Button>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --dir frontend test --run --pool=forks --no-file-parallelism src/features/editor/`
Expected: PASS.

- [ ] **Step 6: Typecheck + build**

Run: `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build`
Expected: clean, exit 0.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/features/editor/VersionsPanel.tsx frontend/src/features/editor/__tests__/VersionsPanel.test.tsx
git commit -m "feat(web): one-click use-version-as-reference button in Versions panel"
```

---

## Task 3: Full verification

- [ ] **Step 1:** `uv run --directory backend pytest -q` → all pass.
- [ ] **Step 2:** `pnpm --dir frontend test --run --pool=forks --no-file-parallelism` → all pass.
- [ ] **Step 3:** `pnpm --dir frontend exec tsc --noEmit && pnpm --dir frontend build` → clean, exit 0.
- [ ] **Step 4 (manual smoke):** generate a page twice, open the Versions panel, click "Use as reference" on v1, confirm the editor's Reference control shows the new thumbnail immediately, confirm it also appears in that book's Inspiration section, then delete v1 and confirm the reference is unaffected.

---

## Self-Review

**Spec coverage:** copy-not-share semantics → Task 1 Step 3 (`storage.get_bytes`/`put_bytes` to a fresh key) + Task 1's independence test. Book-scoping → `InspirationImage(book_id=page.book_id, ...)`. One-click sets the reference immediately → `page.reference_image_id = img.id` in the same request. Button on every version row → Task 2 Step 4.

**Placeholders:** none — all steps carry complete code.

**Type consistency:** endpoint path `/pages/{page_id}/versions/{version_id}/use-as-reference` identical in Task 1 (route decorator) and Task 2 (hook's `apiFetch` call). Hook name `useUseVersionAsReference(pageId)` with mutate-argument `versionId: string` matches between its definition (Task 2 Step 3) and its test/usage (Task 2 Steps 1 and 4).
