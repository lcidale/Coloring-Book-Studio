/**
 * DashboardPage — live Dashboard route matching coloring-book-studio.html mockup.
 *
 * Layout:
 *   Top: 3 stat cards (active books / pages this week / print-ready pages)
 *   Middle left: Active Book Projects list + Recently Generated Pages grid
 *   Middle right: AI Agents panel + Quick Actions + Print Readiness + Recent Activity
 */
import * as React from "react"
import { useNavigate } from "react-router-dom"
import { toast } from "sonner"

import { StatCard } from "@/components/ui/stat-card"
import { BookListItem } from "@/components/ui/book-list-item"
import { PageCard } from "@/components/ui/page-card"
import { ProgressBar } from "@/components/ui/progress"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import type { PageStatus } from "@/lib/api"
import {
  useDashboardStats,
  useDashboardActivity,
  useDashboardAgents,
  usePrintReadiness,
  useBooks,
} from "@/lib/api"

// ── Helpers ────────────────────────────────────────────────────────────────────

function activityDotColor(kind: string): string {
  switch (kind) {
    case "approved":  return "bg-[var(--status-green)]"
    case "generated": return "bg-[var(--status-purple)]"
    case "flagged":   return "bg-[var(--status-red)]"
    case "exported":  return "bg-[var(--status-gray)]"
    default:          return "bg-[var(--status-blue)]"
  }
}

function bookBadgeVariant(pct: number): React.ComponentProps<typeof Badge>["variant"] {
  if (pct >= 80) return "green"
  if (pct >= 40) return "blue"
  if (pct >= 10) return "yellow"
  return "gray"
}

function bookBadgeLabel(pct: number): string {
  if (pct >= 80) return "In Production"
  if (pct >= 40) return "In Progress"
  if (pct >= 10) return "Needs Review"
  return "Draft"
}

// ── Section header ─────────────────────────────────────────────────────────────

function SectionHeader({
  title,
  linkLabel,
  onLink,
}: {
  title: string
  linkLabel?: string
  onLink?: () => void
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h2 className="text-[14px] font-semibold text-[var(--foreground)]">{title}</h2>
      {linkLabel && (
        <button
          onClick={onLink}
          className="text-[12px] font-medium text-[var(--brand-accent)] hover:underline focus-visible:outline-2 focus-visible:outline-[var(--ring)]"
        >
          {linkLabel}
        </button>
      )}
    </div>
  )
}

// ── Card wrapper ───────────────────────────────────────────────────────────────

function PanelCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`overflow-hidden rounded-[10px] border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-card)] ${className}`}
    >
      {children}
    </div>
  )
}

// ── Loading skeleton ───────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-[var(--border)] ${className}`}
    />
  )
}

// ── Error state ────────────────────────────────────────────────────────────────

function ErrorMsg({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-[var(--status-red-bg)] bg-[var(--status-red-bg)] px-4 py-3 text-sm text-[var(--status-red)]">
      {message}
    </p>
  )
}

// ── Stat Cards row ─────────────────────────────────────────────────────────────

function StatsRow() {
  const { data, isLoading, isError } = useDashboardStats()

  if (isLoading) {
    return (
      <div className="mb-6 grid grid-cols-3 gap-4">
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-[90px]" />)}
      </div>
    )
  }
  if (isError || !data) {
    return <ErrorMsg message="Could not load dashboard stats." />
  }

  return (
    <div className="mb-6 grid grid-cols-3 gap-4">
      <StatCard
        label="Active Books"
        value={data.active_books}
        sub="Total book projects"
      />
      <StatCard
        label="Pages This Week"
        value={data.pages_this_week}
        sub={
          <span>
            <span className="font-semibold text-[var(--status-green)]">
              {data.pages_this_week > 0 ? `↑ ${data.pages_this_week}` : "0"}
            </span>{" "}
            generated this week
          </span>
        }
      />
      <StatCard
        label="Print-Ready Pages"
        value={data.print_ready_pages}
        sub="Across all projects"
      />
    </div>
  )
}

// ── Active Books panel ─────────────────────────────────────────────────────────

function ActiveBooksPanel({ onViewAll }: { onViewAll: () => void }) {
  const { data, isLoading, isError } = useBooks()
  const navigate = useNavigate()

  return (
    <div className="mb-5">
      <SectionHeader title="Active Book Projects" linkLabel="View All" onLink={onViewAll} />
      <PanelCard>
        {isLoading && (
          <div className="divide-y divide-[var(--border)]">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3.5 px-4 py-3.5">
                <Skeleton className="h-[54px] w-[42px] shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-2/3" />
                  <Skeleton className="h-2.5 w-1/3" />
                </div>
                <Skeleton className="h-1 w-20" />
              </div>
            ))}
          </div>
        )}
        {isError && <p className="px-4 py-6 text-sm text-[var(--muted-foreground)]">Failed to load books.</p>}
        {data && data.length === 0 && (
          <p className="px-4 py-6 text-sm text-[var(--muted-foreground)]">
            No book projects yet.{" "}
            <button
              className="text-[var(--brand-accent)] underline"
              onClick={() => navigate("/books")}
            >
              Create your first book
            </button>
          </p>
        )}
        {data &&
          data.slice(0, 5).map((book) => (
            <BookListItem
              key={book.id}
              thumb={book.emoji}
              thumbBg="#fef3c7"
              thumbColor="#92400e"
              title={book.title}
              badgeVariant={bookBadgeVariant(book.progress_pct)}
              badgeLabel={bookBadgeLabel(book.progress_pct)}
              meta={`${book.page_count} / ${book.target_page_count} pages`}
              progress={book.progress_pct}
              onClick={() => navigate(`/books/${book.id}`)}
            />
          ))}
      </PanelCard>
    </div>
  )
}

// ── Recent Pages panel ─────────────────────────────────────────────────────────

function RecentPagesPanel({ onViewAll }: { onViewAll: () => void }) {
  const { data: books } = useBooks()
  // Gather recent pages from books that have pages
  // We flatten across books and take the first 8 to show in grid
  const recentPages = React.useMemo(() => {
    if (!books) return []
    // Create mock recent pages from available books data
    // (Real recent pages would come from a dedicated endpoint)
    return books.slice(0, 4).map((b, i) => ({
      id: b.id + "-page",
      name: b.title,
      status: (["generated", "review", "approved", "print_ready"] as PageStatus[])[i % 4],
      thumb: b.emoji,
    }))
  }, [books])

  return (
    <div>
      <SectionHeader title="Recently Generated Pages" linkLabel="View All" onLink={onViewAll} />
      {recentPages.length === 0 ? (
        <PanelCard>
          <p className="px-4 py-6 text-sm text-[var(--muted-foreground)]">
            No pages generated yet.
          </p>
        </PanelCard>
      ) : (
        <div className="grid grid-cols-4 gap-2.5">
          {recentPages.map((p) => (
            <PageCard
              key={p.id}
              name={p.name}
              status={p.status}
              thumb={p.thumb}
              thumbBg="var(--muted)"
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── AI Agents panel ────────────────────────────────────────────────────────────

function AgentsPanel() {
  const { data, isLoading } = useDashboardAgents()

  return (
    <div>
      <SectionHeader title="AI Agents" />
      <PanelCard>
        {isLoading && (
          <div className="divide-y divide-[var(--border)]">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                <Skeleton className="size-[34px] shrink-0 rounded-lg" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3 w-1/2" />
                  <Skeleton className="h-2.5 w-3/4" />
                </div>
              </div>
            ))}
          </div>
        )}
        {data &&
          data.map((agent) => (
            <div
              key={agent.name}
              className="flex cursor-pointer items-center gap-3 border-b border-[var(--border)] px-4 py-2.5 last:border-b-0 hover:bg-[var(--background)] transition-colors duration-100"
            >
              <div className="flex size-[34px] shrink-0 items-center justify-center rounded-lg bg-[var(--accent-light)] text-base">
                {agent.icon}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-semibold text-[var(--foreground)]">{agent.name}</p>
                <p className="text-[11.5px] text-[var(--muted-foreground)]">{agent.description}</p>
              </div>
              <span className="shrink-0 text-[11px] text-[var(--text-muted)]">{agent.status}</span>
            </div>
          ))}
      </PanelCard>
    </div>
  )
}

// ── Quick Actions panel ────────────────────────────────────────────────────────

const QUICK_ACTIONS = [
  { icon: "📖", label: "New Book", route: "/books/new" },
  { icon: "🖼", label: "Generate Page", route: "/editor" },
  { icon: "✅", label: "Quality Check", route: "/quality" },
  { icon: "📦", label: "Export PDF", route: "/export" },
]

function QuickActionsPanel() {
  const navigate = useNavigate()
  return (
    <div>
      <SectionHeader title="Quick Actions" />
      <PanelCard>
        <div className="grid grid-cols-2 gap-2 p-3.5">
          {QUICK_ACTIONS.map((a) => (
            <button
              key={a.label}
              onClick={() => navigate(a.route)}
              className="flex flex-col items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--background)] px-2.5 py-3 text-center transition-all duration-150 hover:border-[var(--brand-accent)] hover:bg-[var(--accent-light)] focus-visible:outline-2 focus-visible:outline-[var(--ring)]"
            >
              <span className="text-xl">{a.icon}</span>
              <span className="text-[11.5px] font-medium leading-tight text-[var(--muted-foreground)]">
                {a.label}
              </span>
            </button>
          ))}
        </div>
      </PanelCard>
    </div>
  )
}

// ── Print Readiness panel ──────────────────────────────────────────────────────

function PrintReadinessPanel() {
  const { data, isLoading } = usePrintReadiness()

  return (
    <div>
      <SectionHeader title="Print Readiness" />
      <PanelCard>
        {isLoading && (
          <div className="space-y-3 p-4">
            {[0, 1].map((i) => <Skeleton key={i} className="h-8" />)}
          </div>
        )}
        {data && data.length === 0 && (
          <p className="px-4 py-4 text-sm text-[var(--muted-foreground)]">No books with pages yet.</p>
        )}
        {data && data.length > 0 && (
          <div className="divide-y divide-[var(--border)]">
            {data.slice(0, 5).map((row) => {
              const pct = row.total_count > 0
                ? Math.round((row.ready_count / row.total_count) * 100)
                : 0
              return (
                <div key={row.book_id} className="px-4 py-3">
                  <div className="mb-1.5 flex items-center justify-between">
                    <p className="truncate text-[12.5px] font-medium text-[var(--foreground)]">
                      {row.title}
                    </p>
                    <span className="ml-2 shrink-0 text-[11px] text-[var(--text-muted)]">
                      {row.ready_count}/{row.total_count}
                    </span>
                  </div>
                  <ProgressBar value={pct} />
                </div>
              )
            })}
          </div>
        )}
      </PanelCard>
    </div>
  )
}

// ── Recent Activity panel ──────────────────────────────────────────────────────

function ActivityPanel() {
  const { data, isLoading } = useDashboardActivity(8)

  return (
    <div>
      <SectionHeader title="Recent Activity" />
      <PanelCard>
        {isLoading && (
          <div className="divide-y divide-[var(--border)]">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex items-start gap-3 px-4 py-2.5">
                <Skeleton className="mt-1 size-[6px] shrink-0 rounded-full" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-3 w-3/4" />
                  <Skeleton className="h-2.5 w-1/4" />
                </div>
              </div>
            ))}
          </div>
        )}
        {data && data.length === 0 && (
          <p className="px-4 py-4 text-sm text-[var(--muted-foreground)]">No recent activity.</p>
        )}
        {data &&
          data.map((item, i) => (
            <div
              key={i}
              className="flex items-start gap-3 border-b border-[var(--border)] px-4 py-2.5 last:border-b-0"
            >
              <span
                className={`mt-[6px] inline-block size-[6px] shrink-0 rounded-full ${activityDotColor(item.kind)}`}
              />
              <div className="flex-1 min-w-0">
                <p className="text-[12.5px] text-[var(--foreground)]">{item.text}</p>
                <p className="text-[11px] text-[var(--text-muted)]">{item.when}</p>
              </div>
            </div>
          ))}
      </PanelCard>
    </div>
  )
}

// ── DashboardPage ──────────────────────────────────────────────────────────────

export function DashboardPage() {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-full flex-col">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <div>
          <h1 className="text-[16px] font-semibold text-[var(--foreground)]">Dashboard</h1>
          <p className="text-[13px] text-[var(--text-muted)]">Welcome back — here's your studio at a glance.</p>
        </div>
        <div className="ml-auto flex gap-2">
          <Button variant="outline" size="sm" onClick={() => navigate("/books")}>
            Book Projects
          </Button>
          <Button size="sm" onClick={() => { toast.info("Opening new book…"); navigate("/books/new") }}>
            + New Book
          </Button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* Stat cards */}
        <StatsRow />

        {/* Two-column layout */}
        <div className="grid grid-cols-[1fr_320px] gap-5">
          {/* Left column */}
          <div className="min-w-0">
            <ActiveBooksPanel onViewAll={() => navigate("/books")} />
            <RecentPagesPanel onViewAll={() => navigate("/editor")} />
          </div>

          {/* Right column */}
          <div className="flex flex-col gap-5">
            <AgentsPanel />
            <QuickActionsPanel />
            <PrintReadinessPanel />
            <ActivityPanel />
          </div>
        </div>
      </div>
    </div>
  )
}
