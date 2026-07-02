/**
 * api.ts — Typed fetch client + TanStack Query hooks for the Coloring Book Studio API.
 *
 * All requests go through the Vite dev proxy (/api → http://127.0.0.1:8000).
 * In production, /api is served by FastAPI directly.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"

// ── Base fetch ─────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`API ${res.status}: ${text}`)
  }
  // Some endpoints return an empty body (204) or a blob (PDF export)
  const ct = res.headers.get("content-type") ?? ""
  if (ct.includes("application/json")) {
    return res.json() as Promise<T>
  }
  return res as unknown as T
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Resolve a page `image_path` to a usable <img> src.
 *
 * With STORAGE_BACKEND=r2 the backend returns a full absolute URL
 * (https://…r2.dev/…). With local storage it returns a relative path that is
 * served under /storage/. Prefixing an absolute URL with /storage/ breaks it,
 * so pass absolute URLs through unchanged.
 */
export function pageImageSrc(imagePath: string): string {
  return /^https?:\/\//i.test(imagePath) ? imagePath : `/storage/${imagePath}`
}

// ── Domain types ───────────────────────────────────────────────────────────────

export interface StyleGuide {
  id: string
  line_weight: string
  detail_level: string
  white_space: string
  motifs: string
  positive_prefix: string
  positive_suffix: string
  negative_prompt: string
  trim_width_in: number
  trim_height_in: number
  bleed_in: number
  margin_in: number
  target_dpi: number
}

export interface Book {
  id: string
  title: string
  emoji: string
  theme: string
  audience: string
  positioning: string
  target_page_count: number
  page_count: number
  approved_count: number
  progress_pct: number
  created_at: string
  updated_at: string
  style_guide: StyleGuide | null
}

export type PageStatus =
  | "idea"
  | "prompt"
  | "generated"
  | "review"
  | "revision"
  | "approved"
  | "print_ready"
  | "exported"

export interface TextLayer {
  id: string
  page_id: string
  content: string
  x_pct: number
  y_pct: number
  font_size: number
  font_family: string
  anchor: string
  visible: boolean
}

export interface Page {
  id: string
  book_id: string
  sort_order: number
  title: string | null
  concept: string
  status: PageStatus
  prompt: string | null
  negative_prompt: string | null
  image_path: string | null
  image_dpi: number | null
  image_width_px: number | null
  image_height_px: number | null
  is_pure_bw: boolean | null
  print_check_notes: string | null
  reference_image_id: string | null
  reference_image_url: string | null
  created_at: string
  updated_at: string
  text_layers: TextLayer[]
}

export interface PageVersion {
  id: string
  page_id: string
  version_num: number
  image_url: string | null
  svg_url: string | null
  prompt: string
  label: string | null
  notes: string | null
  dpi: number | null
  width_px: number | null
  height_px: number | null
  is_pure_bw: boolean | null
  created_at: string | null
  is_current: boolean
}

export type JobStatus = "queued" | "running" | "done" | "failed"

export interface Job {
  job_id: string
  page_id: string
  status: JobStatus
  error: string | null
  result_version: number | null
  created_at: string | null
  started_at: string | null
  finished_at: string | null
}

export interface DashboardStats {
  active_books: number
  pages_this_week: number
  print_ready_pages: number
}

export interface ActivityItem {
  text: string
  kind: "approved" | "flagged" | "generated" | "exported" | "style" | string
  when: string
}

export interface Agent {
  name: string
  description: string
  icon: string
  status: string
}

export interface PrintReadiness {
  book_id: string
  title: string
  ready_count: number
  total_count: number
}

export interface StatusSummary {
  idea: number
  prompt: number
  generated: number
  review: number
  revision: number
  approved: number
  print_ready: number
  exported: number
}

export interface ProviderModel {
  id: string
  label: string
}

export interface Provider {
  id: string
  label: string
  name?: string       // alias — some callers may pass name
  models: ProviderModel[]
  default_model: string
  configured: boolean
}

export interface ProvidersResponse {
  providers: Provider[]
}

export interface Settings {
  image_provider: string
  image_model: string
  concept_provider: string
  concept_model: string
  prompt_provider: string
  prompt_model: string
  image_configured: boolean
  concept_configured: boolean
  prompt_configured: boolean
}

// ── Books ──────────────────────────────────────────────────────────────────────

export function useBooks() {
  return useQuery<Book[]>({
    queryKey: ["books"],
    queryFn: () => apiFetch<Book[]>("/books"),
  })
}

export function useBook(id: string) {
  return useQuery<Book>({
    queryKey: ["books", id],
    queryFn: () => apiFetch<Book>(`/books/${id}`),
    enabled: !!id,
  })
}

export interface CreateBookInput {
  title: string
  theme?: string
  audience?: string
  positioning?: string
  emoji?: string
  target_page_count?: number
}

export function useCreateBook() {
  const qc = useQueryClient()
  return useMutation<Book, Error, CreateBookInput>({
    mutationFn: (data) =>
      apiFetch<Book>("/books", { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["books"] })
    },
  })
}

export function useUpdateBook() {
  const qc = useQueryClient()
  return useMutation<Book, Error, Partial<CreateBookInput> & { id: string }>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Book>(`/books/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: (book) => {
      void qc.invalidateQueries({ queryKey: ["books"] })
      void qc.invalidateQueries({ queryKey: ["books", book.id] })
    },
  })
}

export function useDeleteBook() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => apiFetch<void>(`/books/${id}`, { method: "DELETE" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["books"] }) },
  })
}

export function useBookStatusSummary(bookId: string) {
  return useQuery<StatusSummary>({
    queryKey: ["books", bookId, "status-summary"],
    queryFn: () => apiFetch<StatusSummary>(`/books/${bookId}/status-summary`),
    enabled: !!bookId,
  })
}

export function useUpdateStyleGuide() {
  const qc = useQueryClient()
  return useMutation<StyleGuide, Error, Partial<StyleGuide> & { bookId: string }>({
    mutationFn: ({ bookId, ...data }) =>
      apiFetch<StyleGuide>(`/books/${bookId}/style-guide`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),
    onSuccess: (_sg, { bookId }) => {
      void qc.invalidateQueries({ queryKey: ["books", bookId] })
    },
  })
}

// ── Pages ──────────────────────────────────────────────────────────────────────

export function usePages(bookId: string) {
  return useQuery<Page[]>({
    queryKey: ["pages", bookId],
    queryFn: () => apiFetch<Page[]>(`/pages/book/${bookId}`),
    enabled: !!bookId,
  })
}

export function usePage(pageId: string) {
  return useQuery<Page>({
    queryKey: ["pages", "detail", pageId],
    queryFn: () => apiFetch<Page>(`/pages/${pageId}`),
    enabled: !!pageId,
  })
}

export interface CreatePageInput {
  concept: string
  sort_order?: number
  title?: string
}

export function useCreatePage(bookId: string) {
  const qc = useQueryClient()
  return useMutation<Page, Error, CreatePageInput>({
    mutationFn: (data) =>
      apiFetch<Page>(`/pages/book/${bookId}`, { method: "POST", body: JSON.stringify(data) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pages", bookId] })
    },
  })
}

export function useUpdatePage() {
  const qc = useQueryClient()
  return useMutation<Page, Error, Partial<CreatePageInput> & { id: string; title?: string; status?: PageStatus; prompt?: string; negative_prompt?: string; reference_image_id?: string | null }>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<Page>(`/pages/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: (page) => {
      void qc.invalidateQueries({ queryKey: ["pages", page.book_id] })
      void qc.invalidateQueries({ queryKey: ["pages", "detail", page.id] })
    },
  })
}

export function useDeletePage() {
  const qc = useQueryClient()
  return useMutation<void, Error, { id: string; bookId: string }>({
    mutationFn: ({ id }) => apiFetch<void>(`/pages/${id}`, { method: "DELETE" }),
    onSuccess: (_v, { bookId }) => { void qc.invalidateQueries({ queryKey: ["pages", bookId] }) },
  })
}

export function useReorderPages(bookId: string) {
  const qc = useQueryClient()
  return useMutation<Page[], Error, string[]>({
    mutationFn: (pageIds) =>
      apiFetch<Page[]>(`/pages/book/${bookId}/reorder`, { method: "PATCH", body: JSON.stringify({ page_ids: pageIds }) }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["pages", bookId] }) },
  })
}

// ── Versions ──────────────────────────────────────────────────────────────────

export function useVersions(pageId: string) {
  return useQuery<PageVersion[]>({
    queryKey: ["versions", pageId],
    queryFn: () => apiFetch<PageVersion[]>(`/pages/${pageId}/versions`),
    enabled: !!pageId,
  })
}

export function useRestoreVersion(pageId: string) {
  const qc = useQueryClient()
  return useMutation<Page, Error, string>({
    mutationFn: (versionId) =>
      apiFetch<Page>(`/pages/${pageId}/versions/${versionId}/restore`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (page) => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", page.book_id] })
    },
  })
}

export function useUseVersionAsReference(pageId: string) {
  const qc = useQueryClient()
  return useMutation<Page, Error, string>({
    mutationFn: (versionId) =>
      apiFetch<Page>(`/pages/${pageId}/versions/${versionId}/use-as-reference`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (page) => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", page.book_id] })
      void qc.invalidateQueries({ queryKey: ["inspiration"] })
    },
  })
}

export function useUpdateVersion(pageId: string) {
  const qc = useQueryClient()
  return useMutation<PageVersion, Error, { versionId: string; label?: string; notes?: string }>({
    mutationFn: ({ versionId, ...data }) =>
      apiFetch<PageVersion>(`/pages/${pageId}/versions/${versionId}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
    },
  })
}

export function useDeleteVersion(pageId: string) {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (versionId) =>
      apiFetch<void>(`/pages/${pageId}/versions/${versionId}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
    },
  })
}

// ── Text Layers ───────────────────────────────────────────────────────────────

export interface CreateTextLayerInput {
  content: string
  x_pct?: number
  y_pct?: number
  font_size?: number
  font_family?: string
  anchor?: string
}

export function useCreateTextLayer(pageId: string) {
  const qc = useQueryClient()
  return useMutation<TextLayer, Error, CreateTextLayerInput>({
    mutationFn: (data) =>
      apiFetch<TextLayer>(`/pages/${pageId}/text-layers`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
    },
  })
}

export function useUpdateTextLayer(pageId: string) {
  const qc = useQueryClient()
  return useMutation<TextLayer, Error, Partial<CreateTextLayerInput> & { layerId: string }>({
    mutationFn: ({ layerId, ...data }) =>
      apiFetch<TextLayer>(`/pages/${pageId}/text-layers/${layerId}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
    },
  })
}

export function useDeleteTextLayer(pageId: string) {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (layerId) =>
      apiFetch<void>(`/pages/${pageId}/text-layers/${layerId}`, { method: "DELETE" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
    },
  })
}

// ── Jobs + generate→poll ───────────────────────────────────────────────────────

export function useJob(jobId: string | null) {
  return useQuery<Job>({
    queryKey: ["jobs", jobId],
    queryFn: () => apiFetch<Job>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const data = query.state.data
      if (!data) return 2000
      // Stop polling once the job reaches a terminal state
      return data.status === "done" || data.status === "failed" ? false : 2000
    },
  })
}

export interface GenerateOptions {
  auto_cleanup?: boolean
  vectorize?: boolean
  reference_image_id?: string | null
}

/**
 * useGeneratePage — enqueues a generation job then polls until done or failed.
 *
 * Call mutate({ pageId, options }); observe data.status to know when done.
 * The returned Job is kept up-to-date by useJob (via polling) once mutationFn
 * resolves the initial 202.
 */
export function useGeneratePage() {
  const qc = useQueryClient()
  return useMutation<Job, Error, { pageId: string; options?: GenerateOptions }>({
    mutationFn: async ({ pageId, options = {} }) => {
      const body = { auto_cleanup: true, vectorize: true, ...options }
      const initial = await apiFetch<Job>(`/pages/${pageId}/generate`, {
        method: "POST",
        body: JSON.stringify(body),
      })
      // Seed the job cache immediately so useJob picks it up
      qc.setQueryData(["jobs", initial.job_id], initial)
      return initial
    },
    onSuccess: (_job, { pageId }) => {
      // The caller should also watch useJob(job.job_id) for completion
      void qc.invalidateQueries({ queryKey: ["pages", "detail", pageId] })
      void qc.invalidateQueries({ queryKey: ["versions", pageId] })
    },
  })
}

// ── Export ────────────────────────────────────────────────────────────────────

export async function exportBookPdf(bookId: string): Promise<Blob> {
  const res = await fetch(`/api/export/book/${bookId}/pdf`, { method: "POST" })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  return res.blob()
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ["dashboard", "stats"],
    queryFn: () => apiFetch<DashboardStats>("/dashboard/stats"),
  })
}

export function useDashboardActivity(limit = 8) {
  return useQuery<ActivityItem[]>({
    queryKey: ["dashboard", "activity", limit],
    queryFn: () => apiFetch<ActivityItem[]>(`/dashboard/activity?limit=${limit}`),
  })
}

export function useDashboardAgents() {
  return useQuery<Agent[]>({
    queryKey: ["dashboard", "agents"],
    queryFn: () => apiFetch<Agent[]>("/dashboard/agents"),
  })
}

export function usePrintReadiness() {
  return useQuery<PrintReadiness[]>({
    queryKey: ["dashboard", "print-readiness"],
    queryFn: () => apiFetch<PrintReadiness[]>("/dashboard/print-readiness"),
  })
}

// ── Settings + Providers ───────────────────────────────────────────────────────

export function useProviders() {
  return useQuery<Provider[]>({
    queryKey: ["providers"],
    queryFn: () =>
      apiFetch<ProvidersResponse>("/providers").then((r) => r.providers),
  })
}

export function useTextProviders() {
  return useQuery<Provider[]>({
    queryKey: ["text-providers"],
    queryFn: () =>
      apiFetch<ProvidersResponse>("/text-providers").then((r) => r.providers),
  })
}

export function useSettings() {
  return useQuery<Settings>({
    queryKey: ["settings"],
    queryFn: () => apiFetch<Settings>("/settings"),
  })
}

export function useUpdateSettings() {
  const qc = useQueryClient()
  return useMutation<Settings, Error, Partial<Settings>>({
    mutationFn: (data) =>
      apiFetch<Settings>("/settings", { method: "PUT", body: JSON.stringify(data) }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["settings"] })
    },
  })
}

// ── AI Actions ────────────────────────────────────────────────────────────────

export interface RefinedConcept {
  refined_concept: string
}

export function useRefineConcept(pageId: string) {
  return useMutation<RefinedConcept, Error, void>({
    mutationFn: () =>
      apiFetch<RefinedConcept>(`/pages/${pageId}/refine-concept`, { method: "POST", body: JSON.stringify({}) }),
  })
}

export interface WrittenPrompt {
  positive: string
  negative: string
}

export function useWritePrompt(pageId: string) {
  return useMutation<WrittenPrompt, Error, void>({
    mutationFn: () =>
      apiFetch<WrittenPrompt>(`/pages/${pageId}/write-prompt`, { method: "POST", body: JSON.stringify({}) }),
  })
}

// ── Inspiration ──────────────────────────────────────────────────────────────

export interface InspirationImage {
  id: string
  book_id: string | null
  image_url: string | null
  caption: string | null
  created_at: string
}

export function useInspiration(scope: string) {
  // scope: "all" | "global" | <bookId>
  return useQuery<InspirationImage[]>({
    queryKey: ["inspiration", scope],
    queryFn: () => apiFetch<InspirationImage[]>(`/inspiration?book_id=${encodeURIComponent(scope)}`),
    enabled: !!scope,
  })
}

/**
 * Images eligible as a page's generation reference for a given book: this
 * book's inspiration images plus global ones, deduplicated by id (ce-review
 * #10 — this merge was previously reimplemented inconsistently in two places).
 */
export function useEligibleReferenceImages(bookId: string): InspirationImage[] {
  const bookImages = useInspiration(bookId)
  const globalImages = useInspiration("global")
  const seen = new Set<string>()
  return [...(bookImages.data ?? []), ...(globalImages.data ?? [])].filter((img) => {
    if (seen.has(img.id)) return false
    seen.add(img.id)
    return true
  })
}

export function useUploadInspiration() {
  const qc = useQueryClient()
  return useMutation<InspirationImage[], Error, { files: File[]; bookId?: string | null; caption?: string }>({
    mutationFn: async ({ files, bookId, caption }) => {
      // Multipart: build FormData and let the browser set the boundary — do NOT
      // route through apiFetch (it forces Content-Type: application/json).
      const fd = new FormData()
      files.forEach((f) => fd.append("files", f))
      if (bookId) fd.append("book_id", bookId)
      if (caption) fd.append("caption", caption)
      const res = await fetch(`/api/inspiration`, { method: "POST", body: fd })
      if (!res.ok) throw new Error(`API ${res.status}: ${await res.text().catch(() => res.statusText)}`)
      return res.json() as Promise<InspirationImage[]>
    },
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["inspiration"] }) },
  })
}

export function useUpdateInspiration() {
  const qc = useQueryClient()
  return useMutation<InspirationImage, Error, { id: string; caption?: string; book_id?: string | null }>({
    mutationFn: ({ id, ...data }) =>
      apiFetch<InspirationImage>(`/inspiration/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["inspiration"] }) },
  })
}

export function useDeleteInspiration() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: (id) => apiFetch<void>(`/inspiration/${id}`, { method: "DELETE" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["inspiration"] }) },
  })
}
