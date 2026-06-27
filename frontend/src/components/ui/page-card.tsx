import * as React from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import type { PageStatus } from "@/components/ui/badge"
import { PAGE_STATUS_LABELS } from "@/components/ui/badge"

/**
 * PageCard — thumbnail + name + status badge tile.
 * Used in the "Recently Generated Pages" grid.
 */
interface PageCardProps extends React.HTMLAttributes<HTMLDivElement> {
  name: string
  status: PageStatus
  /** Emoji or small element shown in the thumbnail area */
  thumb?: React.ReactNode
  thumbBg?: string
}

const STATUS_VARIANT_MAP: Record<PageStatus, React.ComponentProps<typeof Badge>["variant"]> = {
  idea:        "idea",
  prompt:      "prompt",
  generated:   "generated",
  review:      "review",
  revision:    "revision",
  approved:    "approved",
  print_ready: "print_ready",
  exported:    "exported",
}

function PageCard({
  name,
  status,
  thumb,
  thumbBg = "var(--muted)",
  className,
  ...props
}: PageCardProps) {
  return (
    <div
      data-slot="page-card"
      role="button"
      tabIndex={0}
      className={cn(
        "overflow-hidden rounded-lg border border-[var(--border)] transition-all duration-150",
        "cursor-pointer hover:border-[var(--brand-accent)] hover:shadow-[var(--shadow-card-md)]",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-2",
        className
      )}
      {...props}
    >
      {/* Thumbnail */}
      <div
        aria-hidden="true"
        className="flex h-[90px] items-center justify-center border-b border-[var(--border)] text-[28px]"
        style={{ background: thumbBg }}
      >
        {thumb}
      </div>

      {/* Info */}
      <div className="px-[10px] py-2">
        <p className="mb-1 truncate text-[12px] font-semibold text-[var(--foreground)]">
          {name}
        </p>
        <Badge variant={STATUS_VARIANT_MAP[status]} dot>
          {PAGE_STATUS_LABELS[status]}
        </Badge>
      </div>
    </div>
  )
}

export { PageCard }
