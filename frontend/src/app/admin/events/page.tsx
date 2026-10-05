"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowRight, Inbox, Repeat } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { JsonBlock, LoadingBlock, PageHeader, StatCard } from "@/components/common/page"
import { Pagination } from "@/components/common/pagination"
import { StatusBadge } from "@/components/common/status"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, errorMessage } from "@/lib/api"
import { formatDateTime, timeAgo } from "@/lib/format"
import { useAdminOverview, useSession } from "@/lib/hooks"
import type { EventItem, Page } from "@/lib/types"

interface Topology {
  exchange: string
  dead_letter_queue: { name: string; depth: number | null }
  consumers: { name: string; queue: string; routing_keys: string[]; depth: number | null }[]
}

const TYPES = [
  "", "APPLICATION_CREATED", "CONSENT_GRANTED", "CONSENT_REVOKED", "DATA_FETCHED", "SOURCE_UNAVAILABLE", "ELIGIBILITY_COMPLETED",
  "APPLICATION_SUBMITTED", "CLARIFICATION_REQUESTED", "APPLICATION_APPROVED", "APPLICATION_REJECTED", "GRIEVANCE_CREATED",
  "GRIEVANCE_RESOLVED", "NOTIFICATION_REQUESTED",
]
const STATUSES = ["", "PENDING", "PUBLISHED", "PROCESSED", "FAILED", "DEAD_LETTERED"]

function FilterSelect({ value, options, onChange, all, width = "w-56" }: { value: string; options: string[]; onChange: (v: string) => void; all: string; width?: string }) {
  return (
    <Select items={options.map((o) => ({ value: o, label: o || all }))} value={value} onValueChange={(v) => onChange(String(v ?? ""))}>
      <SelectTrigger className={`h-9 ${width}`}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((o) => (
          <SelectItem key={o || "all"} value={o}>
            {o || all}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

export default function EventsPage() {
  const qc = useQueryClient()
  const [type, setType] = useState("")
  const [status, setStatus] = useState("")
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<EventItem | null>(null)
  const overview = useAdminOverview()
  const session = useSession()
  const topology = useQuery({ queryKey: ["events", "topology"], queryFn: () => api.get<Topology>("events/topology"), refetchInterval: 5000 })
  const events = useQuery({
    queryKey: ["events", type, status, offset],
    queryFn: () => api.get<Page<EventItem>>("events", { event_type: type || undefined, status: status || undefined, limit: 30, offset }),
    refetchInterval: 4000,
  })
  const replay = useMutation({
    mutationFn: (id: string) => api.post<EventItem>(`events/${id}/replay`),
    onSuccess: (e) => {
      toast.success(`Event ${e.event_type} re-published`)
      setSelected(e)
      qc.invalidateQueries({ queryKey: ["events"] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const byStatus = overview.data?.events.by_status ?? {}

  return (
    <>
      <PageHeader
        eyebrow="Event-driven architecture"
        title="Events"
        description="Domain events are written to a transactional outbox, published to RabbitMQ (topic exchange) and consumed by independent services."
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Processed" value={byStatus.PROCESSED ?? 0} tone="green" />
        <StatCard label="Published / in flight" value={(byStatus.PUBLISHED ?? 0) + (byStatus.PENDING ?? 0)} />
        <StatCard label="Failed" value={byStatus.FAILED ?? 0} tone={byStatus.FAILED ? "red" : "slate"} />
        <StatCard label="Dead-letter queue" value={topology.data?.dead_letter_queue.depth ?? "—"} tone={topology.data?.dead_letter_queue.depth ? "red" : "slate"} hint={topology.data?.dead_letter_queue.name} />
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Broker topology</CardTitle>
          <CardDescription>
            Exchange <code className="font-mono">{topology.data?.exchange}</code> → durable consumer queues (dead-lettering to{" "}
            <code className="font-mono">{topology.data?.dead_letter_queue.name}</code>)
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {topology.data?.consumers.map((c) => (
            <div key={c.name} className="rounded-lg border bg-white p-3">
              <p className="flex items-center justify-between gap-2 font-semibold">
                {c.name}
                <span className="flex items-center gap-1 text-xs font-normal text-muted-foreground">
                  <Inbox className="size-3.5" /> {c.depth ?? "—"} queued
                </span>
              </p>
              <p className="font-mono text-[10px] text-muted-foreground">{c.queue}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {c.routing_keys.map((k) => (
                  <code key={k} className="rounded bg-secondary px-1.5 py-0.5 text-[10px]">
                    {k}
                  </code>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h2 className="mr-auto text-lg font-semibold">Event log</h2>
        <FilterSelect value={type} options={TYPES} all="All event types" onChange={(v) => { setType(v); setOffset(0) }} width="w-64" />
        <FilterSelect value={status} options={STATUSES} all="All statuses" onChange={(v) => { setStatus(v); setOffset(0) }} width="w-44" />
      </div>
      {events.isLoading && <LoadingBlock />}
      {events.data && (
        <div className="rounded-xl border bg-white">
          <Table data-testid="events-table">
            <TableHeader>
              <TableRow>
                <TableHead>Event</TableHead>
                <TableHead>Routing key</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Consumers</TableHead>
                <TableHead>Created</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {events.data.items.map((e) => (
                <TableRow key={e.id} className="cursor-pointer" onClick={() => setSelected(e)} data-event={e.event_type}>
                  <TableCell className="font-mono text-xs font-semibold">{e.event_type}</TableCell>
                  <TableCell className="font-mono text-[11px] text-muted-foreground">{e.routing_key}</TableCell>
                  <TableCell>
                    <StatusBadge status={e.status} />
                  </TableCell>
                  <TableCell className="text-xs">{e.processed_by.join(", ") || "—"}</TableCell>
                  <TableCell className="text-xs whitespace-nowrap text-muted-foreground">{timeAgo(e.created_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="px-4">
            <Pagination total={events.data.total} limit={30} offset={offset} onChange={setOffset} />
          </div>
        </div>
      )}

      <Sheet open={Boolean(selected)} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle className="font-mono">{selected.event_type}</SheetTitle>
                <SheetDescription>
                  {selected.aggregate_type} {selected.aggregate_id}
                </SheetDescription>
              </SheetHeader>
              <div className="space-y-3 px-4 pb-6 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={selected.status} /> <span className="text-muted-foreground">attempts {selected.attempts}</span>
                </div>
                <ol className="space-y-1 text-xs">
                  <li>Created {formatDateTime(selected.created_at)}</li>
                  <li className="flex items-center gap-1">
                    <ArrowRight className="size-3" /> Published {formatDateTime(selected.published_at)}
                  </li>
                  <li className="flex items-center gap-1">
                    <ArrowRight className="size-3" /> Processed {formatDateTime(selected.processed_at)} by {selected.processed_by.join(", ") || "—"}
                  </li>
                </ol>
                <p className="text-xs">
                  Correlation ID: <code className="font-mono">{selected.correlation_id}</code>
                </p>
                {selected.last_error && <p className="rounded bg-danger-soft p-2 text-xs text-red-800">{selected.last_error}</p>}
                <JsonBlock value={selected.payload} />
                {session.data?.user?.roles.includes("PLATFORM_ADMIN") && (
                  <Button variant="outline" onClick={() => replay.mutate(selected.id)} disabled={replay.isPending}>
                    <Repeat className="size-4" /> Replay event
                  </Button>
                )}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}
