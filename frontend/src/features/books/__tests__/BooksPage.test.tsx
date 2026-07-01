/**
 * BooksPage.test.tsx — unit tests for rename + delete book actions.
 *
 * Stubs global fetch so no real network calls occur.
 * Wraps in QueryClientProvider + MemoryRouter.
 */
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { MemoryRouter } from "react-router-dom"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { BooksPage } from "../BooksPage"

// ── Mock sonner so we don't need the real implementation ─────────────────────

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

// ── Helpers ───────────────────────────────────────────────────────────────────

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <BooksPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

// ── Fixtures ──────────────────────────────────────────────────────────────────

const BOOK = {
  id: "b1",
  title: "Woodland",
  emoji: "📖",
  theme: "",
  audience: "",
  positioning: "",
  target_page_count: 30,
  page_count: 0,
  approved_count: 0,
  progress_pct: 0,
  created_at: "",
  updated_at: "",
  style_guide: null,
}

// ── Setup ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/books" && (!init || init.method === undefined))
        return new Response(JSON.stringify([BOOK]), {
          status: 200,
          headers: { "content-type": "application/json" },
        })
      return new Response("{}", {
        status: 200,
        headers: { "content-type": "application/json" },
      })
    }),
  )
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("BooksPage book menu", () => {
  it("opens rename dialog pre-filled with the current title", async () => {
    renderPage()
    await screen.findByText("Woodland")
    await userEvent.click(screen.getByLabelText("Book actions for Woodland"))
    await userEvent.click(await screen.findByText("Rename"))
    const input = (await screen.findByLabelText("Title")) as HTMLInputElement
    expect(input.value).toBe("Woodland")
  })

  it("delete confirm calls the DELETE endpoint", async () => {
    renderPage()
    await screen.findByText("Woodland")
    await userEvent.click(screen.getByLabelText("Book actions for Woodland"))
    await userEvent.click(await screen.findByText("Delete"))
    // Confirm button in the alert dialog
    const confirmBtn = await screen.findByRole("button", { name: /delete/i })
    await userEvent.click(confirmBtn)
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const deleteCalls = fetchMock.mock.calls.filter(
        ([url, init]) => url === "/api/books/b1" && (init as RequestInit)?.method === "DELETE",
      )
      expect(deleteCalls.length).toBeGreaterThanOrEqual(1)
    })
  })
})
