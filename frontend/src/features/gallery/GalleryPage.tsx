/**
 * GalleryPage — Component + design token gallery for fidelity and a11y verification.
 * Route: /gallery (rendered from App.tsx based on ?gallery query param or hash)
 */
import * as React from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card"
import { Badge, type PageStatus, PAGE_STATUS_LABELS } from "@/components/ui/badge"
import { StatCard } from "@/components/ui/stat-card"
import { ProgressBar } from "@/components/ui/progress"
import { PageCard } from "@/components/ui/page-card"
import { BookListItem } from "@/components/ui/book-list-item"
import {
  AppSidebar,
  SidebarLogo,
  SidebarSection,
  SidebarNavItem,
  SidebarFooter,
} from "@/components/ui/app-sidebar"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter as DialogFoot,
  DialogTrigger,
} from "@/components/ui/dialog"

/* ── Section wrapper ── */
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--text-muted)]">
        {title}
      </h2>
      <hr className="mb-5 border-[var(--border)]" />
      {children}
    </section>
  )
}

/* ── Token swatch ── */
function Swatch({ name, value, textClass }: { name: string; value: string; textClass?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div
        className="h-10 rounded-[6px] border border-[var(--border)]"
        style={{ background: value }}
        title={value}
      />
      <p className={`text-[10px] font-medium ${textClass ?? "text-[var(--foreground)]"}`}>{name}</p>
      <p className="text-[10px] text-[var(--text-muted)]">{value}</p>
    </div>
  )
}

const PAGE_STATUSES: PageStatus[] = [
  "idea", "prompt", "generated", "review", "revision", "approved", "print_ready", "exported",
]

export function GalleryPage() {
  const [activeNav, setActiveNav] = React.useState("dashboard")

  return (
    <div className="flex min-h-screen bg-[var(--background)]">

      {/* ── Live Sidebar Preview ── */}
      <AppSidebar className="h-screen sticky top-0">
        <SidebarLogo />
        <SidebarSection label="Workspace">
          <SidebarNavItem
            icon="⊞"
            active={activeNav === "dashboard"}
            onClick={() => setActiveNav("dashboard")}
          >
            Dashboard
          </SidebarNavItem>
          <SidebarNavItem
            icon="📖"
            badge={4}
            active={activeNav === "books"}
            onClick={() => setActiveNav("books")}
          >
            Book Projects
          </SidebarNavItem>
          <SidebarNavItem
            icon="🖼"
            active={activeNav === "editor"}
            onClick={() => setActiveNav("editor")}
          >
            Page Editor
          </SidebarNavItem>
          <SidebarNavItem
            icon="🤖"
            active={activeNav === "agents"}
            onClick={() => setActiveNav("agents")}
          >
            Agent Console
          </SidebarNavItem>
        </SidebarSection>
        <SidebarSection label="Library">
          <SidebarNavItem icon="💡" active={activeNav === "inspiration"} onClick={() => setActiveNav("inspiration")}>Inspiration</SidebarNavItem>
          <SidebarNavItem icon="📚" active={activeNav === "mybooks"} onClick={() => setActiveNav("mybooks")}>My Books</SidebarNavItem>
          <SidebarNavItem icon="🔍" active={activeNav === "market"} onClick={() => setActiveNav("market")}>Search Market</SidebarNavItem>
        </SidebarSection>
        <SidebarSection label="Production">
          <SidebarNavItem icon="✅" active={activeNav === "quality"} onClick={() => setActiveNav("quality")}>Quality Check</SidebarNavItem>
          <SidebarNavItem icon="📦" active={activeNav === "export"} onClick={() => setActiveNav("export")}>Export Center</SidebarNavItem>
          <SidebarNavItem icon="🖨" active={activeNav === "print"} onClick={() => setActiveNav("print")}>Print Prep</SidebarNavItem>
        </SidebarSection>
        <SidebarFooter>
          <SidebarNavItem icon="⚙️" active={activeNav === "settings"} onClick={() => setActiveNav("settings")}>Settings</SidebarNavItem>
        </SidebarFooter>
      </AppSidebar>

      {/* ── Main gallery content ── */}
      <main className="flex-1 overflow-y-auto px-8 py-10">
        <div className="mx-auto max-w-4xl">

          <div className="mb-8">
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-[var(--brand-accent)]">
              U3 — Component Gallery
            </p>
            <h1 className="text-2xl font-bold text-[var(--foreground)]">
              Design System Gallery
            </h1>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Every component rendered with all variants. Colors and spacing match{" "}
              <code className="rounded bg-[var(--muted)] px-1 py-0.5 text-[11px]">
                coloring-book-studio.html
              </code>{" "}
              mockup.
            </p>
          </div>

          {/* ── DESIGN TOKENS ── */}
          <Section title="Design Tokens — Color Palette">
            <div className="grid grid-cols-4 gap-4 sm:grid-cols-6 lg:grid-cols-8">
              <Swatch name="background" value="#f7f5f0" />
              <Swatch name="surface" value="#ffffff" />
              <Swatch name="sidebar" value="#1c1917" textClass="text-white" />
              <Swatch name="accent" value="#b45309" textClass="text-white" />
              <Swatch name="accent-light" value="#fef3c7" />
              <Swatch name="border" value="#e7e5e0" />
              <Swatch name="text-primary" value="#1c1917" textClass="text-white" />
              <Swatch name="text-muted" value="#a8a29e" />
            </div>
            <div className="mt-4 grid grid-cols-4 gap-4 sm:grid-cols-6">
              <Swatch name="green" value="#15803d" textClass="text-white" />
              <Swatch name="green-light" value="#dcfce7" />
              <Swatch name="blue" value="#1d4ed8" textClass="text-white" />
              <Swatch name="blue-light" value="#dbeafe" />
              <Swatch name="red" value="#b91c1c" textClass="text-white" />
              <Swatch name="red-light" value="#fee2e2" />
              <Swatch name="yellow" value="#b45309" textClass="text-white" />
              <Swatch name="yellow-light" value="#fef3c7" />
              <Swatch name="purple" value="#7c3aed" textClass="text-white" />
              <Swatch name="purple-light" value="#ede9fe" />
            </div>
          </Section>

          {/* ── BADGE ── */}
          <Section title="Badge — All Variants">
            <div className="flex flex-wrap gap-3">
              {PAGE_STATUSES.map((s) => (
                <Badge key={s} variant={s} dot>
                  {PAGE_STATUS_LABELS[s]}
                </Badge>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-3">
              <Badge variant="green" dot>In Production</Badge>
              <Badge variant="blue" dot>In Progress</Badge>
              <Badge variant="yellow" dot>Needs Review</Badge>
              <Badge variant="red" dot>Revision</Badge>
              <Badge variant="purple" dot>Generated</Badge>
              <Badge variant="gray" dot>Draft</Badge>
              <Badge variant="outline">Outline</Badge>
            </div>
          </Section>

          {/* ── BUTTON ── */}
          <Section title="Button — All Variants + Sizes">
            <div className="flex flex-wrap items-center gap-2">
              <Button>Default</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="destructive">Destructive</Button>
              <Button variant="link">Link</Button>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Button size="xs">XSmall</Button>
              <Button size="sm">Small</Button>
              <Button size="default">Default</Button>
              <Button size="lg">Large</Button>
              <Button disabled>Disabled</Button>
            </div>
          </Section>

          {/* ── STAT CARDS ── */}
          <Section title="StatCard — Dashboard Metrics">
            <div className="grid grid-cols-3 gap-4">
              <StatCard
                label="Active Books"
                value="4"
                sub="2 in production · 2 in draft"
              />
              <StatCard
                label="Pages This Week"
                value="23"
                sub={
                  <span>
                    <span className="font-semibold text-[var(--status-green)]">↑ 8</span>{" "}
                    from last week
                  </span>
                }
              />
              <StatCard
                label="Print-Ready Pages"
                value="147"
                sub="Across all projects"
              />
            </div>
          </Section>

          {/* ── PROGRESS BAR ── */}
          <Section title="ProgressBar">
            <div className="flex max-w-sm flex-col gap-4">
              <div>
                <p className="mb-1 text-xs text-[var(--muted-foreground)]">80% complete</p>
                <ProgressBar value={80} showLabel />
              </div>
              <div>
                <p className="mb-1 text-xs text-[var(--muted-foreground)]">51% complete</p>
                <ProgressBar value={51} showLabel />
              </div>
              <div>
                <p className="mb-1 text-xs text-[var(--muted-foreground)]">10% complete</p>
                <ProgressBar value={10} showLabel />
              </div>
            </div>
          </Section>

          {/* ── CARD ── */}
          <Section title="Card">
            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>Card Title</CardTitle>
                  <CardDescription>Supporting description text for the card component.</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-[var(--muted-foreground)]">
                    Card body content area. Matches the mockup surface (#fff) with warm border.
                  </p>
                </CardContent>
                <CardFooter className="gap-2">
                  <Button size="sm">Primary</Button>
                  <Button size="sm" variant="outline">Cancel</Button>
                </CardFooter>
              </Card>
              <Card size="sm">
                <CardHeader>
                  <CardTitle>Compact Card</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-[var(--muted-foreground)]">Smaller card variant.</p>
                </CardContent>
              </Card>
            </div>
          </Section>

          {/* ── BOOK LIST ITEMS ── */}
          <Section title="BookListItem">
            <Card className="overflow-hidden">
              <BookListItem
                thumb="🌸"
                thumbBg="#fef3c7"
                thumbColor="#92400e"
                title="Botanical Serenity Vol. 2"
                badgeVariant="green"
                badgeLabel="In Production"
                meta="32 / 40 pages"
                progress={80}
              />
              <BookListItem
                thumb="🏡"
                thumbBg="#dbeafe"
                thumbColor="#1d4ed8"
                title="Cozy Cottage Life"
                badgeVariant="blue"
                badgeLabel="In Progress"
                meta="18 / 35 pages"
                progress={51}
              />
              <BookListItem
                thumb="🦋"
                thumbBg="#dcfce7"
                thumbColor="#15803d"
                title="Enchanted Garden"
                badgeVariant="yellow"
                badgeLabel="Needs Review"
                meta="12 / 30 pages"
                progress={40}
              />
              <BookListItem
                thumb="🌙"
                thumbBg="#f5f5f4"
                thumbColor="#57534e"
                title="Celestial Dreams"
                badgeVariant="gray"
                badgeLabel="Draft"
                meta="3 / 30 pages"
                progress={10}
              />
            </Card>
          </Section>

          {/* ── PAGE CARDS ── */}
          <Section title="PageCard — Generated Pages Grid">
            <div className="grid grid-cols-4 gap-3">
              <PageCard name="Hibiscus Border" status="print_ready" thumb="🌺" thumbBg="#fef9ee" />
              <PageCard name="Mountain Scene" status="review" thumb="⛰️" thumbBg="#dbeafe" />
              <PageCard name="Owl Sketch" status="revision" thumb="🦉" thumbBg="#fee2e2" />
              <PageCard name="Mandala Draft" status="generated" thumb="🌀" thumbBg="#ede9fe" />
              <PageCard name="Sea Turtle" status="approved" thumb="🐢" thumbBg="#dcfce7" />
              <PageCard name="Story Prompt" status="prompt" thumb="✏️" thumbBg="#fef3c7" />
              <PageCard name="Concept Note" status="idea" thumb="💡" thumbBg="#f5f5f4" />
              <PageCard name="Final Export" status="exported" thumb="📦" thumbBg="#f5f5f4" />
            </div>
          </Section>

          {/* ── DIALOG ── */}
          <Section title="Dialog (Modal)">
            <p className="mb-3 text-sm text-[var(--muted-foreground)]">
              Focus-trapped, closes on Esc, ARIA labelled.
            </p>
            <Dialog>
              <DialogTrigger asChild>
                <Button>Open Dialog</Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Confirm Export</DialogTitle>
                  <DialogDescription>
                    This will export "Botanical Serenity Vol. 2" as a print-ready PDF at 300 DPI.
                    This cannot be undone.
                  </DialogDescription>
                </DialogHeader>
                <DialogFoot showCloseButton>
                  <Button>Export Now</Button>
                </DialogFoot>
              </DialogContent>
            </Dialog>
          </Section>

          {/* ── TOAST ── */}
          <Section title="Toast (Sonner)">
            <p className="mb-3 text-sm text-[var(--muted-foreground)]">
              Toast notifications via Sonner — rendered in App root.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => toast.success("Page exported successfully!")}>
                Success Toast
              </Button>
              <Button size="sm" variant="outline" onClick={() => toast.info("Generating page…")}>
                Info Toast
              </Button>
              <Button size="sm" variant="destructive" onClick={() => toast.error("Export failed. Try again.")}>
                Error Toast
              </Button>
              <Button size="sm" variant="secondary" onClick={() => toast.warning("Low print quality detected.")}>
                Warning Toast
              </Button>
            </div>
          </Section>

          {/* ── A11Y NOTES ── */}
          <Section title="Accessibility Notes">
            <Card>
              <CardContent className="pt-4">
                <ul className="space-y-1.5 text-sm text-[var(--muted-foreground)]">
                  <li>✓ All interactive elements have visible focus rings (2px solid --ring)</li>
                  <li>✓ Dialog traps focus + closes on Esc (Radix DialogPrimitive)</li>
                  <li>✓ Sidebar nav items have aria-current="page" on active item</li>
                  <li>✓ ProgressBar has role=progressbar + aria-valuenow/min/max</li>
                  <li>✓ Badge dot is aria-hidden (decorative)</li>
                  <li>✓ PageCard and BookListItem have role=button + tabIndex for keyboard nav</li>
                  <li>✓ Color contrast: accent #b45309 on white = 4.6:1 (AA large text)</li>
                  <li>✓ Status text colors all ≥ 4.5:1 on their light backgrounds</li>
                </ul>
              </CardContent>
            </Card>
          </Section>

        </div>
      </main>
    </div>
  )
}
