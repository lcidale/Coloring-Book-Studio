// frontend/src/features/editor/__tests__/VersionsPanel.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { VersionsPanel } from "../VersionsPanel"

const VERSIONS = [
  { id: "v2", page_id: "p1", version_num: 2, image_url: "/storage/v2.png", svg_url: null, prompt: "prompt two", label: null, notes: null, dpi: 300, width_px: 2550, height_px: 3300, is_pure_bw: true, created_at: "", is_current: true },
  { id: "v1", page_id: "p1", version_num: 1, image_url: "/storage/v1.png", svg_url: null, prompt: "prompt one", label: "too busy", notes: null, dpi: 300, width_px: 2550, height_px: 3300, is_pure_bw: true, created_at: "", is_current: false },
]

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (url === "/api/pages/p1/versions")
      return new Response(JSON.stringify(VERSIONS), { status: 200, headers: { "content-type": "application/json" } })
    return new Response("{}", { status: 200, headers: { "content-type": "application/json" } })
  }))
})

function renderPanel(onCopy = vi.fn()) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <VersionsPanel pageId="p1" onCopyPrompt={onCopy} />
    </QueryClientProvider>,
  )
  return onCopy
}

describe("VersionsPanel", () => {
  it("lists versions newest-first with a current badge", async () => {
    renderPanel()
    expect(await screen.findByText("v2")).toBeInTheDocument()
    expect(screen.getByText("Current")).toBeInTheDocument()
    expect(screen.getByText("too busy")).toBeInTheDocument()
  })

  it("copies a version's prompt to the editor", async () => {
    const onCopy = renderPanel()
    await screen.findByText("v1")
    await userEvent.click(screen.getAllByRole("button", { name: /copy prompt/i })[1])
    expect(onCopy).toHaveBeenCalledWith("prompt one")
  })

  it("disables delete on the current version", async () => {
    renderPanel()
    await screen.findByText("v2")
    const del = screen.getAllByRole("button", { name: /delete version/i })
    // v2 is current → its delete is disabled
    expect(del[0]).toBeDisabled()
  })
})
