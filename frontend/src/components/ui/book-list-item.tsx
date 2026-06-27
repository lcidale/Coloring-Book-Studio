import * as React from "react"
import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { ProgressBar } from "@/components/ui/progress"

/**
 * BookListItem — emoji thumbnail + title + meta + progress row.
 * Used inside the Active Book Projects card list.
 */
interface BookListItemProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string
  /** Emoji or content shown in the thumbnail */
  thumb?: React.ReactNode
  thumbBg?: string
  thumbColor?: string
  badgeVariant?: React.ComponentProps<typeof Badge>["variant"]
  badgeLabel?: string
  meta?: string
  progress?: number
}

function BookListItem({
  title,
  thumb,
  thumbBg = "#f5f5f4",
  thumbColor = "#78716c",
  badgeVariant = "gray",
  badgeLabel,
  meta,
  progress,
  className,
  ...props
}: BookListItemProps) {
  return (
    <div
      data-slot="book-list-item"
      role="button"
      tabIndex={0}
      className={cn(
        "flex cursor-pointer items-center gap-3.5 border-b border-[var(--border)] px-4 py-3.5",
        "last:border-b-0 hover:bg-[var(--background)] transition-colors duration-100",
        "focus-visible:outline-2 focus-visible:outline-[var(--ring)] focus-visible:outline-offset-[-2px]",
        className
      )}
      {...props}
    >
      {/* Thumbnail */}
      <div
        aria-hidden="true"
        className="flex size-[42px] h-[54px] w-[42px] shrink-0 items-center justify-center rounded text-xl font-bold"
        style={{ background: thumbBg, color: thumbColor }}
      >
        {thumb}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p className="mb-[3px] truncate text-[13.5px] font-semibold text-[var(--foreground)]">
          {title}
        </p>
        <div className="flex items-center gap-2 text-[12px] text-[var(--muted-foreground)]">
          {badgeLabel && (
            <Badge variant={badgeVariant} dot>
              {badgeLabel}
            </Badge>
          )}
          {meta && <span>{meta}</span>}
        </div>
      </div>

      {/* Progress */}
      {progress !== undefined && (
        <div className="w-20 shrink-0 text-right">
          <ProgressBar value={progress} />
          <p className="mt-1 text-[11px] text-[var(--text-muted)]">{progress}% done</p>
        </div>
      )}
    </div>
  )
}

export { BookListItem }
