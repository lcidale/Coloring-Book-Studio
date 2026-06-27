/**
 * PlaceholderViews — Styled placeholder views for routes not yet fully implemented.
 * Each has a header, icon, description, and relevant quick-action buttons.
 */
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"

// ── Generic Placeholder Base ───────────────────────────────────────────────────

interface PlaceholderViewProps {
  icon: string
  title: string
  description: string
  subtitle?: string
  actions?: { label: string; route: string; variant?: "default" | "outline" }[]
  features?: { icon: string; label: string; desc: string }[]
}

function PlaceholderView({
  icon,
  title,
  description,
  subtitle,
  actions = [],
  features = [],
}: PlaceholderViewProps) {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-full flex-col">
      {/* Top bar */}
      <header className="flex shrink-0 items-center border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <h1 className="text-[16px] font-semibold text-[var(--foreground)]">{title}</h1>
      </header>

      {/* Centered content */}
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-lg">
          {/* Hero card */}
          <div className="mb-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-8 py-10 text-center shadow-[var(--shadow-card)]">
            <div className="mb-4 text-5xl">{icon}</div>
            <h2 className="mb-2 text-[20px] font-bold text-[var(--foreground)]">{title}</h2>
            {subtitle && (
              <p className="mb-1 text-[13px] font-medium text-[var(--brand-accent)]">{subtitle}</p>
            )}
            <p className="mb-6 text-[13.5px] leading-relaxed text-[var(--muted-foreground)]">
              {description}
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {actions.map((action) => (
                <Button
                  key={action.label}
                  variant={action.variant ?? "default"}
                  size="sm"
                  onClick={() => navigate(action.route)}
                >
                  {action.label}
                </Button>
              ))}
              <Button variant="outline" size="sm" onClick={() => navigate("/")}>
                Back to Dashboard
              </Button>
            </div>
          </div>

          {/* Feature preview cards */}
          {features.length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              {features.map((f) => (
                <div
                  key={f.label}
                  className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3.5 shadow-[var(--shadow-card)]"
                >
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className="text-[18px]">{f.icon}</span>
                    <span className="text-[13px] font-semibold text-[var(--foreground)]">{f.label}</span>
                  </div>
                  <p className="text-[12px] leading-relaxed text-[var(--muted-foreground)]">{f.desc}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Agent Console ──────────────────────────────────────────────────────────────

export function AgentConsolePlaceholder() {
  return (
    <PlaceholderView
      icon="🤖"
      title="Agent Console"
      description="Monitor and configure the AI agents that power your coloring book studio — from concept generation to print QC."
      subtitle="Coming soon"
      actions={[{ label: "View Dashboard", route: "/", variant: "outline" }]}
      features={[
        { icon: "💡", label: "Concept Agent", desc: "Generates book themes, niches, and page ideas based on your brief." },
        { icon: "🖼", label: "Line Art Agent", desc: "Creates B&W coloring page images with provider of your choice." },
        { icon: "🔍", label: "Page Critic", desc: "Reviews each page for colorability, style, and print readiness." },
        { icon: "📦", label: "Export Agent", desc: "Assembles and exports print-ready PDFs for KDP and Etsy." },
      ]}
    />
  )
}

// ── Inspiration ────────────────────────────────────────────────────────────────

export function InspirationPlaceholder() {
  return (
    <PlaceholderView
      icon="💡"
      title="Inspiration"
      description="Browse trending coloring book styles, themes, and reference images. Save inspirations and link them to your current book projects."
      subtitle="Coming soon"
      actions={[{ label: "View Books", route: "/books", variant: "outline" }]}
      features={[
        { icon: "🎨", label: "Style Gallery", desc: "Curated examples of line art styles — botanical, geometric, fantasy, and more." },
        { icon: "📌", label: "Save & Tag", desc: "Pin references and tag them to specific books or pages." },
        { icon: "🔍", label: "Browse by Niche", desc: "Filter by audience, style, complexity, and commercial viability." },
        { icon: "🔗", label: "Link to Book", desc: "Attach inspiration to a book so agents can reference the style." },
      ]}
    />
  )
}

// ── My Books ──────────────────────────────────────────────────────────────────

export function MyBooksPlaceholder() {
  return (
    <PlaceholderView
      icon="📚"
      title="My Books"
      description="View your published and archived coloring books. Track sales, reviews, and republish updated editions."
      subtitle="Coming soon"
      actions={[
        { label: "Open Book Projects", route: "/books" },
        { label: "Back to Dashboard", route: "/", variant: "outline" },
      ]}
      features={[
        { icon: "📖", label: "Published Books", desc: "Books live on KDP, Etsy, or Gumroad with sales tracking." },
        { icon: "🗄", label: "Archive", desc: "Older or discontinued books stored for reference." },
        { icon: "📊", label: "Sales Data", desc: "Revenue and download stats per book." },
        { icon: "🔄", label: "Republish", desc: "Update an existing book with new pages or cover revisions." },
      ]}
    />
  )
}

// ── Search Market ─────────────────────────────────────────────────────────────

export function SearchMarketPlaceholder() {
  return (
    <PlaceholderView
      icon="🔍"
      title="Search Market"
      description="Research the KDP and Etsy coloring book markets. Identify trending niches, best-selling styles, pricing benchmarks, and content gaps."
      subtitle="Coming soon"
      actions={[{ label: "View Books", route: "/books", variant: "outline" }]}
      features={[
        { icon: "📈", label: "Trend Scanner", desc: "Live KDP search trends for coloring books by keyword and niche." },
        { icon: "🏆", label: "Best Sellers", desc: "Top-performing coloring books with review counts and price points." },
        { icon: "🕳", label: "Gap Finder", desc: "Underserved niches with high demand and low competition." },
        { icon: "💰", label: "Pricing Intel", desc: "Price distribution and royalty estimates for your niche." },
      ]}
    />
  )
}

// ── Quality Check ─────────────────────────────────────────────────────────────

export function QualityCheckPlaceholder() {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-full flex-col">
      <header className="flex shrink-0 items-center border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <h1 className="text-[16px] font-semibold text-[var(--foreground)]">Quality Check</h1>
      </header>
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-lg">
          <div className="mb-6 rounded-2xl border border-[var(--border)] bg-[var(--card)] px-8 py-10 text-center shadow-[var(--shadow-card)]">
            <div className="mb-4 text-5xl">✅</div>
            <h2 className="mb-2 text-[20px] font-bold text-[var(--foreground)]">Quality Check</h2>
            <p className="mb-1 text-[13px] font-medium text-[var(--brand-accent)]">Review your pages in the Page Editor</p>
            <p className="mb-6 text-[13.5px] leading-relaxed text-[var(--muted-foreground)]">
              Automated print-quality analysis — pure B&W verification, DPI check, bleed &amp; trim validation.
              Open a page in the editor to review print check notes and approve or request revisions.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              <Button size="sm" onClick={() => navigate("/books")}>
                Open Book Projects
              </Button>
              <Button variant="outline" size="sm" onClick={() => navigate("/workflow")}>
                View Workflow
              </Button>
              <Button variant="outline" size="sm" onClick={() => navigate("/")}>
                Dashboard
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {[
              { icon: "⬛", label: "Pure B&W Check", desc: "Detects gray pixels that would print poorly." },
              { icon: "🔬", label: "DPI Validation", desc: "Ensures 300+ DPI for print-quality output." },
              { icon: "📐", label: "Trim & Bleed", desc: "Verifies correct dimensions and bleed area." },
              { icon: "📝", label: "Print Notes", desc: "Specific issues flagged on each page card." },
            ].map((f) => (
              <div key={f.label} className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-4 py-3.5 shadow-[var(--shadow-card)]">
                <div className="mb-1.5 flex items-center gap-2">
                  <span className="text-[18px]">{f.icon}</span>
                  <span className="text-[13px] font-semibold text-[var(--foreground)]">{f.label}</span>
                </div>
                <p className="text-[12px] leading-relaxed text-[var(--muted-foreground)]">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Export Center ─────────────────────────────────────────────────────────────

export function ExportCenterPlaceholder() {
  return (
    <PlaceholderView
      icon="📦"
      title="Export Center"
      description="Export approved books as print-ready PDFs with correct trim size, bleed, and margins. Export is available now from the Book Detail page."
      subtitle="Export available in Book Projects"
      actions={[
        { label: "Open Book Projects", route: "/books" },
        { label: "Dashboard", route: "/", variant: "outline" },
      ]}
      features={[
        { icon: "📄", label: "KDP Interior PDF", desc: "7×10 or 8.5×11 with correct bleed and margins for Amazon KDP." },
        { icon: "🖨", label: "Printshop PDF", desc: "High-resolution with trim marks and color profile for professional print." },
        { icon: "📱", label: "Etsy Digital", desc: "Letter or A4 formatted for immediate digital download sale." },
        { icon: "📦", label: "Bundle ZIP", desc: "All formats packaged for Gumroad or Payhip bundle." },
      ]}
    />
  )
}

// ── Print Prep ────────────────────────────────────────────────────────────────

export function PrintPrepPlaceholder() {
  return (
    <PlaceholderView
      icon="🖨"
      title="Print Prep"
      description="Final print preparation — KDP upload checklist, cover creation guidance, and Canva export templates for professional publishing."
      subtitle="Coming soon"
      actions={[
        { label: "Export Center", route: "/export" },
        { label: "Dashboard", route: "/", variant: "outline" },
      ]}
      features={[
        { icon: "📋", label: "KDP Checklist", desc: "Step-by-step upload guide for Amazon KDP interior and cover." },
        { icon: "🎨", label: "Cover Creator", desc: "Canva-powered cover templates sized for KDP requirements." },
        { icon: "✅", label: "Pre-flight Check", desc: "Final validation pass before submitting to KDP or printshop." },
        { icon: "🚀", label: "Launch Tracker", desc: "Track your submission status and launch timeline." },
      ]}
    />
  )
}
