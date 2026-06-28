/**
 * SettingsPage.test.tsx — unit tests for the Admin page (SettingsPage).
 *
 * Hooks are mocked via vi.mock("@/lib/api") so no network calls occur.
 * Uses React Testing Library + vitest.
 */
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { type ReactNode } from "react"
import { SettingsPage } from "../SettingsPage"

// ── Mock @/lib/api ─────────────────────────────────────────────────────────────

const mockMutateAsync = vi.fn()

vi.mock("@/lib/api", () => ({
  useProviders: vi.fn(),
  useTextProviders: vi.fn(),
  useSettings: vi.fn(),
  useUpdateSettings: vi.fn(),
}))

// Import mocked module so we can control return values per test
import {
  useProviders,
  useTextProviders,
  useSettings,
  useUpdateSettings,
} from "@/lib/api"

// ── Mock sonner toast so we don't need the real implementation ─────────────────

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

// ── Helpers ────────────────────────────────────────────────────────────────────

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
}

// ── Fixtures ───────────────────────────────────────────────────────────────────

const TEXT_PROVIDERS = [
  {
    id: "gemini",
    label: "Gemini",
    models: [
      { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
      { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
    ],
    default_model: "gemini-2.5-flash",
    configured: true,
  },
  {
    id: "claude",
    label: "Claude",
    models: [
      { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6 (recommended)" },
      { id: "claude-opus-4-8", label: "Claude Opus 4.8" },
    ],
    default_model: "claude-sonnet-4-6",
    configured: false, // ANTHROPIC_API_KEY absent in this scenario
  },
]

const IMAGE_PROVIDERS = [
  {
    id: "fal",
    label: "fal.ai",
    models: [
      { id: "fal-ai/flux/schnell", label: "FLUX Schnell" },
      { id: "fal-ai/flux/dev", label: "FLUX Dev" },
    ],
    default_model: "fal-ai/flux/schnell",
    configured: true,
  },
]

const SETTINGS = {
  image_provider: "fal",
  image_model: "fal-ai/flux/schnell",
  concept_provider: "gemini",
  concept_model: "gemini-2.5-flash",
  prompt_provider: "gemini",
  prompt_model: "gemini-2.5-flash",
  image_configured: true,
  concept_configured: true,
  prompt_configured: true,
}

// ── Setup ──────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  mockMutateAsync.mockResolvedValue(SETTINGS)

  vi.mocked(useTextProviders).mockReturnValue({
    data: TEXT_PROVIDERS,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useTextProviders>)

  vi.mocked(useProviders).mockReturnValue({
    data: IMAGE_PROVIDERS,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useProviders>)

  vi.mocked(useSettings).mockReturnValue({
    data: SETTINGS,
    isLoading: false,
    isError: false,
  } as ReturnType<typeof useSettings>)

  vi.mocked(useUpdateSettings).mockReturnValue({
    mutateAsync: mockMutateAsync,
    isPending: false,
  } as unknown as ReturnType<typeof useUpdateSettings>)
})

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("SettingsPage (Admin)", () => {
  // ── Page heading ─────────────────────────────────────────────────────────────

  it('renders the "Admin" page heading', () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    expect(screen.getByRole("heading", { name: /admin/i, level: 1 })).toBeInTheDocument()
  })

  // ── Three section headings ────────────────────────────────────────────────────

  it('renders the "Concept Model" section heading', () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    expect(screen.getByRole("heading", { name: /concept model/i })).toBeInTheDocument()
  })

  it('renders the "Prompt Model" section heading', () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    expect(screen.getByRole("heading", { name: /prompt model/i })).toBeInTheDocument()
  })

  it('renders the "Image Generation" section heading', () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    expect(screen.getByRole("heading", { name: /image generation/i })).toBeInTheDocument()
  })

  // ── Provider radios ───────────────────────────────────────────────────────────

  it("renders text provider radio options in the Concept Model section", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    // Gemini appears twice (Concept + Prompt), Claude appears twice
    const geminiRadios = screen.getAllByRole("radio", { name: /gemini/i })
    expect(geminiRadios.length).toBeGreaterThanOrEqual(2)
    const claudeRadios = screen.getAllByRole("radio", { name: /claude/i })
    expect(claudeRadios.length).toBeGreaterThanOrEqual(2)
  })

  it("renders image provider radio options in the Image Generation section", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    const falRadios = screen.getAllByRole("radio", { name: /fal/i })
    expect(falRadios.length).toBeGreaterThanOrEqual(1)
  })

  // ── Model selects ─────────────────────────────────────────────────────────────

  it("renders a model select in each section", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    // Each section with a selected provider shows a model select
    const selects = screen.getAllByRole("combobox")
    // Three sections, each with a provider selected → three selects
    expect(selects.length).toBeGreaterThanOrEqual(3)
  })

  it("shows text model options in the Concept Model select", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    // Gemini 2.5 Flash appears at least once
    const flashOptions = screen.getAllByRole("option", { name: /gemini 2\.5 flash/i })
    expect(flashOptions.length).toBeGreaterThanOrEqual(1)
  })

  // ── Not-Configured badge ──────────────────────────────────────────────────────

  it('shows "Not Configured" badge for Claude when ANTHROPIC_API_KEY is absent', () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    // Claude providers are not configured in TEXT_PROVIDERS fixture
    const notConfiguredBadges = screen.getAllByText(/not configured/i)
    // Should appear at least twice — once in Concept, once in Prompt
    expect(notConfiguredBadges.length).toBeGreaterThanOrEqual(2)
  })

  it('shows "Configured" badge for Gemini when configured is true', () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    const configuredBadges = screen.getAllByText(/^configured$/i)
    expect(configuredBadges.length).toBeGreaterThanOrEqual(1)
  })

  // ── Dirty-state Save buttons ──────────────────────────────────────────────────

  it("Save buttons are disabled initially (not dirty)", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    const saveButtons = screen.getAllByRole("button", { name: /save/i })
    // All three Save buttons should start disabled (not dirty)
    saveButtons.forEach((btn) => {
      expect(btn).toBeDisabled()
    })
  })

  it("Save button becomes enabled after changing a provider", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })

    // Find the first Claude radio (Concept section) and click it
    const claudeRadios = screen.getAllByRole("radio", { name: /claude/i })
    fireEvent.click(claudeRadios[0])

    // The first Save button should now be enabled
    const saveButtons = screen.getAllByRole("button", { name: /save/i })
    expect(saveButtons[0]).not.toBeDisabled()
  })

  // ── Section-scoped saves ──────────────────────────────────────────────────────

  it("saving the Concept section calls useUpdateSettings with concept fields only", async () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })

    // Change concept provider to Claude
    const claudeRadios = screen.getAllByRole("radio", { name: /claude/i })
    fireEvent.click(claudeRadios[0]) // first occurrence = Concept section

    // Click the first Save button (Concept section)
    const saveButtons = screen.getAllByRole("button", { name: /save/i })
    fireEvent.click(saveButtons[0])

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1))

    const calledWith = mockMutateAsync.mock.calls[0][0]
    // Must contain concept fields
    expect(calledWith).toHaveProperty("concept_provider")
    expect(calledWith).toHaveProperty("concept_model")
    // Must NOT contain image or prompt fields
    expect(calledWith).not.toHaveProperty("image_provider")
    expect(calledWith).not.toHaveProperty("prompt_provider")
  })

  it("saving the Prompt section calls useUpdateSettings with prompt fields only", async () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })

    // Change prompt provider — second occurrence of Claude radio
    const claudeRadios = screen.getAllByRole("radio", { name: /claude/i })
    fireEvent.click(claudeRadios[1]) // second occurrence = Prompt section

    // Click the second Save button (Prompt section)
    const saveButtons = screen.getAllByRole("button", { name: /save/i })
    fireEvent.click(saveButtons[1])

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1))

    const calledWith = mockMutateAsync.mock.calls[0][0]
    expect(calledWith).toHaveProperty("prompt_provider")
    expect(calledWith).toHaveProperty("prompt_model")
    expect(calledWith).not.toHaveProperty("image_provider")
    expect(calledWith).not.toHaveProperty("concept_provider")
  })

  it("saving the Image Generation section calls useUpdateSettings with image fields only", async () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })

    // Change image model to trigger dirty state
    const selects = screen.getAllByRole("combobox")
    // The image section select is the third one
    const imageSelect = selects[2]
    fireEvent.change(imageSelect, { target: { value: "fal-ai/flux/dev" } })

    // Click the third Save button
    const saveButtons = screen.getAllByRole("button", { name: /save/i })
    fireEvent.click(saveButtons[2])

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1))

    const calledWith = mockMutateAsync.mock.calls[0][0]
    expect(calledWith).toHaveProperty("image_provider")
    expect(calledWith).toHaveProperty("image_model")
    expect(calledWith).not.toHaveProperty("concept_provider")
    expect(calledWith).not.toHaveProperty("prompt_provider")
  })

  // ── Loading state ─────────────────────────────────────────────────────────────

  it("shows skeleton loaders when providers are loading", () => {
    vi.mocked(useTextProviders).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useTextProviders>)

    vi.mocked(useSettings).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useSettings>)

    const wrapper = createWrapper()
    const { container } = render(<SettingsPage />, { wrapper })

    // Skeleton divs use animate-pulse class
    const skeletons = container.querySelectorAll(".animate-pulse")
    expect(skeletons.length).toBeGreaterThan(0)
  })

  // ── Error state ───────────────────────────────────────────────────────────────

  it("shows error message when providers fail to load", () => {
    vi.mocked(useTextProviders).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useTextProviders>)

    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })

    const errorMessages = screen.getAllByText(/failed to load providers/i)
    expect(errorMessages.length).toBeGreaterThanOrEqual(1)
  })

  // ── API Keys section ──────────────────────────────────────────────────────────

  it("lists ANTHROPIC_API_KEY in the API Keys section", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    expect(screen.getByText("ANTHROPIC_API_KEY")).toBeInTheDocument()
  })

  it("lists GEMINI_API_KEY in the API Keys section", () => {
    const wrapper = createWrapper()
    render(<SettingsPage />, { wrapper })
    expect(screen.getByText("GEMINI_API_KEY")).toBeInTheDocument()
  })
})
