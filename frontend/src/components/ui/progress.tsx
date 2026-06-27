import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * ProgressBar — thin horizontal progress indicator.
 * Matches the mockup's 4px accent-colored fill bar.
 */
interface ProgressBarProps extends React.HTMLAttributes<HTMLDivElement> {
  /** 0–100 */
  value: number
  /** Show percentage label below bar */
  showLabel?: boolean
  /** Label text — defaults to "{value}% done" */
  label?: string
}

function ProgressBar({
  value,
  showLabel = false,
  label,
  className,
  ...props
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value))

  return (
    <div className={cn("w-full", className)} {...props}>
      <div
        role="progressbar"
        aria-valuenow={clamped}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-[4px] w-full overflow-hidden rounded-full bg-[var(--border)]"
      >
        <div
          className="h-full rounded-full bg-[var(--brand-accent)] transition-all duration-300"
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <p className="mt-1 text-[11px] text-[var(--text-muted)]">
          {label ?? `${clamped}% done`}
        </p>
      )}
    </div>
  )
}

export { ProgressBar }
