/**
 * PageEditorPage — /editor/:pageId route.
 * Full page editing view: image preview, status track, generate button,
 * approve/revise/print-ready actions, text layers, and export PDF.
 */
import * as React from "react"
import { useParams, useNavigate, useSearchParams } from "react-router-dom"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  usePage,
  useBook,
  useUpdatePage,
  useGeneratePage,
  useJob,
  exportBookPdf,
  useCreateTextLayer,
  useDeleteTextLayer,
  type PageStatus,
} from "@/lib/api"

// ── Constants ──────────────────────────────────────────────────────────────────

const ALL_STATUSES: PageStatus[] = [
  "idea", "prompt", "generated", "review", "revision", "approved", "print_ready", "exported",
]

const STATUS_EMOJI: Record<PageStatus, string> = {
  idea: "💭", prompt: "✏️", generated: "🖼", review: "🔍",
  revision: "🔄", approved: "👍", print_ready: "🖨", exported: "📦",
}

const STATUS_LABEL: Record<PageStatus, string> = {
  idea: "Idea", prompt: "Prompt", generated: "Generated", review: "Needs Review",
  revision: "Needs Revision", approved: "Approved", print_ready: "Print Ready", exported: "Exported",
}

const STATUS_VARIANT: Record<PageStatus, React.ComponentProps<typeof Badge>["variant"]> = {
  idea: "gray", prompt: "yellow", generated: "purple", review: "blue",
  revision: "red", approved: "green", print_ready: "green", exported: "gray",
}

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)] ${className}`} />
}

// ── Status Track ───────────────────────────────────────────────────────────────

function StatusTrack({ current }: { current: PageStatus }) {
  const idx = ALL_STATUSES.indexOf(current)
  return (
    <div className="flex items-center gap-0 overflow-x-auto">
      {ALL_STATUSES.map((s, i) => {
        const done = i < idx
        const active = i === idx
        return (
          <React.Fragment key={s}>
            <div className="flex flex-col items-center gap-1">
              <div
                className={`flex size-9 items-center justify-center rounded-full border-2 text-sm transition-all ${
                  active
                    ? "border-[var(--brand-accent)] bg-[var(--brand-accent)] text-white"
                    : done
                    ? "border-[var(--status-green)] bg-[var(--status-green-bg)] text-[var(--status-green)]"
                    : "border-[var(--border)] bg-[var(--card)] text-[var(--muted-foreground)]"
                }`}
              >
                {STATUS_EMOJI[s]}
              </div>
              <span
                className={`whitespace-nowrap text-[10px] font-medium ${
                  active ? "text-[var(--brand-accent)]" : done ? "text-[var(--status-green)]" : "text-[var(--text-muted)]"
                }`}
              >
                {s === "print_ready" ? "Print Ready" : STATUS_LABEL[s]}
              </span>
            </div>
            {i < ALL_STATUSES.length - 1 && (
              <div
                className={`mb-5 h-[2px] w-6 shrink-0 ${
                  i < idx ? "bg-[var(--status-green)]" : "bg-[var(--border)]"
                }`}
              />
            )}
          </React.Fragment>
        )
      })}
    </div>
  )
}

// ── Generate Button + Job Polling ──────────────────────────────────────────────

function GenerateSection({ pageId }: { pageId: string }) {
  const generate = useGeneratePage()
  const [activeJobId, setActiveJobId] = React.useState<string | null>(null)
  const { data: job } = useJob(activeJobId)
  const updatePage = useUpdatePage()

  React.useEffect(() => {
    if (job?.status === "done") {
      toast.success("Generation complete!")
      setActiveJobId(null)
      void updatePage.mutateAsync({ id: pageId, status: "review" })
    } else if (job?.status === "failed") {
      toast.error(`Generation failed: ${job.error ?? "unknown error"}`)
      setActiveJobId(null)
    }
  }, [job?.status]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleGenerate() {
    try {
      const j = await generate.mutateAsync({ pageId, options: { auto_cleanup: true, vectorize: false } })
      setActiveJobId(j.job_id)
      toast.info("Generation queued…")
    } catch (err) {
      toast.error(String(err))
    }
  }

  const isRunning = generate.isPending || (job?.status === "queued" || job?.status === "running")
  const statusText = job?.status === "queued"
    ? "Queued…"
    : job?.status === "running"
    ? "Generating…"
    : "Generate Image"

  return (
    <div className="flex items-center gap-2">
      <Button
        onClick={handleGenerate}
        disabled={isRunning}
        className="gap-2"
      >
        {isRunning && (
          <span className="inline-block size-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        )}
        {isRunning ? statusText : "🖼 Generate Image"}
      </Button>
      {job && job.status === "running" && (
        <span className="text-[12px] text-[var(--muted-foreground)]">
          Job {job.job_id.slice(0, 8)}…
        </span>
      )}
    </div>
  )
}

// ── Image Preview ──────────────────────────────────────────────────────────────

function ImagePreview({ imagePath, concept }: { imagePath: string | null; concept: string }) {
  if (!imagePath) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed border-[var(--border)] bg-[var(--muted)]">
        <span className="text-5xl opacity-30">🖼</span>
        <p className="text-[13px] text-[var(--muted-foreground)]">No image generated yet</p>
      </div>
    )
  }

  return (
    <div className="flex h-full items-center justify-center overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--muted)]">
      <img
        src={`/storage/${imagePath}`}
        alt={concept}
        className="max-h-full max-w-full object-contain"
      />
    </div>
  )
}

// ── Text Layers Panel ──────────────────────────────────────────────────────────

function TextLayersPanel({ pageId }: { pageId: string }) {
  const { data: page, isLoading } = usePage(pageId)
  const createLayer = useCreateTextLayer(pageId)
  const deleteLayer = useDeleteTextLayer(pageId)
  const [newText, setNewText] = React.useState("")

  async function handleAdd() {
    if (!newText.trim()) return
    try {
      await createLayer.mutateAsync({ content: newText, x_pct: 50, y_pct: 90 })
      setNewText("")
      toast.success("Text layer added.")
    } catch (err) {
      toast.error(String(err))
    }
  }

  async function handleDelete(layerId: string) {
    try {
      await deleteLayer.mutateAsync(layerId)
      toast.success("Text layer removed.")
    } catch (err) {
      toast.error(String(err))
    }
  }

  if (isLoading) return <Skeleton className="h-20" />

  const layers = page?.text_layers ?? []

  return (
    <div>
      <p className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
        Text Layers
      </p>
      <div className="mb-2 flex gap-2">
        <input
          type="text"
          placeholder="Add text (e.g. page title)"
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void handleAdd() }}
          className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-[13px] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:border-[var(--brand-accent)]"
        />
        <Button size="sm" variant="outline" onClick={handleAdd} disabled={createLayer.isPending || !newText.trim()}>
          Add
        </Button>
      </div>
      {layers.length === 0 ? (
        <p className="text-[12px] text-[var(--text-muted)]">No text layers.</p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {layers.map((layer) => (
            <div
              key={layer.id}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2"
            >
              <span className="flex-1 text-[12.5px] text-[var(--foreground)]">{layer.content}</span>
              <span className="text-[11px] text-[var(--text-muted)]">
                {layer.x_pct}%, {layer.y_pct}%
              </span>
              <button
                onClick={() => void handleDelete(layer.id)}
                className="text-[var(--text-muted)] hover:text-[var(--status-red)]"
                aria-label="Delete layer"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── PageEditorPage ─────────────────────────────────────────────────────────────

export function PageEditorPage() {
  const { pageId = "" } = useParams<{ pageId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const { data: page, isLoading, isError } = usePage(pageId)
  const { data: book } = useBook(page?.book_id ?? "")
  const updatePage = useUpdatePage()
  const [exporting, setExporting] = React.useState(false)

  // Prompt edit state
  const [editingPrompt, setEditingPrompt] = React.useState(false)
  const [promptDraft, setPromptDraft] = React.useState("")

  React.useEffect(() => {
    if (page?.prompt) setPromptDraft(page.prompt)
  }, [page?.prompt])

  async function setStatus(status: PageStatus) {
    try {
      await updatePage.mutateAsync({ id: pageId, status })
      toast.success(`Status → ${STATUS_LABEL[status]}`)
    } catch (err) {
      toast.error(String(err))
    }
  }

  async function savePrompt() {
    try {
      await updatePage.mutateAsync({ id: pageId, prompt: promptDraft })
      setEditingPrompt(false)
      toast.success("Prompt saved.")
    } catch (err) {
      toast.error(String(err))
    }
  }

  async function handleExport() {
    if (!page?.book_id) return
    setExporting(true)
    try {
      const blob = await exportBookPdf(page.book_id)
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
          <Skeleton className="h-5 w-48" />
        </header>
        <div className="flex flex-1 gap-0 overflow-hidden">
          <div className="flex-1 p-6"><Skeleton className="h-full rounded-xl" /></div>
          <div className="w-[320px] border-l border-[var(--border)] p-5">
            <Skeleton className="mb-4 h-5 w-32" />
            <Skeleton className="h-20" />
          </div>
        </div>
      </div>
    )
  }

  if (isError || !page) {
    return (
      <div className="flex min-h-full flex-col items-center justify-center p-8">
        <p className="text-[var(--status-red)]">Page not found.</p>
        <Button className="mt-4" variant="outline" onClick={() => navigate(-1)}>
          Go Back
        </Button>
      </div>
    )
  }

  const fromBook = searchParams.get("book") ?? page.book_id

  return (
    <div className="flex min-h-full flex-col">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <button
          onClick={() => navigate(`/books/${fromBook}`)}
          className="text-[13px] text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
        >
          {book?.title ?? "Book"}
        </button>
        <span className="text-[var(--border)]">/</span>
        <span className="text-[14px] font-semibold text-[var(--foreground)]">
          Page #{page.sort_order}
        </span>
        <Badge variant={STATUS_VARIANT[page.status]} dot className="ml-1">
          {STATUS_LABEL[page.status]}
        </Badge>

        <div className="ml-auto flex items-center gap-2">
          <GenerateSection pageId={pageId} />
          <Button
            variant="outline"
            size="sm"
            disabled={exporting}
            onClick={handleExport}
          >
            {exporting ? "Exporting…" : "📦 Export PDF"}
          </Button>
        </div>
      </header>

      {/* Status track */}
      <div className="flex shrink-0 items-center justify-center border-b border-[var(--border)] bg-[var(--card)] px-6 py-4">
        <StatusTrack current={page.status} />
      </div>

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: image preview */}
        <div className="min-w-0 flex-1 overflow-y-auto p-5">
          <div className="h-[min(60vh,500px)]">
            <ImagePreview imagePath={page.image_path} concept={page.concept} />
          </div>

          {/* Concept */}
          <div className="mt-4 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
              Concept
            </p>
            <p className="text-[13.5px] text-[var(--foreground)]">{page.concept}</p>
          </div>

          {/* Print check notes */}
          {page.print_check_notes && (
            <div className="mt-3 rounded-xl border border-[var(--status-yellow-bg)] bg-[var(--status-yellow-bg)] p-4">
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--status-yellow)]">
                Print Check Notes
              </p>
              <p className="text-[12.5px] text-[var(--foreground)]">{page.print_check_notes}</p>
            </div>
          )}
        </div>

        {/* Right: controls panel */}
        <div className="flex w-[300px] shrink-0 flex-col gap-5 overflow-y-auto border-l border-[var(--border)] p-5">
          {/* Approval actions */}
          <div>
            <p className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
              Actions
            </p>
            <div className="flex flex-col gap-2">
              {page.status !== "approved" && page.status !== "print_ready" && (
                <Button
                  size="sm"
                  onClick={() => void setStatus("approved")}
                  disabled={updatePage.isPending}
                  className="w-full justify-start gap-2 bg-[var(--status-green)] text-white hover:bg-[var(--status-green)]/90"
                >
                  👍 Approve
                </Button>
              )}
              {page.status !== "revision" && page.status !== "idea" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void setStatus("revision")}
                  disabled={updatePage.isPending}
                  className="w-full justify-start gap-2 border-[var(--status-red)] text-[var(--status-red)] hover:bg-[var(--status-red-bg)]"
                >
                  🔄 Request Revision
                </Button>
              )}
              {page.status === "approved" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void setStatus("print_ready")}
                  disabled={updatePage.isPending}
                  className="w-full justify-start gap-2 border-[var(--status-green)] text-[var(--status-green)]"
                >
                  🖨 Mark Print Ready
                </Button>
              )}
              {page.status === "print_ready" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void setStatus("exported")}
                  disabled={updatePage.isPending}
                  className="w-full justify-start gap-2"
                >
                  📦 Mark Exported
                </Button>
              )}
            </div>
          </div>

          {/* Prompt editor */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-[12px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                Prompt
              </p>
              {!editingPrompt && (
                <button
                  onClick={() => { setPromptDraft(page.prompt ?? ""); setEditingPrompt(true) }}
                  className="text-[11px] text-[var(--brand-accent)] hover:underline"
                >
                  Edit
                </button>
              )}
            </div>
            {editingPrompt ? (
              <div className="flex flex-col gap-2">
                <textarea
                  rows={5}
                  value={promptDraft}
                  onChange={(e) => setPromptDraft(e.target.value)}
                  className="w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[12.5px] text-[var(--foreground)] outline-none focus:border-[var(--brand-accent)]"
                />
                <div className="flex gap-2">
                  <Button size="sm" onClick={savePrompt} disabled={updatePage.isPending}>
                    Save
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setEditingPrompt(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <p className="rounded-lg border border-[var(--border)] bg-[var(--muted)] px-3 py-2 text-[12px] text-[var(--muted-foreground)] leading-relaxed min-h-[60px]">
                {page.prompt ?? "No prompt yet — generate to create one."}
              </p>
            )}
          </div>

          {/* Image metadata */}
          {page.image_dpi !== null && (
            <div>
              <p className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
                Image Info
              </p>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--muted)] px-3 py-2">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12px]">
                  <span className="text-[var(--muted-foreground)]">DPI</span>
                  <span className="text-[var(--foreground)] font-medium">{page.image_dpi}</span>
                  <span className="text-[var(--muted-foreground)]">Size</span>
                  <span className="text-[var(--foreground)] font-medium">
                    {page.image_width_px} × {page.image_height_px}px
                  </span>
                  <span className="text-[var(--muted-foreground)]">Pure B&W</span>
                  <span className={`font-medium ${page.is_pure_bw ? "text-[var(--status-green)]" : "text-[var(--status-red)]"}`}>
                    {page.is_pure_bw == null ? "—" : page.is_pure_bw ? "Yes" : "No"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Text layers */}
          <TextLayersPanel pageId={pageId} />
        </div>
      </div>
    </div>
  )
}
