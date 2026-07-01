import { describe, it, expect } from "vitest"
import { pageDisplayName } from "./pageLabel"

describe("pageDisplayName", () => {
  it("uses title with zero-padded 1-based number", () => {
    expect(pageDisplayName({ title: "Sleeping Fox", concept: "x" } as any, 2)).toBe("p.03 — Sleeping Fox")
  })
  it("falls back to concept first line when no title", () => {
    expect(pageDisplayName({ title: null, concept: "a curled fox\nmore" } as any, 0)).toBe("p.01 — a curled fox")
  })
  it("falls back to Untitled when both empty", () => {
    expect(pageDisplayName({ title: null, concept: "" } as any, 0)).toBe("p.01 — Untitled")
  })
})
