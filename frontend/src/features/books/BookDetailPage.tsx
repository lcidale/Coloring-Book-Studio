/**
 * BookDetailPage — /books/:id route.
 * Shows page grid with status filters, style-guide dialog, add-page dialog.
 */
import * as React from "react"
import { useParams, useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { ProgressBar } from "@/components/ui/progress"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  useBook,
  usePages,
  useCreatePage,
  useUpdateStyleGuide,
  exportBookPdf,
  pageImageSrc,
  type PageStatus,
  type StyleGuide,
} from "@/lib/api"

// ── Helpers ────────────────────────────────────────────────────────────────────

const ALL_STATUSES: PageStatus[] = [
  "idea", "prompt", "generated", "review", "revision", "approved", "print_ready", "exported",
]

const STATUS_EMOJI: Record<PageStatus, string> = {
  idea: "💭", prompt: "✏️", generated: "🖼", review: "🔍",
  revision: "🔄", approved: "👍", print_ready: "🖨", exported: "📦",
}

const STATUS_LABEL: Record<PageStatus, string> = {
  idea: "Idea", prompt: "Prompt", generated: "Generated", review: "Review",
  revision: "Revision", approved: "Approved", print_ready: "Print Ready", exported: "Exported",
}

const STATUS_VARIANT: Record<PageStatus, React.ComponentProps<typeof Badge>["variant"]> = {
  idea: "gray", prompt: "yellow", generated: "purple", review: "blue",
  revision: "red", approved: "green", print_ready: "green", exported: "gray",
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)] ${className}`} />
}

// ── Style Guide Dialog ─────────────────────────────────────────────────────────

function StyleGuideDialog({
  open,
  onClose,
  bookId,
  current,
}: {
  open: boolean
  onClose: () => void
  bookId: string
  current: StyleGuide | null
}) {
  const update = useUpdateStyleGuide()
  const [form, setForm] = React.useState<Partial<StyleGuide>>({
    line_weight: current?.line_weight ?? "medium",
    detail_level: current?.detail_level ?? "moderate",
    white_space: current?.white_space ?? "generous",
    motifs: current?.motifs ?? "",
    positive_prefix: current?.positive_prefix ?? "",
    positive_suffix: current?.positive_suffix ?? "",
    negative_prompt: current?.negative_prompt ?? "",
    trim_width_in: current?.trim_width_in ?? 8.5,
    trim_height_in: current?.trim_height_in ?? 11,
    bleed_in: current?.bleed_in ?? 0.125,
    margin_in: current?.margin_in ?? 0.5,
    target_dpi: current?.target_dpi ?? 300,
  })

  React.useEffect(() => {
    if (current) {
      setForm({
        line_weight: current.line_weight,
        detail_level: current.detail_level,
        white_space: current.white_space,
        motifs: current.motifs,
        positive_prefix: current.positive_prefix,
        positive_suffix: current.positive_suffix,
        negative_prompt: current.negative_prompt,
        trim_width_in: current.trim_width_in,
        trim_height_in: current.trim_height_in,
        bleed_in: current.bleed_in,
        margin_in: current.margin_in,
        target_dpi: current.target_dpi,
      })
    }
  }, [current])

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    try {
      await update.mutateAsync({ bookId, ...form })
      toast.success("Style guide saved.")
      onClose()
    } catch (err) {
      toast.error(String(err))
    }
  }

  function textField(label: string, key: keyof StyleGuide, placeholder = "") {
    return (
      <div>
        <label className="mb-1 block text-[12px] font-medium text-[var(--foreground)]">
          {label}
        </label>
        <input
          type="text"
          placeholder={placeholder}
          value={String(form[key] ?? "")}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
        />
      </div>
    )
  }

  function numField(label: string, key: keyof StyleGuide, step = 0.1) {
    return (
      <div>
        <label className="mb-1 block text-[12px] font-medium text-[var(--foreground)]">
          {label}
        </label>
        <input
          type="number"
          step={step}
          value={String(form[key] ?? "")}
          onChange={(e) => setForm((f) => ({ ...f, [key]: Number(e.target.value) }))}
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
        />
      </div>
    )
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Style Guide</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSave}>
          <div className="max-h-[60vh] overflow-y-auto">
            <p className="mb-3 text-[12px] text-[var(--muted-foreground)]">
              Style rules applied to every page prompt automatically.
            </p>
            <div className="flex flex-col gap-3">
              {textField("Line Weight", "line_weight", "e.g. medium, thick, fine")}
              {textField("Detail Level", "detail_level", "e.g. moderate, high, low")}
              {textField("White Space", "white_space", "e.g. generous, minimal")}
              {textField("Motifs / Visual Elements", "motifs", "e.g. floral borders, mandalas")}

              <div className="border-t border-[var(--border)] pt-3">
                <p className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                  Prompt Modifiers
                </p>
                {textField("Positive Prefix", "positive_prefix", "Added before every prompt")}
                {textField("Positive Suffix", "positive_suffix", "Added after every prompt")}
                {textField("Negative Prompt", "negative_prompt", "What to avoid in every image")}
              </div>

              <div className="border-t border-[var(--border)] pt-3">
                <p className="mb-2 text-[11.5px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                  Print Specs
                </p>
                <div className="grid grid-cols-2 gap-2">
                  {numField("Width (in)", "trim_width_in")}
                  {numField("Height (in)", "trim_height_in")}
                  {numField("Bleed (in)", "bleed_in", 0.01)}
                  {numField("Margin (in)", "margin_in", 0.01)}
                  {numField("Target DPI", "target_dpi", 50)}
                </div>
              </div>
            </div>
          </div>
          <DialogFooter className="mt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={update.isPending}>
              {update.isPending ? "Saving…" : "Save Style Guide"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Add Page Dialog ────────────────────────────────────────────────────────────

function AddPageDialog({
  open,
  onClose,
  bookId,
  nextOrder,
}: {
  open: boolean
  onClose: () => void
  bookId: string
  nextOrder: number
}) {
  const createPage = useCreatePage(bookId)
  const navigate = useNavigate()
  const [concept, setConcept] = React.useState("")

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!concept.trim()) return
    try {
      const page = await createPage.mutateAsync({ concept, sort_order: nextOrder })
      toast.success("Page added.")
      onClose()
      setConcept("")
      navigate(`/editor/${page.id}`)
    } catch (err) {
      toast.error(String(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Page</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div>
            <label className="mb-1 block text-[12px] font-medium text-[var(--foreground)]">
              Page Concept *
            </label>
            <textarea
              rows={3}
              placeholder="e.g. A mandala with lotus flowers and geometric patterns"
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              className="w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={createPage.isPending || !concept.trim()}>
              {createPage.isPending ? "Adding…" : "Add Page"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Page Grid ──────────────────────────────────────────────────────────────────

function PageGrid({
  bookId,
  filterStatus,
}: {
  bookId: string
  filterStatus: PageStatus | "all"
}) {
  const { data: pages, isLoading, isError } = usePages(bookId)
  const navigate = useNavigate()

  const filtered = React.useMemo(() => {
    if (!pages) return []
    if (filterStatus === "all") return pages
    return pages.filter((p) => p.status === filterStatus)
  }, [pages, filterStatus])

  if (isLoading) {
    return (
      <div className="grid grid-cols-3 gap-3 xl:grid-cols-4">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} className="h-[160px] rounded-xl" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-[var(--status-red-bg)] bg-[var(--status-red-bg)] px-5 py-4 text-sm text-[var(--status-red)]">
        Failed to load pages.
      </div>
    )
  }

  if (filtered.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <span className="text-4xl">🖼</span>
        <p className="text-[13.5px] text-[var(--muted-foreground)]">
          {filterStatus === "all" ? "No pages yet. Add one above." : `No pages with status "${filterStatus}".`}
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-3 gap-3 xl:grid-cols-4">
      {filtered.map((page) => (
        <div
          key={page.id}
          onClick={() => navigate(`/editor/${page.id}`)}
          className="group relative cursor-pointer overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-card)] transition-all duration-150 hover:border-[var(--brand-accent)]/40 hover:shadow-[var(--shadow-card-md)]"
        >
          {/* Thumbnail */}
          <div className="flex h-[120px] items-center justify-center bg-[var(--muted)] text-4xl">
            {page.image_path ? (
              <img
                src={pageImageSrc(page.image_path)}
                alt={page.concept}
                className="h-full w-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
              />
            ) : (
              STATUS_EMOJI[page.status]
            )}
          </div>

          {/* Info */}
          <div className="px-3 py-2.5">
            <p className="mb-1.5 line-clamp-2 text-[11.5px] font-medium leading-snug text-[var(--foreground)]">
              {page.concept}
            </p>
            <div className="flex items-center justify-between">
              <Badge variant={STATUS_VARIANT[page.status]} dot>
                {STATUS_LABEL[page.status]}
              </Badge>
              <span className="text-[10.5px] text-[var(--text-muted)]">
                #{page.sort_order}
              </span>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── BookDetailPage ─────────────────────────────────────────────────────────────

export function BookDetailPage() {
  const { id = "" } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: book, isLoading, isError } = useBook(id)
  const { data: pages } = usePages(id)

  const [filterStatus, setFilterStatus] = React.useState<PageStatus | "all">("all")
  const [styleOpen, setStyleOpen] = React.useState(false)
  const [addOpen, setAddOpen] = React.useState(false)
  const [exporting, setExporting] = React.useState(false)

  async function handleExport() {
    setExporting(true)
    try {
      const blob = await exportBookPdf(id)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `${book?.title ?? "book"}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      toast.success("PDF exported!")
    } catch (err) {
      toast.error(String(err))
    } finally {
      setExporting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-full flex-col">
        <header className="flex shrink-0 items-center border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
          <Skeleton className="h-5 w-40" />
        </header>
        <div className="flex-1 p-6">
          <Skeleton className="mb-4 h-[80px] rounded-xl" />
          <div className="grid grid-cols-3 gap-3">
            {[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-[160px] rounded-xl" />)}
          </div>
        </div>
      </div>
    )
  }

  if (isError || !book) {
    return (
      <div className="flex min-h-full flex-col items-center justify-center p-8">
        <p className="text-[var(--status-red)]">Failed to load book.</p>
        <Button className="mt-4" variant="outline" onClick={() => navigate("/books")}>
          Back to Books
        </Button>
      </div>
    )
  }

  const statusCounts = ALL_STATUSES.reduce(
    (acc, s) => ({ ...acc, [s]: pages?.filter((p) => p.status === s).length ?? 0 }),
    {} as Record<PageStatus, number>
  )

  return (
    <div className="flex min-h-full flex-col">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button
          onClick={() => navigate("/books")}
          className="text-[13px] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          Book Projects
        </button>
        <span className="text-[var(--border)]">/</span>
        <span className="flex items-center gap-2 text-[16px] font-semibold text-[var(--foreground)]">
          {book.emoji} {book.title}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setStyleOpen(true)}>
            🎨 Style Guide
          </Button>
          <Button variant="outline" size="sm" onClick={() => navigate(`/workflow?book=${id}`)}>
            🔄 Workflow
          </Button>
          <Button variant="outline" size="sm" disabled={exporting} onClick={handleExport}>
            {exporting ? "Exporting…" : "📦 Export PDF"}
          </Button>
          <Button size="sm" onClick={() => setAddOpen(true)}>
            + Add Page
          </Button>
        </div>
      </header>

      {/* Book summary strip */}
      <div className="flex shrink-0 items-center gap-6 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex items-center gap-2 text-[12px] text-[var(--muted-foreground)]">
            <span>{book.theme || "—"}</span>
            {book.audience && <><span>·</span><span>{book.audience}</span></>}
          </div>
          <ProgressBar value={book.progress_pct} />
        </div>
        <div className="flex shrink-0 gap-4 text-[12px] text-[var(--muted-foreground)]">
          <span><strong className="text-[var(--foreground)]">{book.page_count}</strong> / {book.target_page_count} pages</span>
          <span><strong className="text-[var(--foreground)]">{book.approved_count}</strong> approved</span>
          <span><strong className="text-[var(--foreground)]">{book.progress_pct}%</strong></span>
        </div>
      </div>

      {/* Status filter tabs */}
      <div className="flex shrink-0 gap-1 overflow-x-auto border-b border-[var(--border)] bg-[var(--card)] px-4 py-2">
        {(["all", ...ALL_STATUSES] as const).map((s) => {
          const count = s === "all" ? (pages?.length ?? 0) : statusCounts[s as PageStatus]
          const active = filterStatus === s
          return (
            <button
              key={s}
              onClick={() => setFilterStatus(s as PageStatus | "all")}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-colors duration-100 ${
                active
                  ? "bg-[var(--brand-accent)] text-white"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {s !== "all" && STATUS_EMOJI[s as PageStatus]}
              {s === "all" ? "All" : STATUS_LABEL[s as PageStatus]}
              <span
                className={`rounded-full px-1.5 py-0.5 text-[10px] leading-none ${
                  active ? "bg-white/20 text-white" : "bg-[var(--border)] text-[var(--muted-foreground)]"
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Page grid */}
      <div className="flex-1 overflow-y-auto p-5">
        <PageGrid bookId={id} filterStatus={filterStatus} />
      </div>

      {/* Style Guide Dialog */}
      <StyleGuideDialog
        open={styleOpen}
        onClose={() => setStyleOpen(false)}
        bookId={id}
        current={book.style_guide}
      />

      {/* Add Page Dialog */}
      <AddPageDialog
        open={addOpen}
        onClose={() => setAddOpen(false)}
        bookId={id}
        nextOrder={(pages?.length ?? 0) + 1}
      />
    </div>
  )
}
