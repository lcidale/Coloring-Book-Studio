// frontend/src/features/editor/__tests__/ReferencePicker.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { ReferencePicker } from "../ReferencePicker"

const PAGE = { id: "p1", book_id: "b1", reference_image_id: null, reference_image_url: null } as any
const ELIGIBLE = [
  { id: "i1", book_id: "b1", image_url: "/storage/inspiration/a.png", caption: "fox ref", created_at: "" },
  { id: "i2", book_id: null, image_url: "/storage/inspiration/b.png", caption: null, created_at: "" },
]

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url.startsWith("/api/inspiration")) return new Response(JSON.stringify(ELIGIBLE), { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

function renderPicker(page = PAGE) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={qc}><ReferencePicker page={page} /></QueryClientProvider>)
}

describe("ReferencePicker", () => {
  it("lists eligible images and sets one as the sticky reference", async () => {
    renderPicker()
    await userEvent.click(await screen.findByRole("button", { name: /set reference/i }))
    await userEvent.click(await screen.findByText("fox ref"))
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith("/api/pages/p1", expect.objectContaining({ method: "PATCH" })),
    )
  })
})
