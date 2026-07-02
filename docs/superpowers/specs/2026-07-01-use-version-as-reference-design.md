# Design: "Use as Reference" One-Click Shortcut

**Date:** 2026-07-01
**Status:** Approved
**Author:** Leslie + Claude

## Problem

Once the inspiration-reference feature shipped, using a *just-generated* image as the
reference for a follow-up small edit requires: save the image from the browser, upload it
to the Inspiration gallery, then set it as the page's reference via the Reference picker.
That three-step round trip is friction for the common case of "I like this, but change one
small thing."

## Goal

A single button on any version in the editor's Versions panel that turns that version's
image into the page's sticky reference immediately — no download, no re-upload, no second
trip to the Reference picker.

## Non-goals

- No UI to "unlink" or otherwise specially manage an auto-created inspiration image — once
  created it is a normal inspiration image, editable/deletable like any other from the
  gallery or the Reference picker.
- No change to the existing manual save-and-upload path; this is an additional shortcut,
  not a replacement.

## Design decision: copy, don't share, the underlying file

Two ways to implement this were considered:

1. **Point `Page.reference_image_id` at a new `InspirationImage` row that reuses the
   version's existing storage key.** Rejected: `delete_version` carries an explicit
   invariant ("each version has a unique image_path... so deleting a non-current version
   never removes a file still referenced by another") that a shared key would silently
   violate — deleting the source version later would delete the file the reference still
   needs.
2. **Copy the version's bytes into a new, independent storage object and `InspirationImage`
   row (chosen).** This exactly mirrors what the manual save+upload workflow already does,
   just performed server-side. The new inspiration image has its own lifecycle from that
   point on; deleting the original version can never affect it.

## Backend

New endpoint on the existing pages router:

`POST /api/pages/{page_id}/versions/{version_id}/use-as-reference`

Behavior:
1. Load the page + version (404 if either is missing).
2. Copy the version's image bytes to a new storage key `inspiration/<uuid>.png` via
   `storage.get_bytes` / `storage.put_bytes` (mirrors `upload_inspiration`'s key scheme).
3. Create an `InspirationImage` row with `book_id = page.book_id` (scoped to the page's own
   book, not global — it originated from that book's work, so it stays discoverable there
   rather than cluttering the shared global pool).
4. Set `page.reference_image_id` to the new row's id (the sticky reference is applied
   immediately — this is the "one click" the feature is named for).
5. Return the updated page (`_page_dict`, with `_attach_reference` called first so
   `reference_image_url` is populated in the response).

No new eligibility check is needed: an image scoped to `page.book_id` is trivially eligible
for that same page per the existing "global or same book" rule.

## Frontend

- New hook `useUseVersionAsReference(pageId)` in `frontend/src/lib/api.ts` — `POST`s to the
  new endpoint, invalidates `["pages", "detail", pageId]` and `["inspiration", ...]` queries
  on success so the editor's Reference control and the Inspiration gallery both reflect the
  new image without a manual refresh.
- A new button on every row in `frontend/src/features/editor/VersionsPanel.tsx`, alongside
  the existing Restore/Delete/label controls: **"Use as reference"**. No confirmation dialog
  needed — it's a fast, low-stakes, reversible action (the user can immediately pick a
  different reference or clear it).

## Testing

- **Backend (pytest):** the endpoint copies bytes to a new storage key (assert
  `storage.exists` on the new key, independent of the source version's key); creates an
  `InspirationImage` scoped to the page's book; sets `page.reference_image_id` to the new
  row and the response includes `reference_image_url`; 404 on unknown page/version; deleting
  the *source* version afterward does not affect the new reference (proves independence).
- **Frontend (Vitest/RTL):** clicking "Use as reference" on a version row calls the new hook
  with the right page/version ids; the Reference control's thumbnail updates after success
  (covered by the existing query-invalidation pattern — no new component logic to test
  beyond the button wiring itself).

## Rollout

Additive: one new endpoint, one new hook, one new button. No schema changes, no migration.
