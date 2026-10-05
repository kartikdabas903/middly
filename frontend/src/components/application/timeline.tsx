import { AlertTriangle, CheckCircle2, Circle, CircleDot, MinusCircle, XCircle } from "lucide-react"

import { formatDateTime } from "@/lib/format"
import type { TimelineStep } from "@/lib/types"
import { cn } from "@/lib/utils"

const ICON = {
  done: { icon: CheckCircle2, cls: "text-emerald-600", line: "bg-emerald-500" },
  current: { icon: CircleDot, cls: "text-primary animate-pulse", line: "bg-border" },
  blocked: { icon: AlertTriangle, cls: "text-amber-600", line: "bg-border" },
  failed: { icon: XCircle, cls: "text-red-600", line: "bg-border" },
  skipped: { icon: MinusCircle, cls: "text-slate-400", line: "bg-border" },
  pending: { icon: Circle, cls: "text-slate-300", line: "bg-border" },
} as const

function detailLine(step: TimelineStep): string | null {
  const d = step.detail as Record<string, unknown>
  if (step.state === "blocked") return `${String(d.system ?? "Department system")} temporarily unavailable — will retry`
  if (step.type === "fetch" && step.state === "done") {
    return d.found === false ? `No record in ${String(d.system)}` : `Retrieved from ${String(d.system)}${d.source_reference ? ` · ref ${String(d.source_reference)}` : ""}`
  }
  if (step.type === "eligibility" && step.state === "done") {
    return d.eligible ? "All eligibility rules passed" : `Failed: ${(d.failed_rules as string[] | undefined)?.join(", ")}`
  }
  if (step.type === "validation" && step.state === "done") return `Data quality: ${String(d.overall ?? "—")}`
  if (step.type === "department_submit" && d.reference) return `${String(d.system)} reference ${String(d.reference)}`
  if (step.type === "decision" && d.decision) return `${String(d.decision)} by ${String(d.decided_by ?? "—")}`
  if (step.type === "human_review" && step.state === "current") return "Waiting for a department officer"
  if (step.type === "consent" && step.state === "current") return "Waiting for your consent"
  if (step.type === "external_status" && d.external_status) return `Department status: ${String(d.external_status)}`
  if (step.type === "notification" && d.delivered_at) return "In-app notification delivered"
  if (step.state === "skipped") return "Not required"
  return null
}

export function WorkflowTimeline({ steps, compact = false }: { steps: TimelineStep[]; compact?: boolean }) {
  return (
    <ol className="relative" aria-label="Application timeline" data-testid="timeline">
      {steps.map((step, i) => {
        const meta = ICON[step.state] ?? ICON.pending
        const Icon = meta.icon
        const last = i === steps.length - 1
        const detail = detailLine(step)
        return (
          <li key={step.key} className="relative flex gap-3 pb-5 last:pb-0" data-state={step.state} data-step={step.key}>
            {!last && <span className={cn("absolute top-6 left-[11px] h-[calc(100%-1.25rem)] w-0.5", meta.line)} aria-hidden />}
            <Icon className={cn("relative z-10 size-6 shrink-0 bg-white", meta.cls)} aria-hidden />
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className={cn("text-sm font-semibold", step.state === "pending" || step.state === "skipped" ? "text-muted-foreground" : "text-foreground")}>
                  {step.label}
                  <span className="sr-only"> — {step.state}</span>
                </p>
                {!compact && (step.completed_at || step.started_at) && (
                  <time className="text-xs text-muted-foreground tabular-nums">{formatDateTime(step.completed_at ?? step.started_at)}</time>
                )}
              </div>
              {!compact && detail && (
                <p className={cn("text-xs", step.state === "blocked" ? "font-medium text-amber-700" : "text-muted-foreground")}>{detail}</p>
              )}
              {!compact && step.attempts > 1 && step.type !== "consent" && step.type !== "notification" && <p className="text-[11px] text-muted-foreground">Attempts: {step.attempts}</p>}
            </div>
          </li>
        )
      })}
    </ol>
  )
}

export function TimelineProgress({ steps }: { steps: TimelineStep[] }) {
  const done = steps.filter((s) => s.state === "done" || s.state === "skipped").length
  const pct = steps.length ? Math.round((done / steps.length) * 100) : 0
  return (
    <div className="flex items-center gap-2" aria-label={`${pct}% complete`}>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs tabular-nums text-muted-foreground">
        {done}/{steps.length}
      </span>
    </div>
  )
}
