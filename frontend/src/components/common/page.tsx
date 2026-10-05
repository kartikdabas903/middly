import { AlertCircle, Inbox, Loader2, type LucideIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { errorMessage } from "@/lib/api"
import { cn } from "@/lib/utils"

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: React.ReactNode
  description?: React.ReactNode
  actions?: React.ReactNode
  eyebrow?: React.ReactNode
}) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0 space-y-1">
        {eyebrow && <div className="text-sm text-muted-foreground">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        {description && <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "primary",
  testId,
}: {
  label: string
  value: React.ReactNode
  hint?: React.ReactNode
  icon?: LucideIcon
  tone?: "primary" | "green" | "amber" | "red" | "slate"
  testId?: string
}) {
  const toneCls = {
    primary: "bg-primary/10 text-primary",
    green: "bg-success-soft text-emerald-700",
    amber: "bg-warning-soft text-amber-700",
    red: "bg-danger-soft text-red-700",
    slate: "bg-muted text-slate-600",
  }[tone]
  return (
    <Card size="sm" className="gap-2" data-testid={testId}>
      <CardContent className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-[13px] font-medium text-muted-foreground">{label}</p>
          <p className="text-[26px] leading-tight font-semibold tabular-nums tracking-tight">{value}</p>
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
        {Icon && (
          <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-md", toneCls)}>
            <Icon className="size-4.5" aria-hidden />
          </span>
        )}
      </CardContent>
    </Card>
  )
}

export function LoadingBlock({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)} aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  )
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} aria-hidden />
}

export function ErrorState({ error, title = "Could not load data" }: { error: unknown; title?: string }) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="size-4" />
      <AlertTitle>{title}</AlertTitle>
      <AlertDescription>{errorMessage(error)}</AlertDescription>
    </Alert>
  )
}

export function EmptyState({ icon: Icon = Inbox, title, description, action }: { icon?: LucideIcon; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed bg-white px-6 py-12 text-center">
      <span className="flex size-11 items-center justify-center rounded-full bg-muted">
        <Icon className="size-5 text-muted-foreground" aria-hidden />
      </span>
      <p className="font-semibold">{title}</p>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}

export function KeyValue({ label, children, className }: { label: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0 space-y-0.5", className)}>
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium break-words text-foreground">{children ?? "—"}</dd>
    </div>
  )
}

export function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border bg-muted px-1.5 py-px text-[11px] font-medium text-muted-foreground">
      {children}
    </span>
  )
}

export function JsonBlock({ value, className }: { value: unknown; className?: string }) {
  return (
    <pre className={cn("max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-[11px] leading-relaxed text-slate-100", className)}>
      {JSON.stringify(value, null, 2)}
    </pre>
  )
}
