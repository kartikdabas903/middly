"use client"

import { Activity, AlertTriangle, Cable, ClipboardList, ExternalLink, Gauge, Radio, ShieldCheck, Timer } from "lucide-react"
import Link from "next/link"
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

import { ConnectorHealthCard } from "@/components/admin/connector-card"
import { ErrorState, LoadingBlock, PageHeader, StatCard } from "@/components/common/page"
import { StatusBadge, statusLabel } from "@/components/common/status"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDuration, humanize, timeAgo } from "@/lib/format"
import { useAdminOverview, useConnectors, useSession } from "@/lib/hooks"
import { cn } from "@/lib/utils"

const AXIS = { fontSize: 11, fill: "var(--muted-foreground)" }

function ChartCard({ title, description, children, className }: { title: string; description?: string; children: React.ReactNode; className?: string }) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent className="h-64">{children}</CardContent>
    </Card>
  )
}

export default function AdminDashboard() {
  const { data, isLoading, error } = useAdminOverview()
  const connectors = useConnectors()
  const session = useSession()
  const links = session.data?.links ?? {}

  if (isLoading) return <LoadingBlock rows={5} />
  if (error || !data) return <ErrorState error={error} />

  const evTotal = Object.values(data.events.by_status).reduce((a, b) => a + b, 0)
  const workflowData = Object.entries(data.workflows).map(([status, count]) => ({ status: humanize(status.replace("WAITING_FOR_", "Waiting: ")), count }))
  const statusData = Object.entries(data.applications.by_status).map(([status, count]) => ({ status: statusLabel(status), count }))
  const cards = connectors.data ?? data.connectors

  return (
    <>
      <PageHeader
        eyebrow="Platform administration"
        title="Interoperability dashboard"
        description="Live view of API traffic, department connectors, workflows, events, consent and data quality."
        actions={
          <>
            {[
              ["Grafana", links.grafana],
              ["Prometheus", links.prometheus],
              ["RabbitMQ", links.rabbitmq],
              ["API docs", links.swagger],
            ].map(([label, href]) =>
              href ? (
                <a key={label} href={href} target="_blank" rel="noreferrer" className={buttonVariants({ variant: "outline", size: "sm" })}>
                  {label} <ExternalLink className="size-3" />
                </a>
              ) : null,
            )}
          </>
        }
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="admin-kpis">
        <StatCard label="API requests" value={data.api.requests.toLocaleString("en-IN")} hint={`${data.api.failures} server failures · ${data.api.client_errors} client errors`} icon={Activity} testId="kpi-api" />
        <StatCard label="Avg API latency" value={`${data.api.avg_latency_ms} ms`} hint="Through the API gateway" icon={Timer} tone="slate" />
        <StatCard
          label="Connector calls"
          value={data.connector_calls.total.toLocaleString("en-IN")}
          hint={`${data.connector_calls.failed} failed · avg ${data.connector_calls.avg_latency_ms} ms`}
          icon={Cable}
          tone={data.connector_calls.failed ? "amber" : "green"}
          testId="kpi-connector-calls"
        />
        <StatCard label="Avg processing time" value={formatDuration(data.avg_processing_seconds)} hint="Submission → decision" icon={Gauge} tone="slate" testId="kpi-processing" />
        <StatCard label="Applications" value={data.applications.total} hint={`${data.applications.by_status.UNDER_REVIEW ?? 0} awaiting officer review`} icon={ClipboardList} />
        <StatCard label="Events" value={evTotal} hint={`DLQ depth: ${data.events.dead_letter_depth ?? "n/a"}`} icon={Radio} tone={data.events.by_status.DEAD_LETTERED ? "red" : "primary"} testId="kpi-events" />
        <StatCard
          label="Active consents"
          value={data.consents.by_status.ACTIVE ?? 0}
          hint={`${data.consents.by_status.REVOKED ?? 0} revoked · ${data.consents.access_denied} denied accesses`}
          icon={ShieldCheck}
          tone="green"
        />
        <StatCard label="Open data-quality issues" value={data.data_quality.open_total} hint="Conflicts, duplicates, stale records" icon={AlertTriangle} tone="amber" />
      </div>

      <section className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Connected systems</h2>
          <Link href="/admin/connectors" className="text-sm font-medium text-primary hover:underline">
            Manage connectors
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
          {cards.map((c) => (
            <ConnectorHealthCard key={c.key} c={c} />
          ))}
        </div>
      </section>

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <ChartCard title="Applications by department" description="Approved, rejected and in-progress">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.applications.by_department} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="department" tick={AXIS} tickFormatter={(v: string) => v.replace(" Department", "")} />
              <YAxis allowDecimals={false} tick={AXIS} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="approved" stackId="a" fill="var(--chart-3)" name="Approved / resolved" />
              <Bar dataKey="pending" stackId="a" fill="var(--chart-1)" name="In progress" />
              <Bar dataKey="rejected" stackId="a" fill="var(--chart-4)" name="Rejected" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Applications submitted" description="Last 14 days">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data.applications.trend} margin={{ left: -20 }}>
              <defs>
                <linearGradient id="appsFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--chart-1)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="var(--chart-1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="date" tick={AXIS} tickFormatter={(v: string) => v.slice(5)} />
              <YAxis allowDecimals={false} tick={AXIS} />
              <Tooltip />
              <Area type="monotone" dataKey="applications" stroke="var(--chart-1)" fill="url(#appsFill)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Connector calls (last hour)" description="Successful vs failed calls per department system">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.recent_connector_calls} margin={{ left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="connector" tick={AXIS} />
              <YAxis allowDecimals={false} tick={AXIS} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="success" fill="var(--chart-3)" name="Success" radius={[4, 4, 0, 0]} />
              <Bar dataKey="failure" fill="var(--chart-4)" name="Failure" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
        <ChartCard title="Workflow instances by state">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={workflowData} layout="vertical" margin={{ left: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" allowDecimals={false} tick={AXIS} />
              <YAxis type="category" dataKey="status" tick={AXIS} width={110} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--chart-2)" radius={[0, 4, 4, 0]} name="Instances" />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between text-base">
              Recent audit activity
              <Link href="/admin/audit-logs" className="text-sm font-medium text-primary hover:underline">
                Open audit log
              </Link>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>When</TableHead>
                  <TableHead>Actor</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.recent_audit.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell className="text-xs whitespace-nowrap text-muted-foreground">{timeAgo(a.timestamp)}</TableCell>
                    <TableCell className="text-xs">{a.actor}</TableCell>
                    <TableCell className="max-w-56 truncate font-mono text-[11px]">{a.action}</TableCell>
                    <TableCell>
                      <StatusBadge status={a.status} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Events &amp; applications by status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.events.by_status).map(([s, n]) => (
                <span key={s} className="flex items-center gap-1.5">
                  <StatusBadge status={s} /> <span className="text-sm font-semibold tabular-nums">{n}</span>
                </span>
              ))}
            </div>
            <ul className="space-y-1.5">
              {statusData.map((s) => (
                <li key={s.status} className="flex items-center justify-between text-sm">
                  <span>{s.status}</span>
                  <span className={cn("font-semibold tabular-nums")}>{s.count}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      
    </>
  )
}
