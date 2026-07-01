// frontend/src/features/inspiration/InspirationGallery.tsx
import { useRef } from "react"
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
      {img.caption && <p className="mt-1 text-xs text-muted-foreground">{img.caption}</p>}
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
