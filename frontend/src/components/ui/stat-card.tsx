import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * StatCard — dashboard metric tile.
 * Matches the mockup's stat-card: label / big value / sub-text layout.
 */
interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
}

function StatCard({ label, value, sub, className, ...props }: StatCardProps) {
  return (
    <div
      data-slot="stat-card"
      className={cn(
        "rounded-[10px] border border-[var(--border)] bg-[var(--card)] px-5 py-[18px]",
        "shadow-[var(--shadow-card)]",
        className
      )}
      {...props}
    >
      <p className="mb-2 text-[12px] font-medium uppercase tracking-[0.04em] text-[var(--text-muted)]">
        {label}
      </p>
      <p className="mb-1.5 text-[28px] font-bold leading-none text-[var(--foreground)]">
        {value}
      </p>
      {sub && (
        <p className="text-[12px] text-[var(--muted-foreground)]">{sub}</p>
      )}
    </div>
  )
}

export { StatCard }
