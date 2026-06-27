/**
 * WorkflowPage — /workflow route.
 * Reproduces the coloring-book-workflow.html reference with:
 * - 5-phase production map (Concept → Create → Review → Refine → Publish)
 * - 8-stage page status tracker with live per-status counts from GET /books/:id/status-summary
 * - 3 principle cards
 * Book selector if ?book= param or first book.
 */
import * as React from "react"
import { useNavigate, useSearchParams } from "react-router-dom"

import { useBooks, useBookStatusSummary, type StatusSummary, type PageStatus } from "@/lib/api"

// ── Types ──────────────────────────────────────────────────────────────────────

interface PhaseStep {
  icon: string
  title: string
  desc: string
  agent: string
  agentIsHuman?: boolean
  outputs: string[]
}

interface Phase {
  id: string
  label: string
  sub: string
  color: string
  bgColor: string
  steps: PhaseStep[]
}

// ── Phase Data ─────────────────────────────────────────────────────────────────

const PHASES: Phase[] = [
  {
    id: "concept",
    label: "Concept",
    sub: "Research",
    color: "#d97706",
    bgColor: "#fef3c7",
    steps: [
      {
        icon: "💡",
        title: "Book Concept",
        desc: "Define theme, niche, emotional tone, target audience, and what makes this book distinct.",
        agent: "Concept Agent",
        outputs: ["Theme", "Audience", "Positioning"],
      },
      {
        icon: "🔍",
        title: "Market Research",
        desc: "Search existing books, identify trends, gaps, visual styles, and what sells in this niche.",
        agent: "Market Agent",
        outputs: ["Comp Set", "Gaps", "Trends"],
      },
      {
        icon: "📌",
        title: "Inspiration Library",
        desc: "Save references, covers, and style examples. Tag and link to the current book project.",
        agent: "Librarian Agent",
        outputs: ["References", "Tags"],
      },
      {
        icon: "🎨",
        title: "Style Guide",
        desc: "Lock in line weight, detail level, white space, motifs, and what to avoid. Used by every page.",
        agent: "Style Guide Agent",
        outputs: ["Style Rules", "Neg. Prompts"],
      },
    ],
  },
  {
    id: "create",
    label: "Create",
    sub: "Generate",
    color: "#7c3aed",
    bgColor: "#ede9fe",
    steps: [
      {
        icon: "✏️",
        title: "Page Concepts",
        desc: "Generate specific, colorable page ideas aligned with the book's theme and style guide.",
        agent: "Page Idea Agent",
        outputs: ["Page List", "Concepts"],
      },
      {
        icon: "🧠",
        title: "Prompt Engineering",
        desc: "Turn each concept into a detailed AI prompt: B&W, clean lines, print-ready, style-consistent.",
        agent: "Prompt Agent",
        outputs: ["Prompts", "Neg. Prompts"],
      },
      {
        icon: "🖼",
        title: "Line Art Generation",
        desc: "Generate original B&W line art. Pure black and white, no gray, clean outlines, high resolution.",
        agent: "Line Art Agent",
        outputs: ["PNG / TIF", "300+ DPI"],
      },
    ],
  },
  {
    id: "review",
    label: "Review",
    sub: "Quality Control",
    color: "#1d4ed8",
    bgColor: "#dbeafe",
    steps: [
      {
        icon: "🔍",
        title: "Page Critique",
        desc: "Check if the page is colorable, well-composed, and style-consistent. Flag issues in plain language.",
        agent: "Page Critic",
        outputs: ["Pass / Fail", "Notes"],
      },
      {
        icon: "🖨",
        title: "Print Check",
        desc: "Verify DPI, line weight, gray pixels, margins, bleed, and trim size for printshop compatibility.",
        agent: "Print Prep Agent",
        outputs: ["Spec Report", "Issues List"],
      },
      {
        icon: "👁",
        title: "Leslie Reviews",
        desc: "Final human eye. Approve, request revision, or regenerate. Your taste is the last quality gate.",
        agent: "You",
        agentIsHuman: true,
        outputs: ["Approved", "Revise", "Regen"],
      },
    ],
  },
  {
    id: "refine",
    label: "Refine",
    sub: "Fix & Edit",
    color: "#b91c1c",
    bgColor: "#fee2e2",
    steps: [
      {
        icon: "✂️",
        title: "Minor Edits",
        desc: "Fix typos, remove stray marks, adjust text, clean up edges — without redoing the full image.",
        agent: "You + Tools",
        agentIsHuman: true,
        outputs: ["Edited PNG", "Clean File"],
      },
      {
        icon: "🔄",
        title: "Revision Agent",
        desc: "AI-assisted fixes: thicken lines, add white space, simplify clutter, create alternate versions.",
        agent: "Revision Agent",
        outputs: ["Revised PNG", "Variants"],
      },
      {
        icon: "↩️",
        title: "Regenerate",
        desc: "If revision isn't enough, regenerate with an improved prompt. Version history is preserved.",
        agent: "Line Art Agent",
        outputs: ["New Version", "History"],
      },
    ],
  },
  {
    id: "publish",
    label: "Publish",
    sub: "Export & Ship",
    color: "#15803d",
    bgColor: "#dcfce7",
    steps: [
      {
        icon: "📐",
        title: "Book Assembly",
        desc: "Set page order, front/back matter, section flow, blank backs, and book structure.",
        agent: "Assembly Agent",
        outputs: ["Page Order", "Structure"],
      },
      {
        icon: "✅",
        title: "Final QC Pass",
        desc: "Full book check: no duplicates, consistent style, no thin lines, all pages print-ready.",
        agent: "QC Agent",
        outputs: ["QC Report", "Issue Log"],
      },
      {
        icon: "📦",
        title: "Export & Ship",
        desc: "Export print-ready PDF for printshop, KDP interior, Etsy digital, or Gumroad bundle.",
        agent: "Export Agent",
        outputs: ["PDF", "KDP Ready", "ZIP"],
      },
    ],
  },
]

// ── Status Track Data ──────────────────────────────────────────────────────────

interface StatusNode {
  key: PageStatus
  emoji: string
  label: string
  circleClass: string
  connectorActive: boolean
}

const STATUS_NODES: StatusNode[] = [
  { key: "idea",        emoji: "💭", label: "Idea",           circleClass: "bg-[#f5f5f4] border-[#d6d3d1]",    connectorActive: true },
  { key: "prompt",      emoji: "✏️", label: "Prompt Drafted", circleClass: "bg-amber-100 border-amber-400",     connectorActive: true },
  { key: "generated",   emoji: "🖼", label: "Generated",      circleClass: "bg-purple-100 border-purple-500",  connectorActive: true },
  { key: "review",      emoji: "🔍", label: "Needs Review",   circleClass: "bg-blue-100 border-blue-500",      connectorActive: false },
  { key: "revision",    emoji: "🔄", label: "Needs Revision", circleClass: "bg-red-100 border-red-500",        connectorActive: true },
  { key: "approved",    emoji: "👍", label: "Approved",       circleClass: "bg-green-100 border-green-500",    connectorActive: true },
  { key: "print_ready", emoji: "🖨", label: "Print Ready",    circleClass: "bg-teal-100 border-teal-500",      connectorActive: true },
  { key: "exported",    emoji: "📦", label: "Exported",       circleClass: "bg-[#f0fdf4] border-green-300",   connectorActive: false },
]

// ── Step Card ──────────────────────────────────────────────────────────────────

function StepCard({ step, phase }: { step: PhaseStep; phase: Phase }) {
  return (
    <div
      className="rounded-xl border-[1.5px] bg-[var(--card)] p-4 shadow-[var(--shadow-card)] transition-all duration-150 hover:-translate-y-px hover:shadow-[var(--shadow-card-md)]"
      style={{ borderColor: phase.color, width: "188px" }}
    >
      <span className="mb-2 block text-[22px]">{step.icon}</span>
      <p className="mb-1 text-[13px] font-bold text-[var(--foreground)]">{step.title}</p>
      <p className="mb-2.5 text-[11.5px] leading-[1.5] text-[var(--muted-foreground)]">{step.desc}</p>
      <span
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10.5px] font-semibold"
        style={{ backgroundColor: phase.bgColor, color: phase.color }}
      >
        {step.agentIsHuman ? "👤" : "🤖"} {step.agent}
      </span>
      <div className="mt-2 flex flex-wrap gap-1">
        {step.outputs.map((o) => (
          <span
            key={o}
            className="rounded border border-[var(--border)] bg-[var(--background)] px-1.5 py-0.5 text-[10px] text-[var(--muted-foreground)]"
          >
            {o}
          </span>
        ))}
      </div>
    </div>
  )
}

// ── Status Tracker ─────────────────────────────────────────────────────────────

function StatusTracker({ summary }: { summary: StatusSummary | undefined }) {
  const total = summary ? Object.values(summary).reduce((a, b) => a + b, 0) : 0

  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-7 shadow-[var(--shadow-card)]">
      <p className="mb-1 text-[14px] font-bold text-[var(--foreground)]">Page-Level Status Flow</p>
      <p className="mb-6 text-[12px] text-[var(--muted-foreground)]">
        Every coloring page moves through these stages independently within a book project.
        {total > 0 && <span className="ml-1 font-medium">({total} pages total)</span>}
      </p>
      <div className="flex items-center gap-0 overflow-x-auto pb-1">
        {STATUS_NODES.map((node, i) => {
          const count = summary?.[node.key] ?? null
          return (
            <React.Fragment key={node.key}>
              <div className="flex flex-col items-center gap-1.5 shrink-0">
                <div
                  className={`relative flex size-11 items-center justify-center rounded-full border-2 text-[18px] ${node.circleClass}`}
                >
                  {node.emoji}
                  {count !== null && count > 0 && (
                    <span className="absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-[var(--brand-accent)] text-[9px] font-bold text-white">
                      {count > 9 ? "9+" : count}
                    </span>
                  )}
                </div>
                <span className="max-w-[72px] text-center text-[11px] font-semibold leading-[1.3] text-[var(--muted-foreground)]">
                  {node.label}
                </span>
              </div>
              {i < STATUS_NODES.length - 1 && (
                <div
                  className={`mb-5 h-[2px] w-6 shrink-0 ${
                    node.connectorActive ? "bg-[var(--brand-accent)]" : "bg-[var(--border)]"
                  }`}
                />
              )}
            </React.Fragment>
          )
        })}
      </div>
    </div>
  )
}

// ── Principles ─────────────────────────────────────────────────────────────────

const PRINCIPLES = [
  {
    icon: "🖨",
    title: "Print Quality Rules",
    items: [
      "Pure black and white — no gray pixels",
      "Minimum 300 DPI (600 DPI preferred for printshop)",
      "Line weight minimum 1pt at final print size",
      "Correct bleed and margin for trim size",
      "No clutter or uncolorable tiny spaces",
    ],
  },
  {
    icon: "✏️",
    title: "Easy Edit Principle",
    items: [
      "Text and artwork kept as separate layers",
      "Never embed editable text inside AI-generated image",
      "Store source files alongside exported versions",
      "Version history preserved for every page",
      "Minor fixes don't require full regeneration",
    ],
  },
  {
    icon: "🎨",
    title: "Style Consistency",
    items: [
      "Style guide applied to every prompt automatically",
      "Negative prompts prevent style drift",
      "Critic flags inconsistency before approval",
      "Style guide versioned per book project",
      "Inspiration references linked to each book",
    ],
  },
]

// ── WorkflowPage ───────────────────────────────────────────────────────────────

export function WorkflowPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { data: books } = useBooks()

  // Determine active book: from ?book= param, fallback to first book
  const paramBookId = searchParams.get("book")
  const [selectedBookId, setSelectedBookId] = React.useState<string>(paramBookId ?? "")
  React.useEffect(() => {
    if (!selectedBookId && books && books.length > 0) {
      setSelectedBookId(books[0].id)
    }
  }, [books, selectedBookId])

  const { data: summary, isLoading: summaryLoading } = useBookStatusSummary(selectedBookId)

  return (
    <div className="flex min-h-full flex-col">
      {/* Top bar */}
      <header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <div>
          <h1 className="text-[16px] font-semibold text-[var(--foreground)]">Production Workflow</h1>
          <p className="text-[13px] text-[var(--text-muted)]">
            From initial concept to a print-ready, commercially publishable coloring book.
          </p>
        </div>
        {books && books.length > 0 && (
          <div className="ml-auto flex items-center gap-2">
            <label className="text-[12px] text-[var(--muted-foreground)]">Book:</label>
            <select
              value={selectedBookId}
              onChange={(e) => setSelectedBookId(e.target.value)}
              className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--brand-accent)]"
            >
              {books.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.emoji} {b.title}
                </option>
              ))}
            </select>
            {selectedBookId && (
              <button
                onClick={() => navigate(`/books/${selectedBookId}`)}
                className="text-[12px] text-[var(--brand-accent)] hover:underline"
              >
                Open →
              </button>
            )}
          </div>
        )}
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-8">
        {/* Phase Legend */}
        <div className="mb-10 flex flex-wrap justify-center gap-5">
          {PHASES.map((phase) => (
            <div key={phase.id} className="flex items-center gap-1.5 text-[12px] font-medium text-[var(--muted-foreground)]">
              <span
                className="inline-block size-2.5 rounded-full"
                style={{ backgroundColor: phase.color }}
              />
              {phase.label} & {phase.sub}
            </div>
          ))}
        </div>

        {/* Phase Flow */}
        <div className="mx-auto mb-10 max-w-[1100px]">
          {PHASES.map((phase) => (
            <div key={phase.id} className="flex gap-0">
              {/* Phase label */}
              <div className="flex w-[130px] shrink-0 flex-col items-end pr-5 pt-[22px] gap-1">
                <p className="text-[11px] font-bold uppercase tracking-[0.07em]" style={{ color: phase.color }}>
                  {phase.label}
                </p>
                <p className="text-[10px] text-[var(--text-muted)]">{phase.sub}</p>
              </div>

              {/* Spine */}
              <div className="relative mr-5 w-[2px] shrink-0">
                <div className="absolute inset-0 bg-[var(--border)]" />
                <div
                  className="absolute left-[-5px] top-[26px] size-3 rounded-full border-2 border-[var(--card)] z-10"
                  style={{ backgroundColor: phase.color }}
                />
              </div>

              {/* Steps */}
              <div className="flex flex-1 flex-wrap items-start gap-2.5 pb-7">
                {phase.steps.map((step) => (
                  <StepCard key={step.title} step={step} phase={phase} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Status Tracker */}
        <div className="mx-auto mb-6 max-w-[1100px]">
          {summaryLoading ? (
            <div className="h-[140px] animate-pulse rounded-2xl bg-[var(--border)]" />
          ) : (
            <StatusTracker summary={summary} />
          )}
        </div>

        {/* Principles */}
        <div className="mx-auto grid max-w-[1100px] grid-cols-3 gap-3">
          {PRINCIPLES.map((p) => (
            <div
              key={p.title}
              className="rounded-[10px] border border-[var(--border)] bg-[var(--card)] px-[18px] py-4"
            >
              <p className="mb-2 flex items-center gap-1.5 text-[12px] font-bold text-[var(--foreground)]">
                {p.icon} {p.title}
              </p>
              <ul className="flex flex-col gap-1.5">
                {p.items.map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-1.5 text-[11.5px] leading-[1.4] text-[var(--muted-foreground)]"
                  >
                    <span className="mt-[2px] shrink-0 text-[var(--text-muted)]">→</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
