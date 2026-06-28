/**
 * App — React Router shell + QueryClient provider.
 *
 * Route map:
 *   /               → DashboardPage
 *   /gallery        → GalleryPage (U3 component gallery)
 *   /books          → BooksPage (U11)
 *   /books/new      → BooksPage (scrolls to new dialog)
 *   /books/:id      → BookDetailPage (U11)
 *   /workflow       → WorkflowPage (U11)
 *   /editor         → PageEditorPage (list/empty state)
 *   /editor/:pageId → PageEditorPage (U11)
 *   /agents         → AgentConsolePlaceholder (U12)
 *   /inspiration    → InspirationPlaceholder (U12)
 *   /my-books       → MyBooksPlaceholder (U12)
 *   /market         → SearchMarketPlaceholder (U12)
 *   /quality        → QualityCheckPlaceholder (U12)
 *   /export         → ExportCenterPlaceholder (U12)
 *   /print-prep     → PrintPrepPlaceholder (U12)
 *   /admin          → SettingsPage (U11/U8)
 */
import {
  BrowserRouter,
  Routes,
  Route,
  useLocation,
  useNavigate,
} from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "@/components/ui/sonner"
import {
  AppSidebar,
  SidebarLogo,
  SidebarSection,
  SidebarNavItem,
  SidebarFooter,
} from "@/components/ui/app-sidebar"
import { DashboardPage } from "@/features/dashboard/DashboardPage"
import { GalleryPage } from "@/features/gallery/GalleryPage"
import { ComingSoon } from "@/features/placeholders/ComingSoon"
import {
  AgentConsolePlaceholder,
  InspirationPlaceholder,
  MyBooksPlaceholder,
  SearchMarketPlaceholder,
  QualityCheckPlaceholder,
  ExportCenterPlaceholder,
  PrintPrepPlaceholder,
} from "@/features/placeholders/PlaceholderViews"
import { BooksPage } from "@/features/books/BooksPage"
import { BookDetailPage } from "@/features/books/BookDetailPage"
import { PageEditorPage } from "@/features/editor/PageEditorPage"
import { WorkflowPage } from "@/features/workflow/WorkflowPage"
import { SettingsPage } from "@/features/settings/SettingsPage"
import { useBooks } from "@/lib/api"

// ── Page Editor empty state ────────────────────────────────────────────────────

function PageEditorEmptyState() {
  return (
    <ComingSoon
      icon="🖼"
      title="Page Editor"
      description="Select a page from a Book Project to open it in the editor, or create a new page from the Book Detail view."
    />
  )
}

// ── Query client ───────────────────────────────────────────────────────────────

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,    // 30 s
      retry: 1,
    },
  },
})

// ── Sidebar nav ────────────────────────────────────────────────────────────────

/**
 * AppNav — the sidebar populated with all studio sections.
 * Uses React Router's NavLink so active state tracks the current route.
 */
function AppNav() {
  const location = useLocation()
  const navigate = useNavigate()
  const { data: books } = useBooks()

  function isActive(path: string) {
    if (path === "/") return location.pathname === "/"
    return location.pathname.startsWith(path)
  }

  function navItem(
    icon: string,
    label: string,
    path: string,
    badge?: number | string
  ) {
    return (
      <SidebarNavItem
        key={path}
        icon={icon}
        active={isActive(path)}
        badge={badge}
        onClick={() => navigate(path)}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") navigate(path) }}
      >
        {label}
      </SidebarNavItem>
    )
  }

  return (
    <AppSidebar className="h-screen sticky top-0 shrink-0">
      <SidebarLogo />

      <SidebarSection label="Workspace">
        {navItem("⊞", "Dashboard", "/")}
        {navItem("📖", "Book Projects", "/books", books?.length || undefined)}
        {navItem("🔄", "Workflow", "/workflow")}
        {navItem("🖼", "Page Editor", "/editor")}
        {navItem("🤖", "Agent Console", "/agents")}
      </SidebarSection>

      <SidebarSection label="Library">
        {navItem("💡", "Inspiration", "/inspiration")}
        {navItem("📚", "My Books", "/my-books")}
        {navItem("🔍", "Search Market", "/market")}
      </SidebarSection>

      <SidebarSection label="Production">
        {navItem("✅", "Quality Check", "/quality")}
        {navItem("📦", "Export Center", "/export")}
        {navItem("🖨", "Print Prep", "/print-prep")}
      </SidebarSection>

      <SidebarFooter>
        {navItem("⚙️", "Admin", "/admin")}
      </SidebarFooter>
    </AppSidebar>
  )
}

// ── Shell layout ───────────────────────────────────────────────────────────────

function Shell() {
  return (
    <div className="flex h-screen overflow-hidden bg-[var(--background)]">
      <AppNav />
      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/gallery" element={<GalleryPage />} />

          {/* Book Projects (U11) */}
          <Route path="/books" element={<BooksPage />} />
          <Route path="/books/new" element={<BooksPage />} />
          <Route path="/books/:id" element={<BookDetailPage />} />

          {/* Workflow (U11) */}
          <Route path="/workflow" element={<WorkflowPage />} />

          {/* Page Editor (U11) */}
          <Route path="/editor" element={<PageEditorEmptyState />} />
          <Route path="/editor/:pageId" element={<PageEditorPage />} />

          {/* Agent Console (U12 placeholder) */}
          <Route path="/agents" element={<AgentConsolePlaceholder />} />

          {/* Library (U12 placeholders) */}
          <Route path="/inspiration" element={<InspirationPlaceholder />} />
          <Route path="/my-books" element={<MyBooksPlaceholder />} />
          <Route path="/market" element={<SearchMarketPlaceholder />} />

          {/* Production (U12 placeholders) */}
          <Route path="/quality" element={<QualityCheckPlaceholder />} />
          <Route path="/export" element={<ExportCenterPlaceholder />} />
          <Route path="/print-prep" element={<PrintPrepPlaceholder />} />

          {/* Admin (U11/U8) */}
          <Route path="/admin" element={<SettingsPage />} />

          {/* Fallback */}
          <Route
            path="*"
            element={
              <ComingSoon
                icon="404"
                title="Page Not Found"
                description="This route doesn't exist. Head back to the Dashboard."
              />
            }
          />
        </Routes>
      </main>
    </div>
  )
}

// ── Root App ───────────────────────────────────────────────────────────────────

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Shell />
        <Toaster position="bottom-right" richColors />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
