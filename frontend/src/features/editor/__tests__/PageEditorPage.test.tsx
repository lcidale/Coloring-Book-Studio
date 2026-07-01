/**
 * PageEditorPage.test.tsx — unit tests for the AI action buttons.
 *
 * Mocks @/lib/api to control hooks, and mocks sonner to assert toast calls.
 * Mirrors the setup patterns in frontend/src/lib/__tests__/api.test.tsx.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import { PageEditorPage } from '../PageEditorPage'
import type { Page, Book } from '@/lib/api'

// ── Mocks ──────────────────────────────────────────────────────────────────────

// Mock the entire API module — we control every hook return value below.
vi.mock('@/lib/api', () => ({
  usePage: vi.fn(),
  useBook: vi.fn(),
  useUpdatePage: vi.fn(),
  useGeneratePage: vi.fn(),
  useJob: vi.fn(),
  useRefineConcept: vi.fn(),
  useWritePrompt: vi.fn(),
  useCreateTextLayer: vi.fn(),
  useDeleteTextLayer: vi.fn(),
  useVersions: vi.fn(),
  useRestoreVersion: vi.fn(),
  useUpdateVersion: vi.fn(),
  useDeleteVersion: vi.fn(),
  exportBookPdf: vi.fn(),
  pageImageSrc: (p: string) => `/storage/${p}`,
}))

// Mock sonner so we can assert toast.error calls without a real DOM toast system.
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

import * as api from '@/lib/api'
import { toast } from 'sonner'

// ── Fixtures ───────────────────────────────────────────────────────────────────

const PAGE: Page = {
  id: 'page-1',
  book_id: 'book-1',
  sort_order: 1,
  title: null,
  concept: 'A bear fishing in a river',
  status: 'idea',
  prompt: null,
  negative_prompt: null,
  image_path: null,
  image_dpi: null,
  image_width_px: null,
  image_height_px: null,
  is_pure_bw: null,
  print_check_notes: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  text_layers: [],
}

const BOOK: Book = {
  id: 'book-1',
  title: 'Animals',
  emoji: '🐻',
  theme: 'animals',
  audience: 'kids',
  positioning: 'fun',
  target_page_count: 24,
  page_count: 5,
  approved_count: 2,
  progress_pct: 40,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
  style_guide: null,
}

// ── Helpers ────────────────────────────────────────────────────────────────────

// Returns a partial react-query mutation mock. Typed as `any` so call sites can
// pass it to any of the typed useX mutation hooks without restating the full
// UseMutationResult shape (this is a test double, not production code).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function makeMutation<TData = unknown>(overrides: Partial<{
  mutateAsync: () => Promise<TData>
  isPending: boolean
}> = {}): any {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
    isSuccess: false,
    isError: false,
    reset: vi.fn(),
    ...overrides,
  }
}

function setupDefaultMocks() {
  vi.mocked(api.usePage).mockReturnValue({
    data: PAGE,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof api.usePage>)

  vi.mocked(api.useBook).mockReturnValue({
    data: BOOK,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof api.useBook>)

  vi.mocked(api.useUpdatePage).mockReturnValue(
    makeMutation<Page>({ mutateAsync: vi.fn().mockResolvedValue(PAGE) })
  )

  vi.mocked(api.useGeneratePage).mockReturnValue(
    makeMutation() as ReturnType<typeof api.useGeneratePage>
  )

  vi.mocked(api.useJob).mockReturnValue({
    data: undefined,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof api.useJob>)

  vi.mocked(api.useRefineConcept).mockReturnValue(
    makeMutation({ mutateAsync: vi.fn().mockResolvedValue({ refined_concept: 'A majestic bear fishing in a mountain stream, surrounded by pine trees' }) })
  )

  vi.mocked(api.useWritePrompt).mockReturnValue(
    makeMutation({ mutateAsync: vi.fn().mockResolvedValue({ positive: 'a bear catching fish, coloring book style', negative: 'color, shading, realistic' }) })
  )

  vi.mocked(api.useCreateTextLayer).mockReturnValue(
    makeMutation() as ReturnType<typeof api.useCreateTextLayer>
  )

  vi.mocked(api.useDeleteTextLayer).mockReturnValue(
    makeMutation() as ReturnType<typeof api.useDeleteTextLayer>
  )

  vi.mocked(api.useVersions).mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
  } as ReturnType<typeof api.useVersions>)

  vi.mocked(api.useRestoreVersion).mockReturnValue(
    makeMutation() as ReturnType<typeof api.useRestoreVersion>
  )

  vi.mocked(api.useUpdateVersion).mockReturnValue(
    makeMutation() as ReturnType<typeof api.useUpdateVersion>
  )

  vi.mocked(api.useDeleteVersion).mockReturnValue(
    makeMutation() as ReturnType<typeof api.useDeleteVersion>
  )
}

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/editor/page-1']}>
        <Routes>
          <Route path="/editor/:pageId" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

function renderPage() {
  const Wrapper = createWrapper()
  return render(
    <Wrapper>
      <PageEditorPage />
    </Wrapper>
  )
}

// ── Setup ──────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  setupDefaultMocks()
})

// ── Refine with AI — Concept ───────────────────────────────────────────────────

describe('Refine with AI (Concept)', () => {
  it('calls useRefineConcept mutation and renders the proposed concept in a review box', async () => {
    const user = userEvent.setup()
    renderPage()

    const refineBtn = screen.getByRole('button', { name: /refine concept with ai/i })
    await user.click(refineBtn)

    // The review box should appear with the proposed text
    await waitFor(() => {
      expect(screen.getByText('A majestic bear fishing in a mountain stream, surrounded by pine trees')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: /accept ai concept proposal/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /discard ai concept proposal/i })).toBeInTheDocument()
  })

  it('Accept saves the proposal via useUpdatePage and closes the review box', async () => {
    const user = userEvent.setup()
    const updatePageMutateAsync = vi.fn().mockResolvedValue(PAGE)
    vi.mocked(api.useUpdatePage).mockReturnValue(
      makeMutation<Page>({ mutateAsync: updatePageMutateAsync })
    )

    renderPage()

    // Click "Refine with AI" to show the proposal
    await user.click(screen.getByRole('button', { name: /refine concept with ai/i }))
    await waitFor(() => {
      expect(screen.getByText('A majestic bear fishing in a mountain stream, surrounded by pine trees')).toBeInTheDocument()
    })

    // Click Accept
    await user.click(screen.getByRole('button', { name: /accept ai concept proposal/i }))

    await waitFor(() => {
      expect(updatePageMutateAsync).toHaveBeenCalledWith({
        id: 'page-1',
        concept: 'A majestic bear fishing in a mountain stream, surrounded by pine trees',
      })
    })

    // Review box should be gone
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /accept ai concept proposal/i })).not.toBeInTheDocument()
    })
  })

  it('Discard closes the review box without calling useUpdatePage', async () => {
    const user = userEvent.setup()
    const updatePageMutateAsync = vi.fn().mockResolvedValue(PAGE)
    vi.mocked(api.useUpdatePage).mockReturnValue(
      makeMutation<Page>({ mutateAsync: updatePageMutateAsync })
    )

    renderPage()

    await user.click(screen.getByRole('button', { name: /refine concept with ai/i }))
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /discard ai concept proposal/i })).toBeInTheDocument()
    })

    await user.click(screen.getByRole('button', { name: /discard ai concept proposal/i }))

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /discard ai concept proposal/i })).not.toBeInTheDocument()
    })

    // updatePage should not have been called during discard
    expect(updatePageMutateAsync).not.toHaveBeenCalled()

    // Original concept text should still be visible
    expect(screen.getByText('A bear fishing in a river')).toBeInTheDocument()
  })

  it('shows an error toast when useRefineConcept fails', async () => {
    const user = userEvent.setup()
    const error = new Error('Provider not configured: ANTHROPIC_API_KEY missing')
    vi.mocked(api.useRefineConcept).mockReturnValue(
      makeMutation({ mutateAsync: vi.fn().mockRejectedValue(error) })
    )

    renderPage()

    await user.click(screen.getByRole('button', { name: /refine concept with ai/i }))

    await waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalledWith(String(error))
    })

    // Review box must NOT appear on error
    expect(screen.queryByRole('button', { name: /accept ai concept proposal/i })).not.toBeInTheDocument()
  })
})

// ── Write with AI — Prompt ─────────────────────────────────────────────────────

describe('Write with AI (Prompt)', () => {
  it('calls useWritePrompt mutation and opens the prompt editor pre-filled with the positive prompt', async () => {
    const user = userEvent.setup()
    renderPage()

    const writeBtn = screen.getByRole('button', { name: /write prompt with ai/i })
    await user.click(writeBtn)

    // The prompt editor (textarea) should appear, pre-filled with the positive prompt.
    // Scope by the pre-filled value — the page has other textboxes (Text Layers input).
    await waitFor(() => {
      expect(
        screen.getByDisplayValue('a bear catching fish, coloring book style'),
      ).toBeInTheDocument()
    })

    // Save and Cancel buttons for the prompt editor should be visible
    expect(screen.getByRole('button', { name: /^Save$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Cancel$/i })).toBeInTheDocument()
  })

  it('shows an error toast when useWritePrompt fails', async () => {
    const user = userEvent.setup()
    const error = new Error('API 400: Gemini key not set')
    vi.mocked(api.useWritePrompt).mockReturnValue(
      makeMutation({ mutateAsync: vi.fn().mockRejectedValue(error) })
    )

    renderPage()

    await user.click(screen.getByRole('button', { name: /write prompt with ai/i }))

    await waitFor(() => {
      expect(vi.mocked(toast.error)).toHaveBeenCalledWith(String(error))
    })

    // Prompt editor should NOT open on error — the positive prompt is never pre-filled.
    // (The page always has other textboxes, e.g. the Text Layers input, so scope by value.)
    expect(
      screen.queryByDisplayValue('a bear catching fish, coloring book style'),
    ).not.toBeInTheDocument()
  })
})
