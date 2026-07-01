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
