"use client"

import { Activity, Cable, Gauge, Timer } from "lucide-react"

import { HealthDot, StatusBadge } from "@/components/common/status"
import { Card, CardContent } from "@/components/ui/card"
import { timeAgo } from "@/lib/format"
import type { ConnectorCard } from "@/lib/types"
import { cn } from "@/lib/utils"

export function ConnectorHealthCard({ c, children }: { c: ConnectorCard; children?: React.ReactNode }) {
  const tone = c.status === "HEALTHY" ? "border-l-emerald-500" : c.status === "DEGRADED" ? "border-l-amber-500" : c.status === "DOWN" ? "border-l-red-500" : "border-l-slate-300"
  return (
    <Card size="sm" className={cn("border-l-4", tone)} data-testid={`connector-${c.key}`} data-status={c.status}>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="flex items-center gap-2 font-semibold">
              <HealthDot status={c.status} /> {c.system_name}
            </p>
            {c.department && c.department !== c.system_name && <p className="truncate text-xs text-muted-foreground">{c.department}</p>}
          </div>
          <StatusBadge status={c.status} dot={false} />
        </div>
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div className="flex items-center gap-1.5">
            <Timer className="size-3.5 text-muted-foreground" />
            <dt className="sr-only">Latency</dt>
            <dd>{c.latency_ms !== null ? `${Math.round(c.latency_ms)} ms` : "—"}</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <Gauge className="size-3.5 text-muted-foreground" />
            <dt className="sr-only">Circuit</dt>
            <dd className={cn(c.circuit_state === "OPEN" && "font-semibold text-red-700")}>Circuit {c.circuit_state.toLowerCase().replace("_", "-")}</dd>
          </div>
          <div className="flex items-center gap-1.5">
            <Activity className="size-3.5 text-muted-foreground" />
            <dt className="sr-only">Calls</dt>
            <dd>
              {c.calls_24h} calls/24h{c.success_rate_24h !== null && ` · ${c.success_rate_24h}% ok`}
            </dd>
          </div>
          <div className="flex items-center gap-1.5">
            <Cable className="size-3.5 text-muted-foreground" />
            <dt className="sr-only">Auth</dt>
            <dd className="truncate">{c.auth_type.replaceAll("_", " ").toLowerCase()}</dd>
          </div>
        </dl>
        <p className="text-[11px] text-muted-foreground">
          Checked {timeAgo(c.last_checked_at)}
          {c.message && c.status !== "HEALTHY" && <span className="block truncate text-red-700">{c.message}</span>}
        </p>
        {children}
      </CardContent>
    </Card>
  )
}
