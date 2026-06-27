/**
 * BooksPage — /books route. Lists all book projects with progress,
 * and provides a "New Book" dialog to create one.
 */
import * as React from "react"
import { useNavigate } from "react-router-dom"
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
import { useBooks, useCreateBook, type CreateBookInput } from "@/lib/api"

// ── Helpers ────────────────────────────────────────────────────────────────────

function statusVariant(pct: number): React.ComponentProps<typeof Badge>["variant"] {
  if (pct >= 80) return "green"
  if (pct >= 40) return "blue"
  if (pct >= 10) return "yellow"
  return "gray"
}

function statusLabel(pct: number): string {
  if (pct >= 80) return "In Production"
  if (pct >= 40) return "In Progress"
  if (pct >= 10) return "Needs Review"
  return "Draft"
}

// ── Skeleton ───────────────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)] ${className}`} />
}

// ── New Book Dialog ────────────────────────────────────────────────────────────

interface NewBookDialogProps {
  open: boolean
  onClose: () => void
}

function NewBookDialog({ open, onClose }: NewBookDialogProps) {
  const createBook = useCreateBook()
  const navigate = useNavigate()
  const [form, setForm] = React.useState<CreateBookInput>({
    title: "",
    emoji: "📖",
    theme: "",
    audience: "",
    positioning: "",
    target_page_count: 32,
  })

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.title.trim()) return
    try {
      const book = await createBook.mutateAsync(form)
      toast.success(`Book "${book.title}" created!`)
      onClose()
      navigate(`/books/${book.id}`)
    } catch (err) {
      toast.error(String(err))
    }
  }

  function field(
    label: string,
    key: keyof CreateBookInput,
    placeholder: string,
    type: "text" | "number" = "text"
  ) {
    return (
      <div>
        <label className="mb-1 block text-[12px] font-medium text-[var(--foreground)]">
          {label}
        </label>
        <input
          type={type}
          placeholder={placeholder}
          value={String(form[key] ?? "")}
          onChange={(e) =>
            setForm((f) => ({
              ...f,
              [key]: type === "number" ? Number(e.target.value) : e.target.value,
            }))
          }
          className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
        />
      </div>
    )
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Book Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="grid grid-cols-[56px_1fr] gap-2">
            <div>
              <label className="mb-1 block text-[12px] font-medium text-[var(--foreground)]">
                Emoji
              </label>
              <input
                type="text"
                maxLength={2}
                value={form.emoji ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, emoji: e.target.value }))}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-2 text-center text-xl outline-none focus:border-[var(--brand-accent)]"
              />
            </div>
            <div>
              {field("Title *", "title", "e.g. Peaceful Gardens")}
            </div>
          </div>
          {field("Theme", "theme", "e.g. botanical, fantasy landscapes")}
          {field("Target Audience", "audience", "e.g. adult relaxation")}
          {field("Positioning", "positioning", "e.g. beginner-friendly stress relief")}
          {field("Target Page Count", "target_page_count", "32", "number")}

          <DialogFooter className="mt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={createBook.isPending || !form.title.trim()}>
              {createBook.isPending ? "Creating…" : "Create Book"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── BooksPage ──────────────────────────────────────────────────────────────────

export function BooksPage() {
  const { data: books, isLoading, isError } = useBooks()
  const navigate = useNavigate()
  const [newOpen, setNewOpen] = React.useState(false)

  return (
    <div className="flex min-h-full flex-col">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <div>
          <h1 className="text-[16px] font-semibold text-[var(--foreground)]">Book Projects</h1>
          <p className="text-[13px] text-[var(--text-muted)]">
            {books ? `${books.length} book${books.length !== 1 ? "s" : ""}` : "Loading…"}
          </p>
        </div>
        <div className="ml-auto">
          <Button size="sm" onClick={() => setNewOpen(true)}>
            + New Book
          </Button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading && (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-[88px] rounded-xl" />
            ))}
          </div>
        )}
        {isError && (
          <div className="rounded-xl border border-[var(--status-red-bg)] bg-[var(--status-red-bg)] px-5 py-4 text-sm text-[var(--status-red)]">
            Failed to load books.
          </div>
        )}
        {books && books.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
            <span className="text-5xl">📖</span>
            <div>
              <p className="text-[15px] font-semibold text-[var(--foreground)]">No books yet</p>
              <p className="mt-1 text-[13px] text-[var(--muted-foreground)]">
                Create your first coloring book project to get started.
              </p>
            </div>
            <Button onClick={() => setNewOpen(true)}>+ New Book</Button>
          </div>
        )}
        {books && books.length > 0 && (
          <div className="flex flex-col gap-3">
            {books.map((book) => (
              <div
                key={book.id}
                onClick={() => navigate(`/books/${book.id}`)}
                className="flex cursor-pointer items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 shadow-[var(--shadow-card)] transition-all duration-150 hover:border-[var(--brand-accent)]/40 hover:shadow-[var(--shadow-card-md)]"
              >
                {/* Cover thumb */}
                <div className="flex size-[54px] shrink-0 items-center justify-center rounded-lg bg-amber-50 text-2xl">
                  {book.emoji || "📖"}
                </div>

                {/* Info */}
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <p className="truncate text-[14px] font-semibold text-[var(--foreground)]">
                      {book.title}
                    </p>
                    <Badge variant={statusVariant(book.progress_pct)} dot>
                      {statusLabel(book.progress_pct)}
                    </Badge>
                  </div>
                  <p className="mb-2 truncate text-[12.5px] text-[var(--muted-foreground)]">
                    {[book.theme, book.audience, book.positioning].filter(Boolean).join(" · ") || "No description"}
                  </p>
                  <div className="flex items-center gap-3">
                    <div className="flex-1">
                      <ProgressBar value={book.progress_pct} />
                    </div>
                    <span className="shrink-0 text-[11.5px] text-[var(--text-muted)]">
                      {book.page_count} / {book.target_page_count} pages
                    </span>
                    <span className="shrink-0 text-[11.5px] text-[var(--text-muted)]">
                      {book.approved_count} approved
                    </span>
                  </div>
                </div>

                {/* Chevron */}
                <span className="ml-2 text-[var(--muted-foreground)]">›</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <NewBookDialog open={newOpen} onClose={() => setNewOpen(false)} />
    </div>
  )
}
