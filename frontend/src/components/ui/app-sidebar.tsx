import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * AppSidebar — dark warm-stone sidebar matching the coloring-book-studio mockup.
 *
 * Structure:
 *   <AppSidebar>
 *     <SidebarLogo />
 *     <SidebarSection label="Workspace">
 *       <SidebarNavItem icon="⊞" active>Dashboard</SidebarNavItem>
 *       <SidebarNavItem icon="📖" badge={4}>Book Projects</SidebarNavItem>
 *     </SidebarSection>
 *     <SidebarFooter>
 *       <SidebarNavItem icon="⚙️">Settings</SidebarNavItem>
 *     </SidebarFooter>
 *   </AppSidebar>
 */

/* ── AppSidebar ── */
interface AppSidebarProps extends React.HTMLAttributes<HTMLElement> {}

function AppSidebar({ className, children, ...props }: AppSidebarProps) {
  return (
    <aside
      data-slot="app-sidebar"
      className={cn(
        "flex w-[220px] shrink-0 flex-col bg-[var(--sidebar)] text-[var(--sidebar-foreground)]",
        className
      )}
      {...props}
    >
      {children}
    </aside>
  )
}

/* ── SidebarLogo ── */
interface SidebarLogoProps {
  icon?: React.ReactNode
  title?: string
  subtitle?: string
}

function SidebarLogo({
  icon = "🎨",
  title = "CB Studio",
  subtitle = "Coloring Book Studio",
}: SidebarLogoProps) {
  return (
    <div className="border-b border-[var(--sidebar-border)] px-[18px] py-5 pb-4">
      <div className="flex items-center gap-2.5">
        <div
          aria-hidden="true"
          className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-[var(--brand-accent)] text-base"
        >
          {icon}
        </div>
        <div>
          <p className="text-[15px] font-semibold leading-[1.2] text-white">{title}</p>
          <p className="text-[11px] leading-tight text-[var(--sidebar-foreground)] opacity-70">
            {subtitle}
          </p>
        </div>
      </div>
    </div>
  )
}

/* ── SidebarSection ── */
interface SidebarSectionProps extends React.HTMLAttributes<HTMLDivElement> {
  label?: string
}

function SidebarSection({ label, children, className, ...props }: SidebarSectionProps) {
  return (
    <div
      data-slot="sidebar-section"
      className={cn("px-2.5 pb-2 pt-4", className)}
      {...props}
    >
      {label && (
        <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-[#57534e]">
          {label}
        </p>
      )}
      {children}
    </div>
  )
}

/* ── SidebarNavItem ── */
interface SidebarNavItemProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: React.ReactNode
  active?: boolean
  badge?: number | string
}

function SidebarNavItem({
  icon,
  active = false,
  badge,
  children,
  className,
  ...props
}: SidebarNavItemProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      data-slot="sidebar-nav-item"
      data-active={active || undefined}
      className={cn(
        "flex cursor-pointer items-center gap-2.5 rounded-[6px] px-2.5 py-[7px] text-[13.5px]",
        "transition-all duration-150 select-none",
        "text-[var(--sidebar-foreground)] hover:bg-[var(--sidebar-accent)] hover:text-white",
        "focus-visible:outline-2 focus-visible:outline-[var(--sidebar-ring)] focus-visible:outline-offset-[-1px]",
        active && "bg-[var(--sidebar-accent)] font-medium text-[var(--sidebar-accent-foreground)]",
        className
      )}
      aria-current={active ? "page" : undefined}
      {...props}
    >
      {icon && (
        <span
          aria-hidden="true"
          className="w-[18px] shrink-0 text-center text-[15px] opacity-85"
        >
          {icon}
        </span>
      )}
      <span className="flex-1">{children}</span>
      {badge !== undefined && (
        <span className="ml-auto rounded-[10px] bg-[var(--brand-accent)] px-1.5 py-px text-[10px] font-semibold leading-none text-white">
          {badge}
        </span>
      )}
    </div>
  )
}

/* ── SidebarFooter ── */
interface SidebarFooterProps extends React.HTMLAttributes<HTMLDivElement> {}

function SidebarFooter({ children, className, ...props }: SidebarFooterProps) {
  return (
    <div
      data-slot="sidebar-footer"
      className={cn(
        "mt-auto border-t border-[var(--sidebar-border)] px-2.5 py-3",
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export { AppSidebar, SidebarLogo, SidebarSection, SidebarNavItem, SidebarFooter }
