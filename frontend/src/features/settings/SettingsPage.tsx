/**
 * SettingsPage — /settings route.
 * Provider dropdown + dependent model dropdown + configured indicator.
 * Loads GET /api/providers and GET /api/settings, saves via PUT /api/settings.
 */
import * as React from "react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useProviders, useSettings, useUpdateSettings } from "@/lib/api"

// ── Skeleton ───────────────────────────────────────────────────────────────────

function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-[var(--border)] ${className}`} />
}

// ── Settings Form ──────────────────────────────────────────────────────────────

function SettingsForm() {
  const { data: providers, isLoading: providersLoading, isError: providersError } = useProviders()
  const { data: settings, isLoading: settingsLoading } = useSettings()
  const updateSettings = useUpdateSettings()

  const [selectedProvider, setSelectedProvider] = React.useState<string>("")
  const [selectedModel, setSelectedModel] = React.useState<string>("")
  const [dirty, setDirty] = React.useState(false)

  // Initialize from loaded settings
  React.useEffect(() => {
    if (settings && !dirty) {
      setSelectedProvider(settings.image_provider ?? "")
      setSelectedModel(settings.image_model ?? "")
    }
  }, [settings, dirty])

  // Reset model when provider changes
  function handleProviderChange(providerId: string) {
    setSelectedProvider(providerId)
    const provider = providers?.find((p) => p.id === providerId)
    const firstModel = provider?.default_model ?? provider?.models[0]?.id ?? ""
    setSelectedModel(firstModel)
    setDirty(true)
  }

  function handleModelChange(model: string) {
    setSelectedModel(model)
    setDirty(true)
  }

  async function handleSave() {
    try {
      await updateSettings.mutateAsync({
        image_provider: selectedProvider,
        image_model: selectedModel,
      })
      setDirty(false)
      toast.success("Settings saved!")
    } catch (err) {
      toast.error(`Failed to save: ${String(err)}`)
    }
  }

  const isLoading = providersLoading || settingsLoading
  const currentProvider = providers?.find((p) => p.id === selectedProvider)
  const availableModels = currentProvider?.models ?? []

  return (
    <div className="flex flex-col gap-6">
      {/* Image Generation */}
      <section>
        <div className="mb-4">
          <h2 className="text-[15px] font-semibold text-[var(--foreground)]">Image Generation</h2>
          <p className="mt-0.5 text-[13px] text-[var(--muted-foreground)]">
            Choose the AI provider and model used for generating coloring page images.
          </p>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-4">
            <Skeleton className="h-[88px] rounded-xl" />
            <Skeleton className="h-[88px] rounded-xl" />
          </div>
        ) : providersError ? (
          <div className="rounded-xl border border-[var(--status-red-bg)] bg-[var(--status-red-bg)] px-5 py-4 text-sm text-[var(--status-red)]">
            Failed to load providers. Ensure the backend is running.
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {/* Provider selection */}
            <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
              <label className="mb-1.5 block text-[12.5px] font-semibold text-[var(--foreground)]">
                Image Provider
              </label>
              <p className="mb-3 text-[12px] text-[var(--muted-foreground)]">
                Select the service that generates your coloring pages.
              </p>
              <div className="flex flex-col gap-2">
                {(providers ?? []).map((provider) => {
                  const isSelected = selectedProvider === provider.id
                  return (
                    <label
                      key={provider.id}
                      className={`flex cursor-pointer items-center gap-3 rounded-lg border-2 px-4 py-3 transition-all duration-100 ${
                        isSelected
                          ? "border-[var(--brand-accent)] bg-[var(--accent-light)]"
                          : "border-[var(--border)] bg-[var(--background)] hover:border-[var(--brand-accent)]/40"
                      }`}
                    >
                      <input
                        type="radio"
                        name="provider"
                        value={provider.id}
                        checked={isSelected}
                        onChange={() => handleProviderChange(provider.id)}
                        className="accent-[var(--brand-accent)]"
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

            {/* Model selection */}
            {selectedProvider && availableModels.length > 0 && (
              <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5">
                <label className="mb-1.5 block text-[12.5px] font-semibold text-[var(--foreground)]">
                  Model
                </label>
                <p className="mb-3 text-[12px] text-[var(--muted-foreground)]">
                  Choose the specific model for {currentProvider?.name ?? selectedProvider}.
                </p>
                <select
                  value={selectedModel}
                  onChange={(e) => handleModelChange(e.target.value)}
                  className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 text-[13px] text-[var(--foreground)] outline-none focus:border-[var(--brand-accent)] focus:ring-2 focus:ring-[var(--brand-accent)]/20"
                >
                  {availableModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Current / save */}
            <div className="flex items-center justify-between rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
              <div className="text-[12.5px] text-[var(--muted-foreground)]">
                {settings ? (
                  <>
                    Current:{" "}
                    <span className="font-medium text-[var(--foreground)]">
                      {settings.image_provider || "—"}
                    </span>{" "}
                    /
                    <span className="ml-1 font-medium text-[var(--foreground)]">
                      {settings.image_model || "—"}
                    </span>
                  </>
                ) : (
                  "No settings saved."
                )}
              </div>
              <Button
                onClick={handleSave}
                disabled={updateSettings.isPending || !dirty || !selectedProvider}
                size="sm"
              >
                {updateSettings.isPending ? "Saving…" : "Save Settings"}
              </Button>
            </div>
          </div>
        )}
      </section>

      {/* Other settings placeholder sections */}
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

      <section>
        <div className="mb-3">
          <h2 className="text-[15px] font-semibold text-[var(--foreground)]">API Keys & Integrations</h2>
          <p className="mt-0.5 text-[13px] text-[var(--muted-foreground)]">
            Provider API keys are managed via environment variables in <code className="rounded bg-[var(--muted)] px-1 py-0.5 text-[11.5px]">.env</code>.
          </p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] px-5 py-4">
          <div className="flex flex-col gap-2">
            {["OPENAI_API_KEY", "STABILITY_API_KEY", "REPLICATE_API_KEY"].map((key) => (
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
          <h1 className="text-[16px] font-semibold text-[var(--foreground)]">Settings</h1>
          <p className="text-[13px] text-[var(--text-muted)]">
            Configure image generation providers, models, and studio preferences.
          </p>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl">
          <SettingsForm />
        </div>
      </div>
    </div>
  )
}
