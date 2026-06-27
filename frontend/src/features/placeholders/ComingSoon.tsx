/**
 * ComingSoon — generic "coming soon" placeholder for unbuilt studio views.
 * Used by all nav routes that don't yet have a feature implementation.
 */
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"

interface ComingSoonProps {
  icon?: string
  title?: string
  description?: string
}

export function ComingSoon({
  icon = "🚧",
  title = "Coming Soon",
  description = "This section is under construction. Check back soon.",
}: ComingSoonProps) {
  const navigate = useNavigate()
  return (
    <div className="flex min-h-full flex-col">
      {/* Minimal top bar */}
      <header className="flex shrink-0 items-center border-b border-[var(--border)] bg-[var(--card)] px-6 py-3">
        <h1 className="text-[16px] font-semibold text-[var(--foreground)]">{title}</h1>
      </header>

      {/* Centered placeholder card */}
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--card)] px-8 py-10 text-center shadow-[var(--shadow-card)]">
          <div className="mb-4 text-5xl">{icon}</div>
          <h2 className="mb-2 text-[18px] font-bold text-[var(--foreground)]">{title}</h2>
          <p className="mb-6 text-[13.5px] text-[var(--muted-foreground)]">{description}</p>
          <Button variant="outline" onClick={() => navigate("/")}>
            Back to Dashboard
          </Button>
        </div>
      </div>
    </div>
  )
}
