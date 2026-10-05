import { cn } from "@/lib/utils"
import { humanize } from "@/lib/format"

type Tone = "green" | "red" | "amber" | "blue" | "violet" | "slate" | "sky"

const TONES: Record<Tone, string> = {
  green: "bg-success-soft text-emerald-800 ring-emerald-600/20",
  red: "bg-danger-soft text-red-800 ring-red-600/20",
  amber: "bg-warning-soft text-amber-900 ring-amber-600/25",
  blue: "bg-info-soft text-blue-800 ring-blue-600/20",
  violet: "bg-violet-50 text-violet-800 ring-violet-600/20",
  slate: "bg-slate-100 text-slate-700 ring-slate-500/20",
  sky: "bg-sky-50 text-sky-800 ring-sky-600/20",
}

const DOT: Record<Tone, string> = {
  green: "bg-emerald-500",
  red: "bg-red-500",
  amber: "bg-amber-500",
  blue: "bg-blue-500",
  violet: "bg-violet-500",
  slate: "bg-slate-400",
  sky: "bg-sky-500",
}

const STATUS: Record<string, { tone: Tone; label?: string }> = {
  // application
  SUBMITTED: { tone: "sky", label: "Submitted" },
  CONSENT_PENDING: { tone: "violet", label: "Consent pending" },
  PROCESSING: { tone: "blue", label: "Verifying data" },
  WAITING_FOR_SOURCE: { tone: "amber", label: "Waiting for department system" },
  FORWARDED_TO_DEPARTMENT: { tone: "sky", label: "Forwarded to department" },
  UNDER_REVIEW: { tone: "blue", label: "Under officer review" },
  CLARIFICATION_REQUESTED: { tone: "amber", label: "Clarification requested" },
  IN_PROGRESS: { tone: "blue", label: "In progress at department" },
  APPROVED: { tone: "green", label: "Approved" },
  REJECTED: { tone: "red", label: "Rejected" },
  RESOLVED: { tone: "green", label: "Resolved" },
  WITHDRAWN: { tone: "slate", label: "Withdrawn" },
  // workflow
  RUNNING: { tone: "blue" },
  WAITING_FOR_CONSENT: { tone: "violet" },
  WAITING_FOR_OFFICER: { tone: "blue" },
  WAITING_FOR_CITIZEN: { tone: "amber" },
  WAITING_FOR_EVENT: { tone: "sky" },
  WAITING_FOR_EXTERNAL: { tone: "sky" },
  COMPLETED: { tone: "green" },
  CANCELLED: { tone: "slate" },
  // health / quality / consent / events
  HEALTHY: { tone: "green" },
  DEGRADED: { tone: "amber" },
  DOWN: { tone: "red" },
  UNKNOWN: { tone: "slate" },
  VERIFIED: { tone: "green" },
  WARNING: { tone: "amber" },
  CONFLICT: { tone: "red" },
  UNAVAILABLE: { tone: "red", label: "Temporarily unavailable" },
  NOT_FOUND: { tone: "amber", label: "No record" },
  PENDING: { tone: "slate" },
  ACTIVE: { tone: "green" },
  REVOKED: { tone: "red" },
  EXPIRED: { tone: "slate" },
  PUBLISHED: { tone: "sky" },
  PROCESSED: { tone: "green" },
  FAILED: { tone: "red" },
  DEAD_LETTERED: { tone: "red", label: "Dead-lettered" },
  SUCCESS: { tone: "green" },
  FAILURE: { tone: "red" },
  DENIED: { tone: "red" },
  ALLOWED: { tone: "green" },
  CIRCUIT_OPEN: { tone: "red", label: "Circuit open" },
  OPEN: { tone: "amber" },
  CLOSED: { tone: "green" },
  HALF_OPEN: { tone: "amber", label: "Half-open" },
  CRITICAL: { tone: "red" },
  INFO: { tone: "sky" },
}

export function statusTone(status?: string | null): Tone {
  return (status && STATUS[status]?.tone) || "slate"
}

export function statusLabel(status?: string | null): string {
  if (!status) return "—"
  return STATUS[status]?.label ?? humanize(status)
}

export function StatusBadge({ status, label, className, dot = true }: { status?: string | null; label?: string; className?: string; dot?: boolean }) {
  const tone = statusTone(status)
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset whitespace-nowrap", TONES[tone], className)}
      data-status={status ?? ""}
    >
      {dot && <span className={cn("size-1.5 rounded-full", DOT[tone])} aria-hidden />}
      {label ?? statusLabel(status)}
    </span>
  )
}

export function HealthDot({ status, pulse = true }: { status?: string | null; pulse?: boolean }) {
  const tone = statusTone(status)
  return (
    <span className="relative inline-flex size-2.5" aria-hidden>
      {pulse && tone !== "slate" && <span className={cn("absolute inline-flex size-full animate-ping rounded-full opacity-50", DOT[tone])} />}
      <span className={cn("relative inline-flex size-2.5 rounded-full", DOT[tone])} />
    </span>
  )
}
