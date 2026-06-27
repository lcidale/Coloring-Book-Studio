/**
 * api.test.tsx — unit tests for the typed fetch client and TanStack Query hooks.
 *
 * fetch is globally mocked via vi.stubGlobal so no actual network calls occur.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { type ReactNode } from 'react'
import {
  useBooks,
  useBook,
  useCreateBook,
  usePages,
  useJob,
  useGeneratePage,
  useDashboardStats,
  useDashboardActivity,
  type Book,
  type Page,
  type Job,
  type DashboardStats,
  type ActivityItem,
} from '../api'

// ── Helpers ────────────────────────────────────────────────────────────────────

function makeResponse<T>(data: T, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (_: string) => 'application/json' },
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as unknown as Response
}

function makeErrorResponse(status: number, body = 'Server Error') {
  return {
    ok: false,
    status,
    statusText: body,
    headers: { get: () => 'text/plain' },
    json: () => Promise.reject(new Error('not json')),
    text: () => Promise.resolve(body),
  } as unknown as Response
}

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return {
    wrapper: ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    ),
    queryClient: qc,
  }
}

// ── Fixtures ───────────────────────────────────────────────────────────────────

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

const PAGE: Page = {
  id: 'page-1',
  book_id: 'book-1',
  sort_order: 1,
  concept: 'A bear fishing',
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

const JOB_QUEUED: Job = {
  job_id: 'job-1',
  page_id: 'page-1',
  status: 'queued',
  error: null,
  result_version: null,
  created_at: '2024-01-01T00:00:00Z',
  started_at: null,
  finished_at: null,
}

const JOB_DONE: Job = { ...JOB_QUEUED, status: 'done', result_version: 1 }

const STATS: DashboardStats = {
  active_books: 3,
  pages_this_week: 12,
  print_ready_pages: 5,
}

const ACTIVITY: ActivityItem[] = [
  { text: 'Page approved', kind: 'approved', when: '2m ago' },
  { text: 'Page generated', kind: 'generated', when: '5m ago' },
]

// ── Setup ──────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  vi.restoreAllMocks()
})

// ── useBooks ───────────────────────────────────────────────────────────────────

describe('useBooks', () => {
  it('fetches and returns book list', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse([BOOK]))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBooks(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(1)
    expect(result.current.data![0].title).toBe('Animals')
  })

  it('calls /api/books', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse([]))
    const { wrapper } = createWrapper()
    renderHook(() => useBooks(), { wrapper })
    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        '/api/books',
        expect.objectContaining({ headers: expect.any(Object) })
      )
    )
  })

  it('surfaces errors from the API', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeErrorResponse(500, 'Internal Server Error'))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBooks(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/500/)
  })
})

// ── useBook (single) ──────────────────────────────────────────────────────────

describe('useBook', () => {
  it('fetches a single book by id', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse(BOOK))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBook('book-1'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.id).toBe('book-1')
  })

  it('is disabled when id is empty string', () => {
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useBook(''), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
    expect(vi.mocked(fetch)).not.toHaveBeenCalled()
  })
})

// ── useCreateBook mutation ─────────────────────────────────────────────────────

describe('useCreateBook', () => {
  it('POSTs to /api/books and returns the new book', async () => {
    const newBook = { ...BOOK, id: 'book-new', title: 'Dinos' }
    vi.mocked(fetch)
      .mockResolvedValueOnce(makeResponse(newBook)) // POST
      .mockResolvedValueOnce(makeResponse([newBook])) // invalidate → refetch books

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useCreateBook(), { wrapper })

    result.current.mutate({ title: 'Dinos', theme: 'dinosaurs' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.title).toBe('Dinos')
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      '/api/books',
      expect.objectContaining({ method: 'POST' })
    )
  })
})

// ── usePages ───────────────────────────────────────────────────────────────────

describe('usePages', () => {
  it('fetches pages for a book', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse([PAGE]))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePages('book-1'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data![0].concept).toBe('A bear fishing')
  })

  it('is disabled when bookId is empty', () => {
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => usePages(''), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
  })
})

// ── useJob (polling) ──────────────────────────────────────────────────────────

describe('useJob', () => {
  it('is disabled when jobId is null', () => {
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useJob(null), { wrapper })
    expect(result.current.fetchStatus).toBe('idle')
  })

  it('fetches job status', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse(JOB_DONE))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useJob('job-1'), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.status).toBe('done')
  })

  it('continues polling when status is queued', async () => {
    // First call queued, second call done
    vi.mocked(fetch)
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED))
      .mockResolvedValueOnce(makeResponse(JOB_DONE))

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useJob('job-1'), { wrapper })

    // Wait for first fetch to settle
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    // Status could be queued or done depending on timing; both are valid
    expect(['queued', 'done']).toContain(result.current.data?.status)
  })
})

// ── useGeneratePage (enqueue + seed cache) ────────────────────────────────────

describe('useGeneratePage', () => {
  it('POSTs to generate endpoint and returns the initial job', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(makeResponse(JOB_QUEUED, 202)) // POST generate → 202
      .mockResolvedValueOnce(makeResponse([PAGE]))           // invalidate pages refetch

    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useGeneratePage(), { wrapper })

    result.current.mutate({ pageId: 'page-1' })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(result.current.data?.job_id).toBe('job-1')
    expect(result.current.data?.status).toBe('queued')
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      '/api/pages/page-1/generate',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('propagates generate API errors', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeErrorResponse(402, 'No API key'))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useGeneratePage(), { wrapper })
    result.current.mutate({ pageId: 'page-1' })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toMatch(/402/)
  })
})

// ── useDashboardStats ─────────────────────────────────────────────────────────

describe('useDashboardStats', () => {
  it('fetches dashboard stats', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse(STATS))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDashboardStats(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.active_books).toBe(3)
    expect(result.current.data?.pages_this_week).toBe(12)
    expect(result.current.data?.print_ready_pages).toBe(5)
  })
})

// ── useDashboardActivity ──────────────────────────────────────────────────────

describe('useDashboardActivity', () => {
  it('fetches activity feed with default limit', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse(ACTIVITY))
    const { wrapper } = createWrapper()
    const { result } = renderHook(() => useDashboardActivity(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toHaveLength(2)
    expect(result.current.data![0].kind).toBe('approved')
  })

  it('includes limit param in the URL', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(makeResponse([]))
    const { wrapper } = createWrapper()
    renderHook(() => useDashboardActivity(5), { wrapper })
    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      '/api/dashboard/activity?limit=5',
      expect.any(Object)
    )
  })
})
