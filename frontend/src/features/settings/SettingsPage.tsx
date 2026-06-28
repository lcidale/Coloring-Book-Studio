/**
 * SettingsPage — /admin route (formerly /settings).
 * Three provider+model picker sections: Concept Model, Prompt Model, Image Generation.
 * Each section is powered by a reusable ProviderModelSection component.
 * Loads GET /api/providers (image), GET /api/text-providers (text), GET /api/settings.
 * Saves via PUT /api/settings with only the affected section's fields.
 */
import * as React from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  useProviders,
  useTextProviders,
  useSettings,
  useUpdateSettings,
  type Provider,
} from "@/lib/api"

// ── Skeleton ───────────────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)] ${className}`} />
}

// ── ProviderModelSection ───────────────────────────────────────────────────────

interface ProviderModelSectionProps {
  title: string
  description: string
  providers: Provider[] | undefined
  isLoading: boolean
  isError: boolean
  /** The currently persisted provider value (from settings) */
  providerValue: string
  /** The currently persisted model value (from settings) */
  modelValue: string
  /** Whether the selected provider is configured (key present) */
  configured: boolean
  /** Whether a save mutation is in flight */
  saving: boolean
  /** Called when the user clicks Save; receives the local provider+model selection */
  onSave: (provider: string, model: string) => void
}

/**
 * ProviderModelSection — reusable radio provider list + model select + badge + Save.
 * Follows design-system §4.5 (radio-select provider pattern), §2.11 (select styling),
 * §4.3 (dirty-state Save), and §2.2 (Badge).
 */
function ProviderModelSection({
  title,
  description,
  providers,
  isLoading,
  isError,
  providerValue,
  modelValue,
  configured,
  saving,
  onSave,
}: ProviderModelSectionProps) {
  const [selectedProvider, setSelectedProvider] = React.useState<string>(providerValue)
  const [selectedModel, setSelectedModel] = React.useState<string>(modelValue)
  const [dirty, setDirty] = React.useState(false)

  // Sync local state when persisted values arrive or change (only if not dirty)
  React.useEffect(() => {
    if (!dirty) {
      setSelectedProvider(providerValue)
      setSelectedModel(modelValue)
    }
  }, [providerValue, modelValue, dirty])

  function handleProviderChange(providerId: string) {
    setSelectedProvider(providerId)
    const provider = providers?.find((p) => p.id === providerId)
    const defaultModel = provider?.default_model ?? provider?.models[0]?.id ?? ""
    setSelectedModel(defaultModel)
    setDirty(true)
  }

  function handleModelChange(model: string) {
    setSelectedModel(model)
    setDirty(true)
  }

  function handleSave() {
    onSave(selectedProvider, selectedModel)
    setDirty(false)
  }

  const currentProvider = providers?.find((p) => p.id === selectedProvider)
  const availableModels = currentProvider?.models ?? []

  // Determine badge for the selected provider's configured state
  const selectedProviderObj = providers?.find((p) => p.id === selectedProvider)
  const isSelectedConfigured = selectedProviderObj?.configured ?? configured

  return (
    <section>
      <div className="mb-4">
        <h2 className="text-[15px] font-semibold text-[var(--foreground)]">{title}</h2>
        <p className="mt-0.5 text-[13px] text-[var(--muted-foreground)]">{description}</p>
      </div>

      {isLoading ? (
        <div className="flex flex-col gap-4">
          <Skeleton className="h-[88px] rounded-xl" />
          <Skeleton className="h-[88px] rounded-xl" />
        </div>
      ) : isError ? (
        <div className="rounded-xl border border-[var(--status-red-bg)] bg-[var(--status-red-bg)] px-5 py-4 text-sm text-[var(--status-red)]">
          Failed to load providers. Ensure the backend is running.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {/* Provider radio selection */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
            <label className="mb-1.5 block text-[12.5px] font-semibold text-[var(--foreground)]">
              Provider
            </label>
            <p className="mb-3 text-[12px] text-[var(--muted-foreground)]">
              Select the AI service for {title.toLowerCase()}.
            </p>
            <div className="flex flex-col gap-2" role="radiogroup" aria-label={`${title} provider`}>
              {(providers ?? []).map((provider) => {
                const isSelected = selectedProvider === provider.id
                return (
                  <label
                    key={provider.id}
                    className={`flex cursor-pointer items-center gap-3 rounded-lg border-2 px-4 py-3 transition-all duration-100 ${
                      isSelected
                        ? "border-[var(--brand-accent)] bg-[var(--brand-accent-light)]"
                        : "border-[var(--border)] bg-[var(--background)] hover:border-[var(--brand-accent)]/40"
                    }`}
                  >
                    <input
                      type="radio"
                      name={`provider-${title.replace(/\s+/g, "-").toLowerCase()}`}
                      value={provider.id}
                      checked={isSelected}
                      onChange={() => handleProviderChange(provider.id)}
                      className="accent-[var(--brand-accent)]"
                      aria-label={provider.label}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[13.5px] font-semibold text-[var(--foreground)]">
                          {provider.label}
                        </span>
                        {provider.configured ? (
                          <Badge variant="green" dot>Configured</Badge>
                        ) : (
                          <Badge variant="yellow" dot>Not Configured</Badge>
                        )}
                      </div>
                      {!provider.configured && (
                        <p className="mt-0.5 text-[11.5px] text-[var(--muted-foreground)]">
                          API key not set — add it to .env to enable this provider.
                        </p>
                      )}
                    </div>
                  </label>
                )
              })}
              {(providers ?? []).length === 0 && (
                <p className="text-[13px] text-[var(--muted-foreground)]">No providers available.</p>
              )}
            </div>
          </div>

          {/* Model select */}
          {selectedProvider && availableModels.length > 0 && (
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <label
                htmlFor={`model-select-${title.replace(/\s+/g, "-").toLowerCase()}`}
                className="mb-1.5 block text-[12.5px] font-semibold text-[var(--foreground)]"
              >
                Model
              </label>
              <p className="mb-3 text-[12px] text-[var(--muted-foreground)]">
                Choose the specific model for {currentProvider?.name ?? currentProvider?.label ?? selectedProvider}.
              </p>
              <select
                id={`model-select-${title.replace(/\s+/g, "-").toLowerCase()}`}
                value={selectedModel}
                onChange={(e) => handleModelChange(e.target.value)}
                className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
                aria-label={`${title} model`}
              >
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Current values + dirty-state Save */}
          <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
            <div className="text-[12.5px] text-[var(--muted-foreground)]">
              {selectedProvider ? (
                <>
                  Selected:{" "}
                  <span className="font-medium text-[var(--foreground)]">
                    {selectedProvider || "—"}
                  </span>{" "}
                  /
                  <span className="ml-1 font-medium text-[var(--foreground)]">
                    {selectedModel || "—"}
                  </span>
                  {!isSelectedConfigured && (
                    <span className="ml-2 text-[var(--status-yellow)]">(not configured)</span>
                  )}
                </>
              ) : (
                "No provider selected."
              )}
            </div>
            <Button
              onClick={handleSave}
              disabled={saving || !dirty || !selectedProvider}
              size="sm"
            >
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      )}
    </section>
  )
}

// ── AdminForm ──────────────────────────────────────────────────────────────────

function AdminForm() {
  const { data: imageProviders, isLoading: imageProvidersLoading, isError: imageProvidersError } = useProviders()
  const { data: textProviders, isLoading: textProvidersLoading, isError: textProvidersError } = useTextProviders()
  const { data: settings, isLoading: settingsLoading } = useSettings()
  const updateSettings = useUpdateSettings()

  // Track which section is saving (to show per-section pending state)
  const [savingSection, setSavingSection] = React.useState<"concept" | "prompt" | "image" | null>(null)

  async function handleConceptSave(provider: string, model: string) {
    setSavingSection("concept")
    try {
      await updateSettings.mutateAsync({ concept_provider: provider, concept_model: model })
      toast.success("Concept model saved!")
    } catch (err) {
      toast.error(`Failed to save concept model: ${String(err)}`)
    } finally {
      setSavingSection(null)
    }
  }

  async function handlePromptSave(provider: string, model: string) {
    setSavingSection("prompt")
    try {
      await updateSettings.mutateAsync({ prompt_provider: provider, prompt_model: model })
      toast.success("Prompt model saved!")
    } catch (err) {
      toast.error(`Failed to save prompt model: ${String(err)}`)
    } finally {
      setSavingSection(null)
    }
  }

  async function handleImageSave(provider: string, model: string) {
    setSavingSection("image")
    try {
      await updateSettings.mutateAsync({ image_provider: provider, image_model: model })
      toast.success("Image generation settings saved!")
    } catch (err) {
      toast.error(`Failed to save image settings: ${String(err)}`)
    } finally {
      setSavingSection(null)
    }
  }

  const textIsLoading = textProvidersLoading || settingsLoading
  const imageIsLoading = imageProvidersLoading || settingsLoading

  return (
    <div className="flex flex-col gap-8">
      {/* Concept Model */}
      <ProviderModelSection
        title="Concept Model"
        description="The AI model used to refine and deepen coloring page concepts."
        providers={textProviders}
        isLoading={textIsLoading}
        isError={textProvidersError}
        providerValue={settings?.concept_provider ?? ""}
        modelValue={settings?.concept_model ?? ""}
        configured={settings?.concept_configured ?? false}
        saving={savingSection === "concept"}
        onSave={handleConceptSave}
      />

      {/* Prompt Model */}
      <ProviderModelSection
        title="Prompt Model"
        description="The AI model used to write image generation prompts from the concept."
        providers={textProviders}
        isLoading={textIsLoading}
        isError={textProvidersError}
        providerValue={settings?.prompt_provider ?? ""}
        modelValue={settings?.prompt_model ?? ""}
        configured={settings?.prompt_configured ?? false}
        saving={savingSection === "prompt"}
        onSave={handlePromptSave}
      />

      {/* Image Generation */}
      <ProviderModelSection
        title="Image Generation"
        description="Choose the AI provider and model used for generating coloring page images."
        providers={imageProviders}
        isLoading={imageIsLoading}
        isError={imageProvidersError}
        providerValue={settings?.image_provider ?? ""}
        modelValue={settings?.image_model ?? ""}
        configured={settings?.image_configured ?? false}
        saving={savingSection === "image"}
        onSave={handleImageSave}
      />

      {/* Studio Preferences placeholder */}
      <section>
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-[var(--foreground)]">Studio Preferences</h2>
          <p className="mt-0.5 text-[13px] text-[var(--muted-foreground)]">
            General studio configuration.
          </p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
          <p className="text-[13px] text-[var(--muted-foreground)]">
            Additional preferences (theme, default page count, etc.) — coming in a future update.
          </p>
        </div>
      </section>

      {/* API Keys & Integrations */}
      <section>
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-[var(--foreground)]">API Keys & Integrations</h2>
          <p className="mt-0.5 text-[13px] text-[var(--muted-foreground)]">
            Provider API keys are managed via environment variables in{" "}
            <code className="rounded bg-[var(--muted)] px-1 py-0.5 text-[11.5px]">.env</code>.
          </p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
          <div className="flex flex-col gap-2">
            {[
              "ANTHROPIC_API_KEY",
              "GEMINI_API_KEY",
              "OPENAI_API_KEY",
              "STABILITY_API_KEY",
              "REPLICATE_API_KEY",
            ].map((key) => (
              <div key={key} className="flex items-center gap-3">
                <code className="flex-1 rounded bg-[var(--muted)] px-3 py-1.5 text-[12px] text-[var(--foreground)]">
                  {key}
                </code>
                <Badge variant="gray">env var</Badge>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}

// ── SettingsPage ───────────────────────────────────────────────────────────────

export function SettingsPage() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <div>
          <h1 className="text-[16px] font-semibold text-[var(--foreground)]">Admin</h1>
          <p className="text-[13px] text-[var(--text-muted)]">
            Configure LLM providers for concept refinement, prompt writing, and image generation.
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl">
          <AdminForm />
        </div>
      </div>
    </div>
  )
}
