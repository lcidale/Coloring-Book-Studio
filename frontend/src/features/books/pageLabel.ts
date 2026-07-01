import type { Page } from "@/lib/api"

export function pageDisplayName(page: Pick<Page, "title" | "concept">, index: number): string {
  const num = String(index + 1).padStart(2, "0")
  const name = (page.title?.trim())
    || (page.concept?.split("\n")[0].trim().slice(0, 40))
    || "Untitled"
  return `p.${num} — ${name}`
}
