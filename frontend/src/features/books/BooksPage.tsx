/**
 * BooksPage — /books route. Lists all book projects with progress,
 * and provides a "New Book" dialog to create one.
 *
 * Each card has a ⋯ menu with Rename and Delete actions.
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
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "@/components/ui/alert-dialog"
import {
  useBooks,
  useCreateBook,
  useUpdateBook,
  useDeleteBook,
  type CreateBookInput,
  type Book,
} from "@/lib/api"

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

// ── Book Form Fields (shared by New + Rename dialogs) ─────────────────────────

interface BookFormState {
  title: string
  emoji: string
  theme: string
  audience: string
  positioning: string
  target_page_count: number
}

function bookFormDefaults(): BookFormState {
  return {
    title: "",
    emoji: "📖",
    theme: "",
    audience: "",
    positioning: "",
    target_page_count: 32,
  }
}

function bookFormFromBook(book: Book): BookFormState {
  return {
    title: book.title,
    emoji: book.emoji ?? "📖",
    theme: book.theme ?? "",
    audience: book.audience ?? "",
    positioning: book.positioning ?? "",
    target_page_count: book.target_page_count ?? 32,
  }
}

interface BookFormFieldsProps {
  form: BookFormState
  setForm: React.Dispatch<React.SetStateAction<BookFormState>>
}

function BookFormFields({ form, setForm }: BookFormFieldsProps) {
  function field(
    label: string,
    key: keyof BookFormState,
    placeholder: string,
    type: "text" | "number" = "text",
  ) {
    return (
      <div>
        <label
          className="mb-1 block text-[12px] font-medium text-[var(--foreground)]"
          htmlFor={`book-field-${key}`}
        >
          {label}
        </label>
        <input
          id={`book-field-${key}`}
          aria-label={label.replace(" *", "")}
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
    <>
      <div className="grid grid-cols-[56px_1fr] gap-2">
        <div>
          <label
            className="mb-1 block text-[12px] font-medium text-[var(--foreground)]"
            htmlFor="book-field-emoji"
          >
            Emoji
          </label>
          <input
            id="book-field-emoji"
            type="text"
            maxLength={2}
            value={form.emoji ?? ""}
            onChange={(e) => setForm((f) => ({ ...f, emoji: e.target.value }))}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-2 py-2 text-center text-xl outline-none focus:border-[var(--brand-accent)]"
          />
        </div>
        <div>{field("Title *", "title", "e.g. Peaceful Gardens")}</div>
      </div>
      {field("Theme", "theme", "e.g. botanical, fantasy landscapes")}
      {field("Target Audience", "audience", "e.g. adult relaxation")}
      {field("Positioning", "positioning", "e.g. beginner-friendly stress relief")}
      {field("Target Page Count", "target_page_count", "32", "number")}
    </>
  )
}

// ── New Book Dialog ────────────────────────────────────────────────────────────

interface NewBookDialogProps {
  open: boolean
  onClose: () => void
}

function NewBookDialog({ open, onClose }: NewBookDialogProps) {
  const createBook = useCreateBook()
  const navigate = useNavigate()
  const [form, setForm] = React.useState<BookFormState>(bookFormDefaults())

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.title.trim()) return
    try {
      const input: CreateBookInput = {
        title: form.title,
        emoji: form.emoji,
        theme: form.theme,
        audience: form.audience,
        positioning: form.positioning,
        target_page_count: form.target_page_count,
      }
      const book = await createBook.mutateAsync(input)
      toast.success(`Book "${book.title}" created!`)
      onClose()
      navigate(`/books/${book.id}`)
    } catch (err) {
      toast.error(String(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Book Project</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <BookFormFields form={form} setForm={setForm} />
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

// ── Rename Book Dialog ─────────────────────────────────────────────────────────

interface RenameBookDialogProps {
  book: Book | null
  onClose: () => void
}

function RenameBookDialog({ book, onClose }: RenameBookDialogProps) {
  const updateBook = useUpdateBook()
  const [form, setForm] = React.useState<BookFormState>(bookFormDefaults())

  // Sync form whenever the book changes (i.e. when dialog opens for a new book)
  React.useEffect(() => {
    if (book) setForm(bookFormFromBook(book))
  }, [book])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!book || !form.title.trim()) return
    try {
      await updateBook.mutateAsync({
        id: book.id,
        title: form.title,
        emoji: form.emoji,
        theme: form.theme,
        audience: form.audience,
        positioning: form.positioning,
        target_page_count: form.target_page_count,
      })
      toast.success(`Book renamed to "${form.title}"`)
      onClose()
    } catch (err) {
      toast.error(String(err))
    }
  }

  return (
    <Dialog open={!!book} onOpenChange={(v) => { if (!v) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Rename Book</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <BookFormFields form={form} setForm={setForm} />
          <DialogFooter className="mt-2">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={updateBook.isPending || !form.title.trim()}>
              {updateBook.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ── Delete Book Confirm ────────────────────────────────────────────────────────

interface DeleteBookDialogProps {
  book: Book | null
  onClose: () => void
}

function DeleteBookDialog({ book, onClose }: DeleteBookDialogProps) {
  const deleteBook = useDeleteBook()

  async function handleConfirm() {
    if (!book) return
    try {
      await deleteBook.mutateAsync(book.id)
      toast.success(`"${book.title}" deleted.`)
      onClose()
    } catch (err) {
      toast.error(String(err))
    }
  }

  return (
    <AlertDialog open={!!book} onOpenChange={(v) => { if (!v) onClose() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete &ldquo;{book?.title}&rdquo;?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently removes the book and all its pages and versions. This
            action cannot be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onClose}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleConfirm} disabled={deleteBook.isPending}>
            {deleteBook.isPending ? "Deleting…" : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

// ── BooksPage ──────────────────────────────────────────────────────────────────

export function BooksPage() {
  const { data: books, isLoading, isError } = useBooks()
  const navigate = useNavigate()
  const [newOpen, setNewOpen] = React.useState(false)
  const [editingBook, setEditingBook] = React.useState<Book | null>(null)
  const [deletingBook, setDeletingBook] = React.useState<Book | null>(null)

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
                className="relative flex cursor-pointer items-center gap-4 rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4 shadow-[var(--shadow-card)] transition-all duration-150 hover:border-[var(--brand-accent)]/40 hover:shadow-[var(--shadow-card-md)]"
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
                    {[book.theme, book.audience, book.positioning].filter(Boolean).join(" · ") ||
                      "No description"}
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

                {/* ⋯ Actions menu */}
                <DropdownMenu>
                  <DropdownMenuTrigger
                    aria-label={`Book actions for ${book.title}`}
                    onClick={(e) => e.stopPropagation()}
                    className="ml-1 flex size-7 items-center justify-center rounded-md text-[var(--muted-foreground)] hover:bg-[var(--accent)] hover:text-[var(--foreground)] focus-visible:outline-none"
                  >
                    ⋯
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <DropdownMenuItem
                      onSelect={() => setEditingBook(book)}
                    >
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onSelect={() => setDeletingBook(book)}
                      className="text-red-600 focus:text-red-600"
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))}
          </div>
        )}
      </div>

      <NewBookDialog open={newOpen} onClose={() => setNewOpen(false)} />
      <RenameBookDialog book={editingBook} onClose={() => setEditingBook(null)} />
      <DeleteBookDialog book={deletingBook} onClose={() => setDeletingBook(null)} />
    </div>
  )
}

export default BooksPage
