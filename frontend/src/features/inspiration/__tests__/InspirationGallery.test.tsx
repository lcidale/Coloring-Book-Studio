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
