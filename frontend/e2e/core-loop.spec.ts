/**
 * core-loop.spec.ts — E2E spec for the main Coloring Book Studio workflow.
 *
 * All /api routes are intercepted at the network layer so no live backend
 * is required. This lets the spec run in CI without any backend service.
 *
 * Covered flow:
 *   1. Navigate to /books and open "New Book" dialog
 *   2. Fill form → submit → land on BookDetailPage
 *   3. Open "Add Page" dialog → create a page → land on PageEditorPage
 *   4. Assert "Generate" button is visible and click it
 *      - Because no API key exists in CI, we intercept the generate call
 *        and assert the request was made (enqueue step only)
 *   5. Back on BookDetailPage, intercept an "approve" action (status PATCH)
 *   6. Trigger Export PDF → assert the download fetch was fired
 */
import { test, expect, type Page, type Route } from '@playwright/test'

// ── Fixtures ───────────────────────────────────────────────────────────────────

const BOOK = {
  id: 'book-e2e-1',
  title: 'E2E Test Animals',
  emoji: '🐻',
  theme: 'animals',
  audience: 'kids',
  positioning: 'fun',
  target_page_count: 24,
  page_count: 1,
  approved_count: 0,
  progress_pct: 4,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
  style_guide: null,
}

const PAGE = {
  id: 'page-e2e-1',
  book_id: 'book-e2e-1',
  sort_order: 1,
  concept: 'A bear fishing in a stream',
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

const PAGE_APPROVED = { ...PAGE, status: 'approved' }

const JOB_QUEUED = {
  job_id: 'job-e2e-1',
  page_id: 'page-e2e-1',
  status: 'queued',
  error: null,
  result_version: null,
  created_at: '2024-01-01T00:00:00Z',
  started_at: null,
  finished_at: null,
}

const JOB_DONE = { ...JOB_QUEUED, status: 'done', result_version: 1 }

// ── Helpers ────────────────────────────────────────────────────────────────────

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  })
}

/**
 * Wire up all baseline API intercepts so the app loads without real backend.
 * Individual tests can override specific routes after calling this.
 */
async function wireBaseApiMocks(page: Page) {
  // Books list — initially empty, then returns our book after creation
  await page.route('**/api/books', async (route) => {
    if (route.request().method() === 'GET') {
      return json(route, [BOOK])
    }
    if (route.request().method() === 'POST') {
      return json(route, BOOK, 201)
    }
    return route.continue()
  })

  // Single book
  await page.route('**/api/books/book-e2e-1', async (route) => {
    return json(route, BOOK)
  })

  // Book status summary
  await page.route('**/api/books/book-e2e-1/status-summary', async (route) => {
    return json(route, {
      idea: 1, prompt: 0, generated: 0, review: 0,
      revision: 0, approved: 0, print_ready: 0, exported: 0,
    })
  })

  // Pages list for the book
  await page.route('**/api/pages/book/book-e2e-1', async (route) => {
    if (route.request().method() === 'GET') {
      return json(route, [PAGE])
    }
    if (route.request().method() === 'POST') {
      return json(route, PAGE, 201)
    }
    return route.continue()
  })

  // Single page
  await page.route('**/api/pages/page-e2e-1', async (route) => {
    if (route.request().method() === 'GET') {
      return json(route, PAGE)
    }
    if (route.request().method() === 'PATCH') {
      return json(route, PAGE_APPROVED)
    }
    return route.continue()
  })

  // Generate
  await page.route('**/api/pages/page-e2e-1/generate', async (route) => {
    return json(route, JOB_QUEUED, 202)
  })

  // Job poll
  await page.route('**/api/jobs/job-e2e-1', async (route) => {
    return json(route, JOB_DONE)
  })

  // Export PDF — return a minimal PDF blob
  await page.route('**/api/export/book/book-e2e-1/pdf', async (route) => {
    return route.fulfill({
      status: 200,
      contentType: 'application/pdf',
      body: Buffer.from('%PDF-1.4 mock'),
    })
  })

  // Dashboard
  await page.route('**/api/dashboard/**', async (route) => {
    const url = route.request().url()
    if (url.includes('/stats')) return json(route, { active_books: 1, pages_this_week: 0, print_ready_pages: 0 })
    if (url.includes('/activity')) return json(route, [])
    if (url.includes('/agents')) return json(route, [])
    if (url.includes('/print-readiness')) return json(route, [])
    return json(route, {})
  })

  // Providers / Settings
  await page.route('**/api/providers', async (route) => {
    return json(route, { providers: [] })
  })
  await page.route('**/api/settings', async (route) => {
    return json(route, { image_provider: '', image_model: '' })
  })
}

// ── Tests ──────────────────────────────────────────────────────────────────────

test.describe('Core loop: create book → add page → generate → approve → export', () => {
  test.beforeEach(async ({ page }) => {
    await wireBaseApiMocks(page)
  })

  test('1. Books page loads and shows New Book button', async ({ page }) => {
    await page.goto('/books')
    await expect(page.getByRole('button', { name: /new book/i })).toBeVisible()
    // The mocked book list should render the book title
    await expect(page.getByText('E2E Test Animals')).toBeVisible()
  })

  test('2. New Book dialog — fill and submit', async ({ page }) => {
    // Override books list to start empty so we see the "No books yet" state first
    await page.route('**/api/books', async (route) => {
      if (route.request().method() === 'GET') return json(route, [])
      if (route.request().method() === 'POST') return json(route, BOOK, 201)
      return route.continue()
    })

    await page.goto('/books')

    // Empty state CTA
    await expect(page.getByText('No books yet')).toBeVisible()
    await page.getByRole('button', { name: /new book/i }).first().click()

    // Dialog appears
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText('New Book Project')).toBeVisible()

    // Fill the title (required field)
    await page.getByPlaceholder(/peaceful gardens/i).fill('E2E Test Animals')

    // After submitting, we navigate to /books/book-e2e-1
    // Intercept subsequent book fetch to return full book
    const createBookBtn = page.getByRole('button', { name: /create book/i })
    await expect(createBookBtn).toBeEnabled()
    await createBookBtn.click()

    // Should navigate to book detail page
    await expect(page).toHaveURL(/\/books\/book-e2e-1/)
    await expect(page.getByText('E2E Test Animals')).toBeVisible()
  })

  test('3. Book detail page — Add Page dialog', async ({ page }) => {
    await page.goto('/books/book-e2e-1')

    // Detail page loaded
    await expect(page.getByText('E2E Test Animals')).toBeVisible()
    await expect(page.getByRole('button', { name: /add page/i })).toBeVisible()

    // Open add page dialog
    await page.getByRole('button', { name: /add page/i }).click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText('Add Page')).toBeVisible()

    // Fill concept
    await page.getByPlaceholder(/mandala/i).fill('A bear fishing in a stream')

    // Submit — should navigate to editor
    await page.getByRole('button', { name: /add page/i, exact: false }).last().click()

    // Navigates to editor
    await expect(page).toHaveURL(/\/editor\/page-e2e-1/)
  })

  test('4. Page editor — Generate button is visible and fires generate request', async ({ page }) => {
    const generateRequests: string[] = []

    // Capture generate calls
    await page.route('**/api/pages/page-e2e-1/generate', async (route) => {
      generateRequests.push(route.request().url())
      return json(route, JOB_QUEUED, 202)
    })

    await page.goto('/editor/page-e2e-1')

    // Page concept should appear
    await expect(page.getByText('A bear fishing in a stream')).toBeVisible()

    // Generate button must be present
    const generateBtn = page.getByRole('button', { name: /generate/i })
    await expect(generateBtn).toBeVisible()

    // Click it — backend returns 202 queued (no API key needed for test)
    await generateBtn.click()

    // Verify the fetch was fired
    await expect.poll(() => generateRequests.length).toBeGreaterThan(0)
  })

  test('5. Page editor — Approve action sends PATCH status=approved', async ({ page }) => {
    const patchBodies: string[] = []

    // Intercept page PATCH
    await page.route('**/api/pages/page-e2e-1', async (route) => {
      if (route.request().method() === 'PATCH') {
        patchBodies.push(await route.request().postData() ?? '')
        return json(route, PAGE_APPROVED)
      }
      return json(route, PAGE)
    })

    await page.goto('/editor/page-e2e-1')

    // Find the Approve button
    const approveBtn = page.getByRole('button', { name: /approve/i })
    await expect(approveBtn).toBeVisible()
    await approveBtn.click()

    // Verify PATCH was fired with approved status
    await expect.poll(() => patchBodies.length).toBeGreaterThan(0)
    const body = JSON.parse(patchBodies[0]!) as Record<string, unknown>
    expect(body.status).toBe('approved')
  })

  test('6. Book detail page — Export PDF triggers the export endpoint', async ({ page }) => {
    const exportCalls: string[] = []

    await page.route('**/api/export/book/book-e2e-1/pdf', async (route) => {
      exportCalls.push(route.request().url())
      return route.fulfill({
        status: 200,
        contentType: 'application/pdf',
        body: Buffer.from('%PDF-1.4 mock'),
      })
    })

    await page.goto('/books/book-e2e-1')
    await expect(page.getByText('E2E Test Animals')).toBeVisible()

    // Click Export PDF button in the top bar
    const exportBtn = page.getByRole('button', { name: /export pdf/i })
    await expect(exportBtn).toBeVisible()

    // Intercept the browser download (createObjectURL) so it doesn't open a file
    await page.evaluate(() => {
      window.URL.createObjectURL = () => 'blob:mock'
      window.URL.revokeObjectURL = () => undefined
    })

    await exportBtn.click()

    // Verify the export API call was made
    await expect.poll(() => exportCalls.length).toBeGreaterThan(0)
  })
})
