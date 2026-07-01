// frontend/src/features/editor/ReferencePicker.tsx
import { useState } from "react"
import { useInspiration, useUpdatePage, pageImageSrc, type Page, type InspirationImage } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function ReferencePicker({ page }: { page: Page }) {
  const update = useUpdatePage()
  const bookImages = useInspiration(page.book_id)
  const globalImages = useInspiration("global")
  const [open, setOpen] = useState(false)

  const seen = new Set<string>()
  const eligible: InspirationImage[] = [
    ...(bookImages.data ?? []),
    ...(globalImages.data ?? []),
  ].filter((img) => {
    if (seen.has(img.id)) return false
    seen.add(img.id)
    return true
  })

  function choose(id: string | null) {
    update.mutate({ id: page.id, reference_image_id: id })
    setOpen(false)
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">Reference image</span>
        {page.reference_image_url ? (
          <>
            <img src={pageImageSrc(page.reference_image_url)} alt="reference" className="h-10 w-8 object-contain border" />
            <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Change</Button>
            <Button size="sm" variant="outline" onClick={() => choose(null)}>Clear</Button>
          </>
        ) : (
          <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Set reference</Button>
        )}
      </div>
      {open && (
        <div className="grid grid-cols-4 gap-2 rounded border p-2">
          {eligible.length === 0 && <p className="text-xs text-muted-foreground">No eligible images. Add inspiration to this book or Global.</p>}
          {eligible.map((img) => (
            <button key={img.id} type="button" className="border p-1 text-left" onClick={() => choose(img.id)}>
              {img.image_url && <img src={pageImageSrc(img.image_url)} alt={img.caption ?? "inspiration"} className="aspect-square w-full object-contain" />}
              <span className="block truncate text-[10px]">{img.caption ?? "—"}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
