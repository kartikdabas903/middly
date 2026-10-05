"use client"

import { useMutation, useQuery } from "@tanstack/react-query"
import { Fingerprint, Search, ShieldCheck, ShieldX } from "lucide-react"
import { useState } from "react"

import { ErrorState, JsonBlock, KeyValue, LoadingBlock, PageHeader, Spinner } from "@/components/common/page"
import { Pagination } from "@/components/common/pagination"
import { StatusBadge } from "@/components/common/status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api } from "@/lib/api"
import { formatDateTime, humanize } from "@/lib/format"
import type { AuditEntry, Page } from "@/lib/types"

const LIMIT = 50

export default function AuditLogsPage() {
  const [filters, setFilters] = useState({ action: "", actor: "", status: "", correlation_id: "", resource_id: "" })
  const [draft, setDraft] = useState(filters)
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<AuditEntry | null>(null)
  const actions = useQuery({ queryKey: ["audit", "actions"], queryFn: () => api.get<string[]>("audit-logs/actions") })
  const logs = useQuery({
    queryKey: ["audit", filters, offset],
    queryFn: () => api.get<Page<AuditEntry>>("audit-logs", { ...filters, limit: LIMIT, offset }),
    refetchInterval: 10000,
  })
  const verify = useMutation({ mutationFn: () => api.get<{ valid: boolean; checked: number; broken_at_id?: number; head_hash?: string }>("audit-logs/verify") })

  const apply = () => {
    setFilters(draft)
    setOffset(0)
  }

  return (
    <>
      <PageHeader
        eyebrow="Accountability"
        title="Audit logs"
        description="Append-only (enforced by a database trigger) and SHA-256 hash-chained. Every consent, data access, decision and failure is recorded."
        actions={
          <Button variant="outline" onClick={() => verify.mutate()} disabled={verify.isPending} data-testid="verify-chain">
            {verify.isPending ? <Spinner /> : <Fingerprint className="size-4" />} Verify integrity
          </Button>
        }
      />
      {verify.data && (
        <Alert variant={verify.data.valid ? "default" : "destructive"} className={verify.data.valid ? "mb-4 border-emerald-300 bg-success-soft" : "mb-4"}>
          {verify.data.valid ? <ShieldCheck className="size-4 text-emerald-700" /> : <ShieldX className="size-4" />}
          <AlertTitle>{verify.data.valid ? "Audit chain intact" : "Audit chain broken"}</AlertTitle>
          <AlertDescription>
            {verify.data.valid
              ? `${verify.data.checked} records verified. Head hash ${verify.data.head_hash?.slice(0, 16)}…`
              : `Mismatch at record #${verify.data.broken_at_id} after ${verify.data.checked} valid records.`}
          </AlertDescription>
        </Alert>
      )}

      <div className="mb-4 grid gap-2 rounded-xl border bg-white p-3 md:grid-cols-[1.4fr_1fr_0.8fr_1.2fr_auto]">
        <Select
          items={[{ value: "", label: "All actions" }, ...(actions.data ?? []).map((a) => ({ value: a, label: a }))]}
          value={draft.action}
          onValueChange={(v) => setDraft((d) => ({ ...d, action: String(v ?? "") }))}
        >
          <SelectTrigger className="h-9 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All actions</SelectItem>
            {(actions.data ?? []).map((a) => (
              <SelectItem key={a} value={a}>
                {a}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input className="h-9" placeholder="Actor (e.g. officer1)" value={draft.actor} onChange={(e) => setDraft((d) => ({ ...d, actor: e.target.value }))} />
        <Select
          items={["", "SUCCESS", "FAILURE", "DENIED", "NOT_FOUND"].map((s) => ({ value: s, label: s || "Any status" }))}
          value={draft.status}
          onValueChange={(v) => setDraft((d) => ({ ...d, status: String(v ?? "") }))}
        >
          <SelectTrigger className="h-9 w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {["", "SUCCESS", "FAILURE", "DENIED", "NOT_FOUND"].map((s) => (
              <SelectItem key={s || "any"} value={s}>
                {s || "Any status"}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          className="h-9 font-mono text-xs"
          placeholder="Correlation ID"
          value={draft.correlation_id}
          onChange={(e) => setDraft((d) => ({ ...d, correlation_id: e.target.value.trim() }))}
        />
        <Button onClick={apply} className="h-9">
          <Search className="size-4" /> Search
        </Button>
      </div>

      {logs.isLoading && <LoadingBlock />}
      {logs.error && <ErrorState error={logs.error} />}
      {logs.data && (
        <div className="rounded-xl border bg-white">
          <Table data-testid="audit-table">
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Timestamp</TableHead>
                <TableHead>Actor / role</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead className="hidden lg:table-cell">Source → destination</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logs.data.items.map((a) => (
                <TableRow key={a.id} className="cursor-pointer" onClick={() => setSelected(a)}>
                  <TableCell className="text-xs text-muted-foreground tabular-nums">{a.id}</TableCell>
                  <TableCell className="text-xs whitespace-nowrap">{formatDateTime(a.timestamp)}</TableCell>
                  <TableCell className="text-xs">
                    {a.actor}
                    <span className="block text-muted-foreground">{humanize(a.role)}</span>
                  </TableCell>
                  <TableCell className="font-mono text-[11px] font-semibold">{a.action}</TableCell>
                  <TableCell className="max-w-40 truncate text-xs">
                    {a.resource}
                    <span className="block truncate font-mono text-[10px] text-muted-foreground">{a.resource_id}</span>
                  </TableCell>
                  <TableCell className="hidden text-xs text-muted-foreground lg:table-cell">
                    {[a.source_system, a.destination_system].filter(Boolean).join(" → ") || "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={a.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="px-4">
            <Pagination total={logs.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
          </div>
        </div>
      )}

      <Sheet open={Boolean(selected)} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle className="font-mono text-base">{selected.action}</SheetTitle>
                <SheetDescription>Audit record #{selected.id}</SheetDescription>
              </SheetHeader>
              <div className="space-y-4 px-4 pb-6">
                <dl className="grid grid-cols-2 gap-3">
                  <KeyValue label="Timestamp">{formatDateTime(selected.timestamp)}</KeyValue>
                  <KeyValue label="Status">
                    <StatusBadge status={selected.status} />
                  </KeyValue>
                  <KeyValue label="Actor">{selected.actor}</KeyValue>
                  <KeyValue label="Role">{selected.role}</KeyValue>
                  <KeyValue label="Resource">{selected.resource}</KeyValue>
                  <KeyValue label="Resource ID">
                    <code className="font-mono text-xs">{selected.resource_id ?? "—"}</code>
                  </KeyValue>
                  <KeyValue label="Source system">{selected.source_system ?? "—"}</KeyValue>
                  <KeyValue label="Destination system">{selected.destination_system ?? "—"}</KeyValue>
                  <KeyValue label="IP address">{selected.ip_address ?? "—"}</KeyValue>
                  <KeyValue label="Correlation ID" className="col-span-2">
                    <button
                      className="font-mono text-xs text-primary hover:underline"
                      onClick={() => {
                        const f = { ...filters, action: "", actor: "", correlation_id: selected.correlation_id ?? "" }
                        setDraft(f)
                        setFilters(f)
                        setSelected(null)
                      }}
                    >
                      {selected.correlation_id}
                    </button>
                  </KeyValue>
                  <KeyValue label="Hash" className="col-span-2">
                    <code className="font-mono text-[10px] break-all">{selected.hash}</code>
                  </KeyValue>
                </dl>
                <JsonBlock value={selected.details} />
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </>
  )
}
