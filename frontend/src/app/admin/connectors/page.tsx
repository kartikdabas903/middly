"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { HeartPulse, Puzzle } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { ConnectorHealthCard } from "@/components/admin/connector-card"
import { FaultButtons } from "@/components/admin/demo-controls"
import { ErrorState, KeyValue, LoadingBlock, PageHeader, Spinner } from "@/components/common/page"
import { StatusBadge } from "@/components/common/status"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, errorMessage } from "@/lib/api"
import { formatDateTime } from "@/lib/format"
import { useConnectors, useSession } from "@/lib/hooks"
import type { ConnectorCard, Page } from "@/lib/types"

interface Call {
  id: string
  operation: string
  status: string
  http_status: number | null
  latency_ms: number
  attempts: number
  error: string | null
  correlation_id: string | null
  created_at: string
}

function CallsTable({ connector }: { connector: ConnectorCard }) {
  const { data, isLoading } = useQuery({
    queryKey: ["connector-calls", connector.key],
    queryFn: () => api.get<Page<Call>>(`connectors/${connector.key}/calls`, { limit: 25 }),
    refetchInterval: 5000,
  })
  if (isLoading) return <LoadingBlock rows={2} />
  return (
    <div className="max-h-96 overflow-auto rounded-lg border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead>Operation</TableHead>
            <TableHead>Result</TableHead>
            <TableHead>HTTP</TableHead>
            <TableHead>Latency</TableHead>
            <TableHead>Attempts</TableHead>
            <TableHead>Correlation ID</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data?.items.map((c) => (
            <TableRow key={c.id}>
              <TableCell className="text-xs whitespace-nowrap">{formatDateTime(c.created_at)}</TableCell>
              <TableCell className="font-mono text-xs">{c.operation}</TableCell>
              <TableCell>
                <StatusBadge status={c.status} />
                {c.error && <span className="block max-w-56 truncate text-[11px] text-red-700">{c.error}</span>}
              </TableCell>
              <TableCell className="text-xs">{c.http_status ?? "—"}</TableCell>
              <TableCell className="text-xs tabular-nums">{Math.round(c.latency_ms)} ms</TableCell>
              <TableCell className="text-xs">{c.attempts}</TableCell>
              <TableCell className="max-w-40 truncate font-mono text-[10px] text-muted-foreground">{c.correlation_id}</TableCell>
            </TableRow>
          ))}
          {data?.items.length === 0 && (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-sm text-muted-foreground">
                No calls yet
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  )
}

export default function ConnectorsPage() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useConnectors()
  const session = useSession()
  const isPlatformAdmin = session.data?.user?.roles.includes("PLATFORM_ADMIN") ?? false
  const [selected, setSelected] = useState<string | null>(null)

  const check = useMutation({
    mutationFn: () => api.post<{ key: string; status: string }[]>("connectors/health-check"),
    onSuccess: (res) => {
      toast.success(`Health check complete: ${res.map((r) => `${r.key} ${r.status}`).join(", ")}`)
      qc.invalidateQueries({ queryKey: ["connectors"] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const toggle = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) => api.patch(`connectors/${key}`, { enabled }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["connectors"] }),
    onError: (e) => toast.error(errorMessage(e)),
  })

  if (isLoading) return <LoadingBlock rows={4} />
  if (error || !data) return <ErrorState error={error} />
  const current = data.find((c) => c.key === selected) ?? data[0]

  return (
    <>
      <PageHeader
        eyebrow="Connector framework"
        title="Department connectors"
        description="Each department integrates through a plugin implementing the standard connector interface. Health is checked live against each system."
        actions={
          <Button size="lg" onClick={() => check.mutate()} disabled={check.isPending} data-testid="run-health-check">
            {check.isPending ? <Spinner /> : <HeartPulse className="size-4" />} Run live health checks
          </Button>
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
        {data.map((c) => (
          <button key={c.key} onClick={() => setSelected(c.key)} className="text-left">
            <ConnectorHealthCard c={c} />
          </button>
        ))}
      </div>

      {current && (
        <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between gap-2">
                {current.name} <StatusBadge status={current.status} />
              </CardTitle>
              <CardDescription>{current.description}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <dl className="grid grid-cols-2 gap-4">
                <KeyValue label="Connector key">
                  <code className="font-mono">{current.key}</code>
                </KeyValue>
                <KeyValue label="Version">{current.version}</KeyValue>
                <KeyValue label="Base URL" className="col-span-2">
                  <code className="font-mono text-xs">{current.base_url}</code>
                </KeyValue>
                <KeyValue label="Authentication">{current.auth_type}</KeyValue>
                <KeyValue label="Data format">{current.data_format}</KeyValue>
                <KeyValue label="Data categories">{current.data_categories.join(", ") || "— (destination system)"}</KeyValue>
                <KeyValue label="Timeout / retries">
                  {current.timeout_seconds}s / {current.max_retries}
                </KeyValue>
                <KeyValue label="Capabilities" className="col-span-2">
                  <span className="flex flex-wrap gap-1">
                    {current.capabilities.map((cap) => (
                      <code key={cap} className="rounded bg-muted px-1.5 py-0.5 text-[11px]">
                        {cap}()
                      </code>
                    ))}
                  </span>
                </KeyValue>
                <KeyValue label="Plugin module" className="col-span-2">
                  <code className="font-mono text-xs">connectors/{current.plugin_module}</code>
                </KeyValue>
                <KeyValue label="Circuit breaker">
                  <StatusBadge status={current.circuit_state} />
                </KeyValue>
                <KeyValue label="Last checked">{formatDateTime(current.last_checked_at)}</KeyValue>
              </dl>
              {isPlatformAdmin && (
                <div className="space-y-3 rounded-lg border bg-muted/30 p-3">
                  <label className="flex items-center justify-between gap-2 text-sm font-medium">
                    Connector enabled
                    <Switch checked={current.enabled} onCheckedChange={(v) => toggle.mutate({ key: current.key, enabled: Boolean(v) })} />
                  </label>
                  {session.data?.environment.sandbox && (
                    <div className="space-y-1.5">
                      <p className="text-sm font-medium">Simulate an outage (sandbox)</p>
                      <FaultButtons connector={current} />
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Recent calls through {current.system_name}</CardTitle>
                <CardDescription>Every invocation is persisted with latency, attempts (retries) and correlation ID.</CardDescription>
              </CardHeader>
              <CardContent>
                <CallsTable connector={current} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Puzzle className="size-4 text-primary" /> Onboarding a new department
                </CardTitle>
                <CardDescription>No change to the core workflow engine is required.</CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-[11px] leading-relaxed text-slate-100">{`# connectors/agriculture/connector.py
class AgricultureConnector(BaseConnector):
    key = "agriculture"
    system_name = "Agriculture Registry"
    data_categories = ["LAND_RECORDS"]
    auth_type = "API_KEY"
    base_url_env = "AGRICULTURE_BASE_URL"
    credential_env = {"api_key": "AGRICULTURE_API_KEY"}

    def authenticate(self): return {"X-API-Key": self.config.credentials["api_key"]}
    def get_citizen(self, citizen_id):
        raw = self.get_json(f"/farmers/{citizen_id}")
        return self.transform_response(raw, citizen_id=citizen_id)
    def transform_response(self, raw, kind="citizen", **ctx): ...`}</pre>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </>
  )
}
