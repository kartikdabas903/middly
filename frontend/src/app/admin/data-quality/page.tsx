"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { CheckCircle2 } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { ErrorState, LoadingBlock, PageHeader, StatCard } from "@/components/common/page"
import { Pagination } from "@/components/common/pagination"
import { StatusBadge } from "@/components/common/status"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { api, errorMessage } from "@/lib/api"
import { formatDateTime, humanize } from "@/lib/format"
import { useConnectors } from "@/lib/hooks"
import type { DQIssue, Page } from "@/lib/types"

interface Summary {
  by_source: { source_system: string; open: number; total: number }[]
  open_by_type: { issue_type: string; count: number }[]
}

const SOURCE_STATUS_HINT: Record<string, string> = {
  NAME_CONFLICT: "CONFLICT",
  DOB_CONFLICT: "CONFLICT",
  SOURCE_UNAVAILABLE: "UNAVAILABLE",
  INVALID_RESPONSE: "CONFLICT",
}

export default function DataQualityPage() {
  const qc = useQueryClient()
  const [status, setStatus] = useState("OPEN")
  const [offset, setOffset] = useState(0)
  const connectors = useConnectors()
  const summary = useQuery({ queryKey: ["dq", "summary"], queryFn: () => api.get<Summary>("data-quality/summary") })
  const issues = useQuery({
    queryKey: ["dq", "issues", status, offset],
    queryFn: () => api.get<Page<DQIssue>>("data-quality/issues", { status: status === "ALL" ? "" : status, limit: 50, offset }),
    refetchInterval: 8000,
  })
  const resolve = useMutation({
    mutationFn: (id: string) => api.post(`data-quality/issues/${id}/resolve`, { note: "Reviewed by administrator" }),
    onSuccess: () => {
      toast.success("Issue marked as reviewed")
      qc.invalidateQueries({ queryKey: ["dq"] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  // Per-source status: worst open issue for each source system.
  const openIssues = issues.data?.items.filter((i) => i.status === "OPEN") ?? []
  const sourceStatus = (system: string) => {
    const mine = openIssues.filter((i) => i.source_system === system)
    if (mine.some((i) => SOURCE_STATUS_HINT[i.issue_type] === "UNAVAILABLE")) return { status: "UNAVAILABLE", reason: "Source unavailable" }
    const conflict = mine.find((i) => SOURCE_STATUS_HINT[i.issue_type] === "CONFLICT")
    if (conflict) return { status: "CONFLICT", reason: conflict.message }
    if (mine.some((i) => i.severity !== "INFO")) return { status: "WARNING", reason: mine[0].message }
    return { status: "VERIFIED", reason: mine.length ? `${mine.length} informational finding(s)` : "No open issues" }
  }

  return (
    <>
      <PageHeader
        eyebrow="Master data management"
        title="Data quality"
        description="Issues detected while aggregating department data: missing fields, invalid formats, duplicates, conflicting names or dates, stale records and unavailable sources. Source records are never modified by the platform."
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {(summary.data?.open_by_type ?? []).slice(0, 4).map((t) => (
          <StatCard key={t.issue_type} label={humanize(t.issue_type)} value={t.count} tone={t.issue_type.includes("CONFLICT") ? "red" : "amber"} />
        ))}
      </div>
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Status by registry</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {(connectors.data ?? [])
            .filter((c) => c.data_categories.length > 0)
            .map((c) => {
              const st = sourceStatus(c.system_name)
              const counts = summary.data?.by_source.find((s) => s.source_system === c.system_name)
              return (
                <div key={c.key} className="rounded-lg border bg-white p-3" data-testid={`dq-${c.key}`}>
                  <p className="font-semibold">{c.system_name}</p>
                  <p className="mt-1 flex items-center gap-2 text-sm">
                    Status: <StatusBadge status={st.status} />
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">Reason: {st.reason}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {counts?.open ?? 0} open · {counts?.total ?? 0} total findings
                  </p>
                </div>
              )
            })}
        </CardContent>
      </Card>

      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Findings</h2>
        <Tabs value={status} onValueChange={(v) => { setStatus(String(v)); setOffset(0) }}>
          <TabsList>
            <TabsTrigger value="OPEN">Open</TabsTrigger>
            <TabsTrigger value="RESOLVED">Resolved</TabsTrigger>
            <TabsTrigger value="ALL">All</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      {issues.isLoading && <LoadingBlock />}
      {issues.error && <ErrorState error={issues.error} />}
      {issues.data && (
        <div className="rounded-xl border bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Detected</TableHead>
                <TableHead>Citizen</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Severity</TableHead>
                <TableHead>Details</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {issues.data.items.map((i) => (
                <TableRow key={i.id}>
                  <TableCell className="text-xs whitespace-nowrap">{formatDateTime(i.detected_at)}</TableCell>
                  <TableCell className="font-mono text-xs">{i.citizen_id}</TableCell>
                  <TableCell className="text-xs">{i.source_system}</TableCell>
                  <TableCell className="text-xs font-medium">{humanize(i.issue_type)}</TableCell>
                  <TableCell>
                    <StatusBadge status={i.severity} />
                  </TableCell>
                  <TableCell className="max-w-md text-xs text-muted-foreground">{i.message}</TableCell>
                  <TableCell>
                    {i.status === "OPEN" ? (
                      <Button size="xs" variant="outline" onClick={() => resolve.mutate(i.id)} disabled={resolve.isPending}>
                        <CheckCircle2 className="size-3" /> Reviewed
                      </Button>
                    ) : (
                      <span className="text-[11px] text-muted-foreground">{i.resolved_by}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="px-4">
            <Pagination total={issues.data.total} limit={50} offset={offset} onChange={setOffset} />
          </div>
        </div>
      )}
    </>
  )
}
