"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Bell, CheckSquare, Database, FileCheck2, Flag, Gavel, Lock, Play, Send, ShieldCheck, UserCheck, type LucideIcon } from "lucide-react"
import { useState } from "react"

import { ErrorState, JsonBlock, LoadingBlock, PageHeader } from "@/components/common/page"
import { Pagination } from "@/components/common/pagination"
import { StatusBadge } from "@/components/common/status"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api } from "@/lib/api"
import { formatDateTime, humanize, timeAgo } from "@/lib/format"
import type { Page, WorkflowDefinition, WorkflowInstanceItem } from "@/lib/types"

const STEP_ICON: Record<string, LucideIcon> = {
  start: Play,
  consent: Lock,
  fetch: Database,
  validation: ShieldCheck,
  eligibility: CheckSquare,
  department_submit: Send,
  human_review: UserCheck,
  decision: Gavel,
  notification: Bell,
  external_status: FileCheck2,
}

const STATUSES = ["", "RUNNING", "WAITING_FOR_CONSENT", "WAITING_FOR_SOURCE", "WAITING_FOR_OFFICER", "WAITING_FOR_CITIZEN", "WAITING_FOR_EVENT", "WAITING_FOR_EXTERNAL", "COMPLETED", "CANCELLED"]

function InstanceSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { data } = useQuery({
    queryKey: ["workflow-instance", id],
    queryFn: () => api.get<WorkflowInstanceItem>(`workflows/${id}`),
    enabled: Boolean(id),
    refetchInterval: 4000,
  })
  return (
    <Sheet open={Boolean(id)} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>
            {data?.application_number} · {data?.workflow_name}
          </SheetTitle>
          <SheetDescription>
            Instance {id} · <StatusBadge status={data?.status} />
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-3 px-4 pb-6">
          {data?.steps?.map((s) => (
            <div key={s.key} className="rounded-lg border bg-white p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-semibold">
                  {s.sequence}. {s.label} <code className="ml-1 text-[10px] text-muted-foreground">{s.type}</code>
                </p>
                <StatusBadge status={s.status} />
              </div>
              <p className="text-xs text-muted-foreground">
                attempts {s.attempts} · started {formatDateTime(s.started_at)} · completed {formatDateTime(s.completed_at)}
              </p>
              {s.error && <p className="mt-1 text-xs text-red-700">{s.error}</p>}
              {Object.keys(s.output).length > 0 && <JsonBlock value={s.output} className="mt-2 max-h-40" />}
            </div>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  )
}

export default function WorkflowsPage() {
  const [status, setStatus] = useState("")
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<string | null>(null)
  const defs = useQuery({ queryKey: ["workflow-defs"], queryFn: () => api.get<WorkflowDefinition[]>("workflows/definitions") })
  const instances = useQuery({
    queryKey: ["workflow-instances", status, offset],
    queryFn: () => api.get<Page<WorkflowInstanceItem>>("workflows", { status: status || undefined, limit: 25, offset }),
    refetchInterval: 5000,
  })

  return (
    <>
      <PageHeader
        eyebrow="Orchestration"
        title="Workflows"
        description="Workflows are JSON definitions (versioned in the database) executed by a generic engine. Every step state is persisted."
      />
      {defs.error && <ErrorState error={defs.error} />}
      <div className="mb-8 grid gap-4">
        {defs.data?.map((d) => (
          <Card key={d.id}>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-center gap-2">
                {d.name} <code className="rounded bg-muted px-1.5 py-0.5 text-xs font-normal">{d.code} v{d.version}</code>
                {d.is_active && <StatusBadge status="ACTIVE" />}
              </CardTitle>
              <CardDescription>{d.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="flex flex-wrap items-center gap-1.5">
                {d.definition.steps.map((s, i) => {
                  const Icon = STEP_ICON[s.type] ?? Flag
                  return (
                    <li key={s.key} className="flex items-center gap-1.5">
                      <span className="flex items-center gap-1.5 rounded-lg border bg-white px-2.5 py-1.5 text-xs">
                        <Icon className="size-3.5 text-primary" />
                        <span className="font-medium">{s.label}</span>
                        {s.connector && <code className="rounded bg-secondary px-1 text-[10px]">{s.connector}</code>}
                      </span>
                      {i < d.definition.steps.length - 1 && <ArrowRight className="size-3 text-muted-foreground" />}
                    </li>
                  )
                })}
              </ol>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Instances</h2>
        <Select
          items={STATUSES.map((s) => ({ value: s, label: s ? humanize(s) : "All states" }))}
          value={status}
          onValueChange={(v) => {
            setStatus(String(v ?? ""))
            setOffset(0)
          }}
        >
          <SelectTrigger className="h-9 w-60">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {STATUSES.map((s) => (
              <SelectItem key={s || "all"} value={s}>
                {s ? humanize(s) : "All states"}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {instances.isLoading && <LoadingBlock />}
      {instances.data && (
        <div className="rounded-xl border bg-white">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Application</TableHead>
                <TableHead>Workflow</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Current step</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {instances.data.items.map((w) => (
                <TableRow key={w.id} className="cursor-pointer" onClick={() => setSelected(w.id)}>
                  <TableCell className="font-mono text-sm font-semibold text-primary">{w.application_number}</TableCell>
                  <TableCell className="text-sm">{w.workflow_name}</TableCell>
                  <TableCell>
                    <StatusBadge status={w.status} />
                  </TableCell>
                  <TableCell className="font-mono text-xs">{w.current_step ?? "—"}</TableCell>
                  <TableCell className="text-xs tabular-nums">
                    {w.progress.completed}/{w.progress.total}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">{timeAgo(w.updated_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="px-4">
            <Pagination total={instances.data.total} limit={25} offset={offset} onChange={setOffset} />
          </div>
        </div>
      )}
      <InstanceSheet id={selected} onClose={() => setSelected(null)} />
    </>
  )
}
