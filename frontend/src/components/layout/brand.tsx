import Link from "next/link"

import { cn } from "@/lib/utils"

/** Middly mark: two systems joined through a central node. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-8", className)} aria-hidden>
      <rect width="32" height="32" rx="8" className="fill-primary" />
      <circle cx="9" cy="16" r="3.2" fill="white" fillOpacity="0.55" />
      <circle cx="23" cy="16" r="3.2" fill="white" fillOpacity="0.55" />
      <path d="M12.2 16h7.6" stroke="white" strokeWidth="2" strokeLinecap="round" />
      <circle cx="16" cy="16" r="3.6" fill="white" />
    </svg>
  )
}

export function Brand({ href = "/", compact = false, className }: { href?: string; compact?: boolean; className?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5", className)} aria-label="Middly home">
      <LogoMark />
      {!compact && <span className="text-[17px] font-semibold tracking-tight text-foreground">Middly</span>}
    </Link>
  )
}
