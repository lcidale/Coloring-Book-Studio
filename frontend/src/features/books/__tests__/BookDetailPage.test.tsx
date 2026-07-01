import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter, Routes, Route } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { BookDetailPage } from "../BookDetailPage"

const PAGES = [
  { id: "p1", book_id: "b1", sort_order: 0, title: "One", concept: "one", status: "idea", prompt: null, negative_prompt: null, image_path: null, image_dpi: null, image_width_px: null, image_height_px: null, is_pure_bw: null, print_check_notes: null, created_at: "", updated_at: "", text_layers: [] },
  { id: "p2", book_id: "b1", sort_order: 1, title: "Two", concept: "two", status: "idea", prompt: null, negative_prompt: null, image_path: null, image_dpi: null, image_width_px: null, image_height_px: null, is_pure_bw: null, print_check_notes: null, created_at: "", updated_at: "", text_layers: [] },
]

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/books/b1") return new Response(JSON.stringify({ id: "b1", title: "B", emoji: "📖", theme: "", audience: "", positioning: "", target_page_count: 30, page_count: 2, approved_count: 0, progress_pct: 0, created_at: "", updated_at: "", style_guide: null }), { status: 200, headers: { "content-type": "application/json" } })
    if (url === "/api/pages/book/b1") return new Response(JSON.stringify(PAGES), { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/books/b1"]}>
        <Routes><Route path="/books/:id" element={<BookDetailPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("BookDetailPage", () => {
  it("shows pages with derived p.NN — Title labels", async () => {
    renderPage()
    expect(await screen.findByText("p.01 — One")).toBeInTheDocument()
    expect(await screen.findByText("p.02 — Two")).toBeInTheDocument()
  })
})
