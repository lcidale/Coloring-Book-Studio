# Coloring Book Studio — Design System

> `/docs/design-system.md` is the UI/UX source of truth for this project. It documents the visual foundations, component standards, layout rules, UX principles, accessibility requirements, interaction patterns, and forbidden UI patterns that all agents and developers must follow. Its purpose is to prevent design drift, preserve intentional design decisions, and ensure that every UI change remains consistent with the project's established product experience.

**Source of truth for all UI/UX decisions.** Every value in this document is extracted directly from `frontend/src/index.css`, `frontend/src/components/ui/`, and the feature pages. Do not invent values — change this doc when you change the code.

**Figma design system file:** https://www.figma.com/design/mC044MH1WirZ5Hzh2PILML
Code Connect mappings exist for **Button** and **Badge** (both have `data-slot` attributes aligned with Figma variants).

---

## 1. Visual Foundations

### 1.1 Color Tokens

All colors are CSS custom properties declared in `:root` inside `frontend/src/index.css`. The Tailwind v4 `@theme inline` block aliases them as `--color-*` utilities. Always use the var(), never the raw hex.

#### Core Semantic Tokens

| Token | Light value | Dark value | When to use |
|---|---|---|---|
| `--background` | `#f7f5f0` | `#0c0a09` | Page/app background |
| `--foreground` | `#1c1917` | `#fafaf9` | Body text, headings |
| `--card` | `#ffffff` | `#1c1917` | Card/panel backgrounds |
| `--card-foreground` | `#1c1917` | `#fafaf9` | Text inside cards |
| `--popover` | `#ffffff` | `#1c1917` | Dropdown/tooltip backgrounds |
| `--popover-foreground` | `#1c1917` | `#fafaf9` | Text inside popovers |
| `--primary` | `#b45309` | `#d97706` | Primary buttons, links |
| `--primary-foreground` | `#ffffff` | `#ffffff` | Text on primary buttons |
| `--secondary` | `#f7f5f0` | `#292524` | Secondary buttons |
| `--secondary-foreground` | `#1c1917` | `#fafaf9` | Text on secondary buttons |
| `--muted` | `#f5f5f4` | `#292524` | Muted/subtle backgrounds |
| `--muted-foreground` | `#78716c` | `#a8a29e` | Secondary/helper text |
| `--accent` | `#fef3c7` | `#44403c` | Hover highlight backgrounds |
| `--accent-foreground` | `#92400e` | `#fef3c7` | Text on accent backgrounds |
| `--destructive` | `#b91c1c` | `#ef4444` | Destructive actions, error text |
| `--border` | `#e7e5e0` | `#292524` | All dividers and control borders |
| `--input` | `#e7e5e0` | `#292524` | Input field border color |
| `--ring` | `#b45309` | `#d97706` | Focus ring color (= brand accent) |

#### Brand Tokens (direct component use)

| Token | Value | When to use |
|---|---|---|
| `--brand-accent` | `#b45309` | Amber — active nav badge, ProgressBar fill, hover borders, logo bg |
| `--brand-accent-hover` | `#92400e` | Darker amber — hover state when `--brand-accent` is the base |
| `--brand-accent-light` | `#fef3c7` | Pale amber — selected radio bg, agent icon bg, quick action hover |
| `--text-muted` | `#a8a29e` | Tertiary text: timestamps, percent labels, sidebar section labels |

#### Sidebar Tokens

| Token | Light value | Dark value | When to use |
|---|---|---|---|
| `--sidebar` | `#1c1917` | `#0c0a09` | Sidebar background |
| `--sidebar-foreground` | `#d6d3cd` | `#d6d3cd` | Sidebar item text |
| `--sidebar-primary` | `#b45309` | `#d97706` | Sidebar primary accent |
| `--sidebar-primary-foreground` | `#ffffff` | `#ffffff` | Text on sidebar primary |
| `--sidebar-accent` | `#292524` | `#1c1917` | Active nav item background |
| `--sidebar-accent-foreground` | `#ffffff` | `#ffffff` | Active nav item text |
| `--sidebar-border` | `#292524` | `#1c1917` | Sidebar dividers |
| `--sidebar-ring` | `#b45309` | `#d97706` | Focus ring inside sidebar |

#### Status Palette

Used exclusively by `Badge` variants and `PageCard`. Never invent a new status color — extend this set if needed.

| Token | Value | Paired bg token | Value |
|---|---|---|---|
| `--status-green` | `#15803d` | `--status-green-bg` | `#dcfce7` |
| `--status-blue` | `#1d4ed8` | `--status-blue-bg` | `#dbeafe` |
| `--status-yellow` | `#b45309` | `--status-yellow-bg` | `#fef3c7` |
| `--status-red` | `#b91c1c` | `--status-red-bg` | `#fee2e2` |
| `--status-purple` | `#7c3aed` | `--status-purple-bg` | `#ede9fe` |
| `--status-gray` | `#78716c` | `--status-gray-bg` | `#f5f5f4` |

#### Chart Tokens

`--chart-1` through `--chart-5`: `#b45309`, `#1d4ed8`, `#15803d`, `#7c3aed`, `#b91c1c`. Use only in chart/data-vis contexts.

---

### 1.2 Typography

Base font size is `14px` (set on `<html>`). All type is `var(--font-sans)` (-apple-system stack). Monospace uses `var(--font-mono)` (ui-monospace / SF Mono stack). `--font-heading` aliases `--font-sans`.

| Use | Class / style |
|---|---|
| Page title (h1) | `text-[16px] font-semibold text-[var(--foreground)]` |
| Page subtitle | `text-[13px] text-[var(--text-muted)]` |
| Section header (h2) | `text-[15px] font-semibold text-[var(--foreground)]` (Settings) / `text-[14px] font-semibold` (Dashboard SectionHeader) |
| Card title | `font-heading text-base font-medium` (via `CardTitle`) |
| Card description | `text-sm text-muted-foreground` (via `CardDescription`) |
| Stat card label | `text-[12px] font-medium uppercase tracking-[0.04em] text-[var(--text-muted)]` |
| Stat card value | `text-[28px] font-bold leading-none text-[var(--foreground)]` |
| Sidebar section label | `text-[10px] font-semibold uppercase tracking-[0.08em] text-[#57534e]` |
| Sidebar nav item | `text-[13.5px]` |
| Badge | `text-[11px] font-medium` |
| Body / helper text | `text-sm text-[var(--muted-foreground)]` |
| Code / env key | `text-[12px] rounded bg-[var(--muted)] px-1` |

---

### 1.3 Radius

Base radius token: `--radius: 0.625rem` (10px).

| Token | Calculation | Approx px |
|---|---|---|
| `--radius-xs` | `calc(var(--radius) * 0.4)` | 4px |
| `--radius-sm` | `calc(var(--radius) * 0.6)` | 6px |
| `--radius-md` | `calc(var(--radius) * 0.8)` | 8px |
| `--radius-lg` | `var(--radius)` | 10px |
| `--radius-xl` | `calc(var(--radius) * 1.4)` | 14px |
| `--radius-2xl` | `calc(var(--radius) * 1.8)` | 18px |
| `--radius-3xl` | `calc(var(--radius) * 2.2)` | 22px |
| `--radius-4xl` | `calc(var(--radius) * 2.6)` | 26px |

In practice components use: cards → `rounded-xl` / `rounded-[10px]`, buttons → `rounded-lg`, badges → `rounded` (tiny), sidebar nav items → `rounded-[6px]`.

---

### 1.4 Shadows

| Token | Value | When to use |
|---|---|---|
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)` | Default card/panel elevation (`StatCard`, `PanelCard`) |
| `--shadow-card-md` | `0 4px 6px rgba(0,0,0,0.07), 0 2px 4px rgba(0,0,0,0.04)` | Hovered `PageCard` |
| `--shadow-modal` | `0 20px 60px rgba(0,0,0,0.15), 0 8px 24px rgba(0,0,0,0.1)` | Modal overlays (available, not yet applied to `DialogContent` directly) |

---

### 1.5 Spacing

No custom spacing scale — use Tailwind's default spacing. Common patterns observed:

- Content padding inside panels: `px-4 py-3.5` (list items), `px-5 py-[18px]` (stat cards), `p-5` (settings sections)
- Gap between dashboard columns: `gap-5`
- Gap between stat cards: `gap-4`
- Page content padding: `p-6`
- Sidebar width: `w-[220px]` (fixed, `shrink-0`)

---

### 1.6 Icon Rules

**Icon library:** all icons come from `lucide-react`. Do not import from any other icon library.

**Icons in use** (confirmed from `frontend/src/components/ui/sonner.tsx` and `dialog.tsx`):

| Icon | Import name | Where used |
|---|---|---|
| Dismiss | `XIcon` | `DialogContent` close button |
| Success toast | `CircleCheckIcon` | Sonner success icon |
| Info toast | `InfoIcon` | Sonner info icon |
| Warning toast | `TriangleAlertIcon` | Sonner warning icon |
| Error toast | `OctagonXIcon` | Sonner error icon |
| Loading toast | `Loader2Icon` | Sonner loading icon (`animate-spin`) |

**Emoji icons** (nav items, thumbnails, placeholder views) are decorative and must always have `aria-hidden="true"`. They are never rendered via a Lucide component — use a plain `<span aria-hidden="true">` or bare string in JSX.

**Icon sizing inside buttons:**
- Standard inline icons: `size-4` (16px)
- Compact / dense contexts: `size-3.5` (14px)
- Use the Button `size="icon"` / `size="icon-sm"` / `size="icon-xs"` / `size="icon-lg"` variants for icon-only buttons (see §2.1)

**Rules:**
- Never mix Lucide with other icon libraries (Heroicons, Radix icons, FontAwesome, etc.)
- Always use the named import form: `import { XIcon } from "lucide-react"` — no default imports or barrel re-exports
- Icon-only buttons must have an `<span className="sr-only">` label (see §5.3)

---

## 2. Component Standards

### 2.1 Button (`frontend/src/components/ui/button.tsx`)

Built with CVA. Variants and sizes:

| Variant | Appearance | Use |
|---|---|---|
| `default` | Amber fill (`--primary`) + white text | Primary actions |
| `outline` | White bg, `--border` border, hover → muted | Secondary actions |
| `secondary` | `--secondary` bg | Tertiary in-page actions |
| `ghost` | Transparent, hover → muted | Toolbar/icon-button context |
| `destructive` | Pale red bg, red text | Delete / irreversible actions |
| `link` | Text-only, underline on hover | Inline navigation |

| Size | Height | Notes |
|---|---|---|
| `default` | `h-8` | Standard |
| `xs` | `h-6` | Fine print contexts |
| `sm` | `h-7` | Page header actions (most common in feature pages) |
| `lg` | `h-9` | Hero CTAs |
| `icon` | `size-8` | Square icon-only |
| `icon-sm` | `size-7` | Dialog close button |
| `icon-xs` | `size-6` | Tight toolbar |
| `icon-lg` | `size-9` | Prominent icon actions |

Props: `variant`, `size`, `asChild` (Slot passthrough), all native `<button>` props. `data-slot="button"` is always present.

```tsx
// Primary action in page header
<Button size="sm" onClick={() => navigate("/books/new")}>+ New Book</Button>

// Secondary action
<Button variant="outline" size="sm" onClick={() => navigate("/books")}>Book Projects</Button>

// Dialog close (auto-rendered by DialogContent)
<Button variant="ghost" size="icon-sm"><XIcon /></Button>
```

---

### 2.2 Badge (`frontend/src/components/ui/badge.tsx`)

Inline status chip. 11px font, 7px horizontal padding, 2px vertical padding.

**Semantic color variants:**

| Variant | Background | Text |
|---|---|---|
| `green` | `--status-green-bg` | `--status-green` |
| `blue` | `--status-blue-bg` | `--status-blue` |
| `yellow` | `--status-yellow-bg` | `--status-yellow` |
| `red` | `--status-red-bg` | `--status-red` |
| `purple` | `--status-purple-bg` | `--status-purple` |
| `gray` | `--status-gray-bg` | `--status-gray` |

**PageStatus workflow variants** (use these, not raw colors, for page statuses):

| Variant | Color alias | Label (from `PAGE_STATUS_LABELS`) |
|---|---|---|
| `idea` | gray | "Idea" |
| `prompt` | yellow | "Prompt" |
| `generated` | purple | "Generated" |
| `review` | blue | "Review" |
| `revision` | red | "Revision" |
| `approved` | green | "Approved" |
| `print_ready` | green | "Print Ready" |
| `exported` | gray | "Exported" |

**Other variants:** `default` (gray), `outline` (border + foreground), `secondary`, `destructive` (red).

**Props:** `variant`, `dot` (boolean — renders a 6px filled circle before text), `className`, all `<span>` props.

```tsx
// Page status badge with dot
<Badge variant="generated" dot>{PAGE_STATUS_LABELS["generated"]}</Badge>

// Provider configured state
<Badge variant="green" dot>Configured</Badge>
<Badge variant="yellow" dot>Not Configured</Badge>

// Env var label
<Badge variant="gray">env var</Badge>
```

---

### 2.3 Card (`frontend/src/components/ui/card.tsx`)

General-purpose container. White bg, `rounded-xl`, `ring-1 ring-foreground/10` (no explicit border token — it uses a ring instead).

**Sub-components:**

| Component | Slot | Notes |
|---|---|---|
| `Card` | `card` | `size="default"` (spacing 4) or `size="sm"` (spacing 3) |
| `CardHeader` | `card-header` | Grid layout; auto-places `CardAction` in col 2 |
| `CardTitle` | `card-title` | `text-base font-medium`, smaller in `size=sm` |
| `CardDescription` | `card-description` | `text-sm text-muted-foreground` |
| `CardAction` | `card-action` | Right-aligned action area in header |
| `CardContent` | `card-content` | Horizontal padding only |
| `CardFooter` | `card-footer` | Muted bg, border-top, rounded-b-xl |

```tsx
<Card size="sm">
  <CardHeader>
    <CardTitle>Active Books</CardTitle>
    <CardAction><Button size="icon-sm" variant="ghost"><PlusIcon /></Button></CardAction>
  </CardHeader>
  <CardContent>…</CardContent>
  <CardFooter>…</CardFooter>
</Card>
```

---

### 2.4 Dialog (`frontend/src/components/ui/dialog.tsx`)

Radix `Dialog.Root` with custom overlay and content. The content is `max-w-sm` (expandable via `className`), centered, `rounded-xl`, `bg-popover`, `ring-1 ring-foreground/10`.

**Key props on `DialogContent`:**
- `showCloseButton` (default `true`) — renders an `icon-sm` ghost Button with `XIcon` at `top-2 right-2`

**Key props on `DialogFooter`:**
- `showCloseButton` (default `false`) — appends an outline "Close" button

Overlay uses `bg-black/10 backdrop-blur-xs`. Open/close uses `data-open` / `data-closed` CSS data attributes for animation.

```tsx
<Dialog open={open} onOpenChange={setOpen}>
  <DialogTrigger asChild>
    <Button size="sm">New Book</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Create Book</DialogTitle>
      <DialogDescription>Fill in details for your new book project.</DialogDescription>
    </DialogHeader>
    {/* form fields */}
    <DialogFooter showCloseButton>
      <Button onClick={handleCreate}>Create</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

---

### 2.5 PageCard (`frontend/src/components/ui/page-card.tsx`)

Thumbnail + name + status badge tile for the "Recently Generated Pages" grid.

**Props:**

| Prop | Type | Default | Notes |
|---|---|---|---|
| `name` | `string` | required | Truncated to one line |
| `status` | `PageStatus` | required | Drives badge variant via `STATUS_VARIANT_MAP` |
| `thumb` | `ReactNode` | — | Content inside 90px thumbnail area |
| `thumbBg` | `string` | `var(--muted)` | CSS background for thumbnail (pass a var, not a hex) |

Thumbnail height: 90px. Hover: `border-[var(--brand-accent)]` + `shadow-[var(--shadow-card-md)]`. Focus: `outline-2 outline-[var(--ring)]`.

```tsx
<PageCard
  name={page.concept}
  status={page.status}
  thumb={book.emoji}
  thumbBg="var(--muted)"
/>
```

Always use `pageImageSrc(page.image_path)` (from `frontend/src/lib/api.ts`) when rendering an actual image in the thumb slot — never construct `/storage/` URLs by hand.

---

### 2.6 ProgressBar (`frontend/src/components/ui/progress.tsx`)

Thin 4px horizontal bar. Fill color: `var(--brand-accent)`. Track color: `var(--border)`. Rounded ends.

**Props:**

| Prop | Type | Default | Notes |
|---|---|---|---|
| `value` | `number` | required | 0–100; clamped internally |
| `showLabel` | `boolean` | `false` | Renders label below bar |
| `label` | `string` | `"{value}% done"` | Override the default label text |

Has `role="progressbar"` with `aria-valuenow/min/max`. Transition: `duration-300`.

```tsx
// Inside BookListItem / PrintReadiness panel
<ProgressBar value={book.progress_pct} />

// With label
<ProgressBar value={72} showLabel label="72 of 100 pages approved" />
```

---

### 2.7 StatCard (`frontend/src/components/ui/stat-card.tsx`)

Dashboard metric tile: label / big value / optional sub-text.

**Props:** `label` (string), `value` (ReactNode), `sub` (ReactNode, optional).

Styling: `rounded-[10px]`, `border border-[var(--border)]`, `bg-[var(--card)]`, `shadow-[var(--shadow-card)]`, padding `px-5 py-[18px]`. Label: 12px uppercase tracked. Value: 28px bold. Sub: 12px muted.

```tsx
<StatCard
  label="Pages This Week"
  value={data.pages_this_week}
  sub={<span><span className="font-semibold text-[var(--status-green)]">↑ {n}</span> generated</span>}
/>
```

---

### 2.8 Sonner / Toaster (`frontend/src/components/ui/sonner.tsx`)

Wrapper around the `sonner` library. Mounted once in `App.tsx` at `<Toaster position="bottom-right" richColors />`. Themed to match app CSS vars (`--normal-bg`, `--normal-border`, `--border-radius`).

Icons are Lucide: `CircleCheckIcon` (success), `InfoIcon` (info), `TriangleAlertIcon` (warning), `OctagonXIcon` (error), `Loader2Icon animate-spin` (loading).

Import and call `toast` from `@/components/ui/sonner`:
```tsx
import { toast } from "@/components/ui/sonner"

toast.success("Settings saved!")
toast.error(`Failed to save: ${String(err)}`)
toast.info("Opening new book…")
```

Do not import `toast` directly from `sonner` — always use the re-export to stay in sync with app theming.

---

### 2.9 AppSidebar (`frontend/src/components/ui/app-sidebar.tsx`)

Dark warm-stone sidebar. Width: `w-[220px]`, `bg-[var(--sidebar)]`, `text-[var(--sidebar-foreground)]`.

**Sub-components:**

| Component | Purpose |
|---|---|
| `AppSidebar` | `<aside>` wrapper, full height flex column |
| `SidebarLogo` | Logo lockup with icon, title, subtitle. Props: `icon`, `title`, `subtitle` |
| `SidebarSection` | Labeled group of nav items. `label` prop renders 10px uppercased section label |
| `SidebarNavItem` | Single nav row. Props: `icon` (emoji/ReactNode), `active` (bool), `badge` (number/string) |
| `SidebarFooter` | `mt-auto` sticky footer with top border, holds Settings item |

`SidebarNavItem` active state: `bg-[var(--sidebar-accent)] font-medium text-[var(--sidebar-accent-foreground)]`. Badge: amber pill (`bg-[var(--brand-accent)] text-white`). Sets `aria-current="page"` when active. Keyboard: `role="button" tabIndex={0}`, `onKeyDown` for Enter/Space in `App.tsx`.

```tsx
<AppSidebar className="h-screen sticky top-0 shrink-0">
  <SidebarLogo />
  <SidebarSection label="Workspace">
    <SidebarNavItem icon="⊞" active={isActive("/")} onClick={() => navigate("/")}>Dashboard</SidebarNavItem>
    <SidebarNavItem icon="📖" badge={books?.length} onClick={() => navigate("/books")}>Book Projects</SidebarNavItem>
  </SidebarSection>
  <SidebarFooter>
    <SidebarNavItem icon="⚙️" onClick={() => navigate("/settings")}>Settings</SidebarNavItem>
  </SidebarFooter>
</AppSidebar>
```

---

### 2.10 BookListItem (`frontend/src/components/ui/book-list-item.tsx`)

Row item inside the Active Book Projects panel.

**Props:**

| Prop | Type | Default |
|---|---|---|
| `title` | `string` | required |
| `thumb` | `ReactNode` | — |
| `thumbBg` | `string` | `#f5f5f4` |
| `thumbColor` | `string` | `#78716c` |
| `badgeVariant` | Badge variant | `"gray"` |
| `badgeLabel` | `string` | — |
| `meta` | `string` | — |
| `progress` | `number` | — |

Thumbnail: `42×54px`, rounded. Row border: bottom divider (`border-[var(--border)]`), last child no border. Hover: `bg-[var(--background)]`. Includes `ProgressBar` when `progress` is provided.

```tsx
<BookListItem
  thumb={book.emoji}
  thumbBg="#fef3c7"
  thumbColor="#92400e"
  title={book.title}
  badgeVariant="blue"
  badgeLabel="In Progress"
  meta={`${book.page_count} / ${book.target_page_count} pages`}
  progress={book.progress_pct}
  onClick={() => navigate(`/books/${book.id}`)}
/>
```

---

### 2.11 Forms & Inputs

There is no shared `<Input>` component. Form controls are styled inline wherever they appear. All new inputs must follow the patterns below.

**Text input / number input** (from `BooksPage.tsx`, `BookDetailPage.tsx` style-guide dialog):

```tsx
<input
  type="text"
  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
/>
```

**Textarea** (from `BookDetailPage.tsx` AddPageDialog):

```tsx
<textarea
  rows={3}
  className="w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] placeholder-[var(--muted-foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
/>
```

**Select** (from `SettingsPage.tsx`):

```tsx
<select
  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
>
```

**Canonical standard for any new input type:**
`rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20`

- All inputs must have an associated `<label>` — see §5.3
- Styled radio buttons use the wrapping `<label>` pattern — see §4.5
- No bare `<input>` without a label

---

### 2.12 ProviderModelSection (`frontend/src/features/settings/SettingsPage.tsx`)

Reusable settings block for picking an AI provider + model. The Admin page (`/admin`) renders three identical instances: **Concept Model**, **Prompt Model**, and **Image Generation**.

Each section contains:
1. A labeled radio list of providers (styled per §4.5 — amber border + pale-amber background when selected)
2. A `<select>` for the model (§2.11 select style), shown only when the provider supports multiple models
3. A `<Badge>` indicating configuration state: `variant="green" dot` ("Configured") or `variant="yellow" dot` ("Not Configured")
4. A Save button that follows the §4.3 dirty-state pattern — enabled only when `dirty && selectedProvider`

Structure:

```tsx
<div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
  <div className="mb-4 flex items-center justify-between">
    <div>
      <h2 className="text-[15px] font-semibold text-[var(--foreground)]">{title}</h2>
      <p className="text-[13px] text-[var(--muted-foreground)]">{description}</p>
    </div>
    <Badge variant={isConfigured ? "green" : "yellow"} dot>
      {isConfigured ? "Configured" : "Not Configured"}
    </Badge>
  </div>
  {/* Radio list — §4.5 pattern */}
  {/* Model <select> — §2.11 pattern */}
  <Button size="sm" disabled={!dirty || !selectedProvider || isPending} onClick={handleSave}>
    {isPending ? "Saving…" : "Save"}
  </Button>
</div>
```

**Sidebar nav:** the Admin page is a `SidebarFooter` item at route `/admin` with icon `⚙️` label "Admin", replacing the former "Settings" item.

---

### 2.13 Tables

No table component exists yet. When one is introduced, follow this standard and document it here:

- Wrap in a `PanelCard` container (see §3.5)
- Header row: `bg-[var(--muted)] text-[var(--muted-foreground)]` with `text-[11px] font-semibold uppercase tracking-[0.04em]`
- Row dividers: `border-b border-[var(--border)]`; last row has no bottom border
- Cell padding: `px-4 py-3`
- Hover row: `hover:bg-[var(--accent)]`
- Use `<caption className="sr-only">` for accessibility when the table context is not otherwise labeled

When a table component is built, add its file path to §7.

---

### 2.14 Alerts & Inline Messages

Two distinct patterns exist; use the right one for the context.

**Inline error banner** (data-load failures — from `SettingsPage.tsx`, `BooksPage.tsx`, `BookDetailPage.tsx`):

```tsx
<div className="rounded-xl border border-[var(--status-red-bg)] bg-[var(--status-red-bg)] px-5 py-4 text-sm text-[var(--status-red)]">
  Failed to load providers. Ensure the backend is running.
</div>
```

Use this pattern for persistent errors that block rendering (provider load failure, book load failure, page load failure). Never use `toast` for these — the user needs a persistent, visible message.

**Print Check Notes panel** (contextual warning — from `PageEditorPage.tsx`):

```tsx
<div className="rounded-xl border border-[var(--status-yellow-bg)] bg-[var(--status-yellow-bg)] p-4">
  <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-[var(--status-yellow)]">
    Print Check Notes
  </p>
  <p className="text-[12.5px] text-[var(--foreground)]">{notes}</p>
</div>
```

Use yellow panel for non-blocking contextual warnings that the user should read but that don't prevent rendering.

**Toasts** (transient feedback): use for mutation success/error, navigation hints. See §4.1 and §5.6 (Error Handling). Do not use toasts for persistent or render-blocking messages.

---

### 2.15 Empty States

Empty states follow a centered layout: large emoji/icon + title text + helper text + optional CTA button(s).

**Pattern** (from `BooksPage.tsx` empty books state and `PageEditorEmptyState` in `App.tsx`):

```tsx
<div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
  <span className="text-5xl" aria-hidden="true">📖</span>
  <div>
    <p className="text-[15px] font-semibold text-[var(--foreground)]">No books yet</p>
    <p className="mt-1 text-[13px] text-[var(--muted-foreground)]">
      Create your first coloring book project to get started.
    </p>
  </div>
  <Button onClick={…}>+ New Book</Button>
</div>
```

Inline filtered-grid empty state (from `BookDetailPage.tsx` PageGrid):

```tsx
<div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
  <span className="text-4xl" aria-hidden="true">🖼</span>
  <p className="text-[13.5px] text-[var(--muted-foreground)]">No pages with status "…"</p>
</div>
```

Placeholder views (`PlaceholderViews.tsx`) use the more elaborate hero-card pattern with a `rounded-2xl` card, large emoji (`text-5xl`), bold title, accent subtitle, description, and action buttons — appropriate for entire unimplemented routes.

Rules:
- Emoji must have `aria-hidden="true"` on the wrapping `<span>`
- Always include a helper text line explaining what to do next
- CTA button is optional but preferred when there is a clear action

---

### 2.16 Loaders

Three loading forms are used in the project; pick the right one for the context.

| Form | When to use | Reference |
|---|---|---|
| **Skeleton pulse** | Full data-load states — list pages, stat cards, dialogs waiting for data | §4.2 |
| **ProgressBar** | Quantifiable progress: book completion, page count percentage | §2.6 |
| **`Loader2Icon animate-spin`** | In-flight mutation feedback inside toasts (Sonner loading state); also used inline as a small border-spinner in tight button contexts | `frontend/src/components/ui/sonner.tsx` |

Inline button spinner (border-based, used in PageEditorPage button during generation):
```tsx
<span className="inline-block size-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
```

Never use a full-page blocking overlay for loading — use skeletons in place and keep the shell stable.

---

## 3. Layout Patterns

### 3.1 Shell Layout

`App.tsx` renders a full-viewport flex row:

```
┌─────────────────────────────────────────────────────┐
│ <aside> AppSidebar (220px, sticky, h-screen)        │
│          <main> flex-1, min-w-0, overflow-hidden    │
│                 <Routes> → page components          │
└─────────────────────────────────────────────────────┘
```

```tsx
// Shell (from App.tsx)
<div className="flex h-screen overflow-hidden bg-[var(--background)]">
  <AppNav />  {/* AppSidebar wrapper */}
  <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
    <Routes>…</Routes>
  </main>
</div>
```

The `<Toaster>` mounts outside the shell div, at the `App` root level.

---

### 3.2 Sidebar Navigation Structure

Three `SidebarSection` groups + one `SidebarFooter`:

| Section | Items |
|---|---|
| **Workspace** | Dashboard (`/`), Book Projects (`/books`), Workflow (`/workflow`), Page Editor (`/editor`), Agent Console (`/agents`) |
| **Library** | Inspiration (`/inspiration`), My Books (`/my-books`), Search Market (`/market`) |
| **Production** | Quality Check (`/quality`), Export Center (`/export`), Print Prep (`/print-prep`) |
| **Footer** | Settings (`/settings`) |

Book Projects badge shows the live count from `useBooks()`. Active state uses `location.pathname.startsWith(path)` — except `/` which requires exact match.

---

### 3.3 Page Header Pattern

Every implemented page has a sticky top-bar `<header>` with a consistent structure:

```tsx
<header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
  <div>
    <h1 className="text-[16px] font-semibold text-[var(--foreground)]">{title}</h1>
    <p className="text-[13px] text-[var(--text-muted)]">{subtitle}</p>
  </div>
  <div className="ml-auto flex gap-2">
    {/* Action buttons — size="sm", variant="outline" or "default" */}
  </div>
</header>
```

- Background: `bg-[var(--card)]` (white), separated from content by `border-b border-[var(--border)]`
- CTA buttons: `size="sm"`, at most one primary, one outline
- No `h1` should appear in page content below this header

---

### 3.4 Content Max-Width Pattern

Pages that benefit from a constrained reading width use:

```tsx
{/* Seen in SettingsPage */}
<div className="flex-1 overflow-y-auto p-6">
  <div className="mx-auto max-w-2xl">
    {/* page content */}
  </div>
</div>
```

Dashboard uses full width with an explicit two-column grid:

```tsx
<div className="grid grid-cols-[1fr_320px] gap-5">
  <div className="min-w-0">{/* left: lists, page grid */}</div>
  <div className="flex flex-col gap-5">{/* right: agents, actions, readiness, activity */}</div>
</div>
```

The stat cards row above the two-column grid uses `grid grid-cols-3 gap-4`.

---

### 3.5 Panel / PanelCard Pattern

Dashboard uses a local `PanelCard` wrapper (not the shadcn `Card`):

```tsx
<div className="overflow-hidden rounded-[10px] border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-card)]">
  {children}
</div>
```

Settings sections use borderless card-like rows:
```tsx
<div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">…</div>
```

Both patterns are valid. Use `PanelCard` for dashboard-style list panels; use the inline div pattern for settings-style form sections.

---

### 3.6 Breakpoints & Responsive Behavior

**Current state:** This is a desktop-first, single-operator production tool. No responsive breakpoints or mobile layout are implemented — this is intentional, not an oversight.

| Constraint | Value | Source |
|---|---|---|
| Shell overflow | `h-screen overflow-hidden` (no scroll on the root) | `App.tsx` Shell |
| Sidebar | `w-[220px] shrink-0 sticky top-0` — fixed width, never collapses | `App.tsx` AppNav |
| Content area | `flex-1 min-w-0 overflow-hidden` — fills remaining viewport | `App.tsx` Shell |
| Minimum usable width | ~900px (220px sidebar + dashboard grid columns) | Layout math |

**Guidance:**
- Do not introduce `sm:`, `md:`, `lg:`, or `xl:` Tailwind breakpoint classes for new layout changes without explicit approval — they imply a mobile experience that does not currently exist.
- Do not add hamburger menus, collapsible sidebars, or stacked-column layouts.
- If responsive support is added in the future, use Tailwind's default breakpoints (`sm` 640px / `md` 768px / `lg` 1024px / `xl` 1280px) and document the changes here.
- The `BookDetailPage.tsx` page grid uses `grid-cols-3 xl:grid-cols-4` — this is the only approved breakpoint use, limited to widening a content grid.

---

## 4. Interaction Patterns

### 4.1 Toasts (Sonner)

Always use `toast` from `@/components/ui/sonner`. Toaster is mounted in `App.tsx` at `position="bottom-right"` with `richColors`.

| Scenario | Call |
|---|---|
| Successful save | `toast.success("Settings saved!")` |
| Mutation error | `toast.error(\`Failed to save: ${String(err)}\`)` |
| Navigation hint | `toast.info("Opening new book…")` |

Do not use `alert()` or inline error text as a replacement for toast feedback on mutations.

---

### 4.2 Loading Skeletons

Use an animated pulse div matching the shape of the real content:

```tsx
function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)] ${className}`} />
}
```

Pattern: render the skeleton inside the same container structure as the real content, matching height/width. For list rows: show 3 placeholder rows matching the real item layout. For stat cards: `h-[90px]` skeleton per card.

---

### 4.3 Dirty-State Save Buttons

When a form has unsaved changes, the Save button is enabled only when `dirty === true` and a required field is set. Disable it while the mutation is pending:

```tsx
<Button
  onClick={handleSave}
  disabled={updateSettings.isPending || !dirty || !selectedProvider}
  size="sm"
>
  {updateSettings.isPending ? "Saving…" : "Save Settings"}
</Button>
```

Always call `setDirty(false)` on successful save and show `toast.success`.

---

### 4.4 PageStatus → Badge Mapping

The `STATUS_VARIANT_MAP` in `page-card.tsx` is the canonical mapping. Reproduce it wherever you need to render a status badge outside of `PageCard`:

| PageStatus | Badge variant | Color |
|---|---|---|
| `idea` | `idea` | gray |
| `prompt` | `prompt` | yellow |
| `generated` | `generated` | purple |
| `review` | `review` | blue |
| `revision` | `revision` | red |
| `approved` | `approved` | green |
| `print_ready` | `print_ready` | green |
| `exported` | `exported` | gray |

Human-readable labels come from `PAGE_STATUS_LABELS` (exported from `badge.tsx`). Always use `PAGE_STATUS_LABELS[status]` as badge text — do not hardcode strings.

---

### 4.5 Radio Selection Pattern (Settings)

Use a styled `<label>` wrapping a visually hidden `<input type="radio">` for provider/option selection:

```tsx
<label className={`flex cursor-pointer items-center gap-3 rounded-lg border-2 px-4 py-3 transition-all duration-100 ${
  isSelected
    ? "border-[var(--brand-accent)] bg-[var(--brand-accent-light)]"
    : "border-[var(--border)] bg-[var(--background)] hover:border-[var(--brand-accent)]/40"
}`}>
  <input type="radio" name="provider" value={id} checked={isSelected} onChange={…} className="accent-[var(--brand-accent)]" />
  {/* label content */}
</label>
```

Selected state: amber border + pale amber background. Always include a visible `<label>` element wrapping the `<input>` for accessibility.

---

### 4.6 Activity Dot Colors

The Recent Activity panel uses small colored dots (6px circles) keyed on event `kind`:

| Kind | Tailwind class |
|---|---|
| `approved` | `bg-[var(--status-green)]` |
| `generated` | `bg-[var(--status-purple)]` |
| `flagged` | `bg-[var(--status-red)]` |
| `exported` | `bg-[var(--status-gray)]` |
| _(default)_ | `bg-[var(--status-blue)]` |

---

### 4.7 AI Action Button + Proposal/Review Pattern

Used in `PageEditorPage.tsx` for AI-assisted text generation. Two variants:

**Propose → review → accept/discard** (Concept Refine):
1. "Refine with AI" button triggers `POST /api/pages/{id}/refine-concept`; button shows inline spinner and is disabled during the request.
2. On success, a bordered review card appears below:
   ```tsx
   <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
     <p className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-[var(--muted-foreground)]">
       AI Suggestion
     </p>
     <p className="mb-3 text-[13px] text-[var(--foreground)]">{proposal}</p>
     <div className="flex gap-2">
       <Button size="sm" onClick={handleAccept}>Accept</Button>
       <Button size="sm" variant="outline" onClick={handleDiscard}>Discard</Button>
     </div>
   </div>
   ```
3. **Accept** writes the proposal into the local field (no auto-save). **Discard** clears the card. Dirty-state save (§4.3) still applies — the user must explicitly save.

**Pre-fill + edit** (Prompt Write):
1. "Write with AI" button triggers `POST /api/pages/{id}/write-prompt`; button disabled + spinner during request.
2. On success, the returned `{positive, negative}` values are written directly into the prompt editor fields for the user to review and edit before saving.
3. No separate review card — the editor itself is the review surface.

**Error handling:** both paths use `toast.error(…)` on failure (network error or 400 provider-not-configured). No inline error banner — this is a transient action, not a data-load failure. See §2.14 vs §4.1 for the distinction.

**Tokens:** review card uses `rounded-xl border border-[var(--border)] bg-[var(--card)]`. The section label inside uses `text-[var(--muted-foreground)]` uppercase, matching the Print Check Notes panel style (§2.14).

---

## 5. Accessibility Requirements

### 5.1 Focus Rings

The global `:focus-visible` rule applies `outline: 2px solid var(--ring); outline-offset: 2px` to all interactive elements. `--ring` equals `--brand-accent` (`#b45309` light / `#d97706` dark).

Interactive custom elements (non-button `role="button"` divs, `PageCard`, `SidebarNavItem`, `BookListItem`) implement their own focus-visible style using:
```
focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-[-1px]
```
(negative offset for elements with a border, so the ring appears inside the border rather than outside.)

Never suppress `:focus-visible` outlines.

### 5.2 Keyboard Navigation

- `SidebarNavItem` and `BookListItem`/`PageCard` are `role="button" tabIndex={0}` divs. They must have `onKeyDown` handlers for `Enter` and `Space` — wire them in the calling component (see `AppNav` in `App.tsx` as the reference implementation).
- `SidebarNavItem` sets `aria-current="page"` when `active`.
- `ProgressBar` has `role="progressbar"` with `aria-valuenow`, `aria-valuemin`, `aria-valuemax`.

### 5.3 Labels and Selects

- Every `<select>` must have an associated `<label>` (visible, not sr-only).
- Radio groups use wrapping `<label>` elements (see Settings pattern above). No bare `<input type="radio">` without a label.
- Icon-only buttons (`size="icon"`, `size="icon-sm"`) must include `<span className="sr-only">…</span>`.

### 5.4 Color Contrast

- Body text (`--foreground` on `--background`): warm stone dark on warm off-white — check passes.
- Muted text (`--muted-foreground` / `--text-muted`) on card white: borderline — use only for secondary/helper text, never for primary labels or interactive affordances.
- Status colors on their `-bg` variants are chosen for readability; always render status text on the matching `*-bg`, not on white directly.
- Dark mode tokens (`--foreground: #fafaf9` on `--background: #0c0a09`) are defined but no dark-mode toggle is implemented yet.

### 5.5 Decorative Content

Emoji thumbnails and icons use `aria-hidden="true"`. Screen-reader-only alternatives are provided via `sr-only` spans where needed (dialog close button).

---

### 5.6 Error Handling

| Error type | Pattern | Never do |
|---|---|---|
| Mutation failure (save, create, export) | `toast.error(String(err))` | Silent failure; `alert()` |
| Data-load failure (query `isError`) | Inline error banner (§2.13) in place of the loading content | Replace whole page with an error route |
| No data / empty state | Empty state pattern (§2.14) — not an error banner | Show a blank region with no explanation |
| Pending / optimistic | Disable the triggering button (`isPending`), show text like "Saving…" or a spinner | Block the whole UI |

Every error path must surface feedback visible to the user. Silent failures are forbidden.

---

### 5.7 Animation Standards

Keep motion subtle and purposeful. Do not add animations for decorative effect.

**Durations in use (confirmed from codebase):**

| Duration | Use |
|---|---|
| `duration-100` | Hover state transitions on interactive elements (radio labels, filter tab buttons) |
| `duration-150` | Card hover (border, shadow), page grid item hover |
| `duration-300` | `ProgressBar` fill transition (`transition-all duration-300` in `progress.tsx`) |
| Dialog enter/exit | `data-open` / `data-closed` CSS data attributes on `DialogContent` and `DialogOverlay` — no JS animation, CSS-driven |

**Rules:**
- Prefer `transition-all` with a named duration class; do not use arbitrary `duration-[Xms]` values
- Do not add `transition` classes to elements that do not change a visible CSS property
- Do not use `animate-bounce`, `animate-ping`, or similar attention-grabbing utilities on persistent UI elements
- `animate-pulse` is reserved for skeleton loaders (§4.2)
- `animate-spin` is reserved for the `Loader2Icon` loading spinner

---

### 5.8 Feedback & Confirmation

**Success / error:** every mutation must surface a `toast.success` or `toast.error` on completion — even if the UI already updates optimistically. See §4.1.

**Status changes:** any page-status transition (e.g. approving a page, flagging a revision) must surface a toast confirming the new status.

**Destructive / irreversible actions:** actions that cannot be undone (deleting a book, deleting a page, overwriting a style guide) must use a confirmation `Dialog` before proceeding. The dialog must:
- Clearly state what will be deleted or overwritten
- Use a `destructive` variant Button for the confirm action
- Offer an "Cancel" outline button
- Not auto-dismiss on backdrop click (set `onOpenChange` to guard against accidental dismissal)

**Pending state:** the triggering button must be disabled with `isPending` and show in-progress text (e.g. "Deleting…") while the mutation is in flight.

---

## 6. Forbidden UI Patterns

| Pattern | Why forbidden | What to do instead |
|---|---|---|
| Hardcoded hex colors in JSX/CSS | Breaks theming and dark-mode consistency | Use `var(--token-name)` CSS variables defined in `index.css` |
| Inventing new status colors | Status palette is fixed and maps to workflow states | Use one of the six existing status tokens; add to the palette in `index.css` + `badge.tsx` together if truly needed |
| `style={{ color: '#b45309' }}` etc. | Same as hardcoded hex | Replace with `text-[var(--brand-accent)]` Tailwind class or CSS var |
| Rendering `page.image_path` directly in `<img src>` | `/storage/` prefix breaks R2-backed absolute URLs | Always call `pageImageSrc(page.image_path)` from `frontend/src/lib/api.ts` |
| Constructing `/storage/filename` strings manually | Same as above | Use `pageImageSrc()` |
| `toast` imported from `sonner` directly | Bypasses app theme wiring | Import from `@/components/ui/sonner` |
| Hardcoded status label strings (e.g. `"Print Ready"`) | Gets out of sync with `PAGE_STATUS_LABELS` | Use `PAGE_STATUS_LABELS[status]` from `badge.tsx` |
| `role="button"` div without `tabIndex={0}` and keyboard handler | Breaks keyboard navigation | Add both, see `SidebarNavItem` as reference |
| Icon-only button without `sr-only` label | Screen readers cannot identify the action | Always add `<span className="sr-only">{label}</span>` |
| Importing `PageStatus` type from anywhere other than `badge.tsx` or `lib/api.ts` | Type duplication | `PageStatus` is exported from both; use `@/lib/api` for API-layer code, `@/components/ui/badge` for UI-layer code |
| `text-[#hex]` Tailwind arbitrary values | Defeats the design token system | Use `text-[var(--token)]` |

---

### 6.1 Components That Must Not Be Changed Without Approval

**Button and Badge variant names** are wired to Figma via Code Connect (`data-slot="button"` / `data-slot="badge"` attributes aligned with Figma variant names). Renaming or removing a variant in code breaks the Figma ↔ code mapping silently. Any such change must be made in Figma and code simultaneously, and the Code Connect file updated to match. See §7 for the Figma design file link.

**The status palette** (`--status-{green,blue,yellow,red,purple,gray}` and their `-bg` pairs) is fixed. Do not add, rename, or reorder tokens without updating `index.css`, `badge.tsx`, and this document together.

---

### 6.2 Legacy Quirks That Exist for a Known Reason

**Dark-mode tokens are fully defined but there is no dark-mode toggle.** All dark values in the `@media (prefers-color-scheme: dark)` block (and the dark token columns in §1.1) are intentional and complete — they are not dead code. They exist so that dark mode can be enabled without a rework of the token system. Do not remove them.

**The `pageImageSrc()` helper exists because page image paths can be either relative paths (local storage) or absolute R2/CDN URLs.** Raw concatenation of `/storage/` + `page.image_path` will break for absolute URLs. Always call `pageImageSrc(page.image_path)` from `frontend/src/lib/api.ts` — this is documented in §2.5 and §6 (main table) but repeated here because it is a common mistake.

---

### 6.3 Intentionally Constrained Decisions

These decisions are final for the current product phase. Do not change them to match generic conventions or "best practice" defaults that don't fit this product:

| Constraint | What it is | Why it must not change |
|---|---|---|
| **Warm-stone + amber palette** | `#b45309` amber brand accent, `#f7f5f0` warm off-white background, `#1c1917` stone foreground | This is the product's identity. Do not swap to generic blue/purple/gray "AI-default" aesthetics or Inter-font layouts |
| **14px base font** | `font-size: 14px` on `<html>` | Sized for dense, data-rich production UI. Do not up-scale to 16px browser default |
| **Desktop-only fixed layout** | `h-screen overflow-hidden`, fixed `w-[220px]` sidebar, no responsive breakpoints | This is a single-operator desktop studio tool. Mobile layout is out of scope |
| **No external font loading** | `-apple-system` font stack via `var(--font-sans)` | Avoids FOUT, reduces network requests, keeps the UI feeling native on macOS |

---

## 7. Reference: Key File Locations

| Concern | File |
|---|---|
| All CSS custom properties / design tokens | `frontend/src/index.css` |
| Button component | `frontend/src/components/ui/button.tsx` |
| Badge + PageStatus type + PAGE_STATUS_LABELS | `frontend/src/components/ui/badge.tsx` |
| Card sub-components | `frontend/src/components/ui/card.tsx` |
| Dialog | `frontend/src/components/ui/dialog.tsx` |
| PageCard | `frontend/src/components/ui/page-card.tsx` |
| ProgressBar | `frontend/src/components/ui/progress.tsx` |
| StatCard | `frontend/src/components/ui/stat-card.tsx` |
| Toast (Sonner wrapper) | `frontend/src/components/ui/sonner.tsx` |
| Sidebar components | `frontend/src/components/ui/app-sidebar.tsx` |
| BookListItem | `frontend/src/components/ui/book-list-item.tsx` |
| App shell + route map + sidebar nav | `frontend/src/App.tsx` |
| Page header / content-max-width pattern | `frontend/src/features/dashboard/DashboardPage.tsx`, `frontend/src/features/settings/SettingsPage.tsx` |
| API client + `pageImageSrc` helper | `frontend/src/lib/api.ts` |
| Admin page (ProviderModelSection — §2.12) | `frontend/src/features/settings/SettingsPage.tsx` |
| Page Editor AI buttons + proposal card (§4.7) | `frontend/src/features/editor/PageEditorPage.tsx` |
| Figma design file | https://www.figma.com/design/mC044MH1WirZ5Hzh2PILML |
