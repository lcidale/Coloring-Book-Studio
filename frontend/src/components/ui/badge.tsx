import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

/**
 * Badge — inline status chip.
 * Variants map directly to the page-workflow statuses:
 *   idea | prompt | generated | review | revision | approved | print_ready | exported
 * Plus semantic color aliases: green | blue | yellow | red | purple | gray
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded px-[7px] py-[2px] text-[11px] font-medium leading-none select-none",
  {
    variants: {
      variant: {
        /* Semantic color aliases */
        green:  "bg-[var(--status-green-bg)]  text-[var(--status-green)]",
        blue:   "bg-[var(--status-blue-bg)]   text-[var(--status-blue)]",
        yellow: "bg-[var(--status-yellow-bg)] text-[var(--status-yellow)]",
        red:    "bg-[var(--status-red-bg)]    text-[var(--status-red)]",
        purple: "bg-[var(--status-purple-bg)] text-[var(--status-purple)]",
        gray:   "bg-[var(--status-gray-bg)]   text-[var(--status-gray)]",

        /* Page workflow status aliases */
        idea:        "bg-[var(--status-gray-bg)]   text-[var(--status-gray)]",
        prompt:      "bg-[var(--status-yellow-bg)] text-[var(--status-yellow)]",
        generated:   "bg-[var(--status-purple-bg)] text-[var(--status-purple)]",
        review:      "bg-[var(--status-blue-bg)]   text-[var(--status-blue)]",
        revision:    "bg-[var(--status-red-bg)]    text-[var(--status-red)]",
        approved:    "bg-[var(--status-green-bg)]  text-[var(--status-green)]",
        print_ready: "bg-[var(--status-green-bg)]  text-[var(--status-green)]",
        exported:    "bg-[var(--status-gray-bg)]   text-[var(--status-gray)]",

        /* shadcn-compat default */
        default:    "bg-[var(--status-gray-bg)]   text-[var(--status-gray)]",
        outline:    "border border-[var(--border)] text-foreground",
        secondary:  "bg-secondary text-secondary-foreground",
        destructive: "bg-[var(--status-red-bg)]   text-[var(--status-red)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export type PageStatus =
  | "idea"
  | "prompt"
  | "generated"
  | "review"
  | "revision"
  | "approved"
  | "print_ready"
  | "exported"

/** Human-readable label for each page status */
export const PAGE_STATUS_LABELS: Record<PageStatus, string> = {
  idea:        "Idea",
  prompt:      "Prompt",
  generated:   "Generated",
  review:      "Review",
  revision:    "Revision",
  approved:    "Approved",
  print_ready: "Print Ready",
  exported:    "Exported",
}

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  dot?: boolean
}

function Badge({ className, variant, dot = false, children, ...props }: BadgeProps) {
  return (
    <span
      data-slot="badge"
      className={cn(badgeVariants({ variant }), className)}
      {...props}
    >
      {dot && (
        <span
          aria-hidden="true"
          className="inline-block size-[6px] rounded-full bg-current opacity-80"
        />
      )}
      {children}
    </span>
  )
}

export { Badge, badgeVariants }
