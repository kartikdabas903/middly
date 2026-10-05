"use client"

import { useQuery } from "@tanstack/react-query"
import { ArrowLeft, CheckCircle2, Lock, MessageCircleQuestion, XCircle } from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useState } from "react"
import { toast } from "sonner"

import { DataQualityPanel, EligibilityPanel, HistoryList, ProfilePanel, SourcesPanel } from "@/components/application/panels"
import { TimelineProgress, WorkflowTimeline } from "@/components/application/timeline"
import { ErrorState, KeyValue, LoadingBlock, PageHeader, Spinner } from "@/components/common/page"
import { StatusBadge } from "@/components/common/status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { api } from "@/lib/api"
import { formatDateTime, formatDuration, humanize } from "@/lib/format"
import { useApplication, useApplicationAction } from "@/lib/hooks"
import type { AuditEntry } from "@/lib/types"

type Decision = "approve" | "reject" | "request-clarification"

const DECISION_COPY: Record<Decision, { title: string; label: string; field: string; required: boolean; variant: "default" | "destructive" | "outline" }> = {
  approve: { title: "Approve application", label: "Approve", field: "Remarks (optional)", required: false, variant: "default" },
  reject: { title: "Reject application", label: "Reject", field: "Reason for rejection (shared with the citizen)", required: true, variant: "destructive" },
  "request-clarification": { title: "Request clarification", label: "Send request", field: "Question for the citizen", required: true, variant: "outline" },
}

function DecisionDialog({ id, kind, onDone }: { id: string; kind: Decision; onDone?: () => void }) {
  const copy = DECISION_COPY[kind]
  const [open, setOpen] = useState(false)
  const [text, setText] = useState("")
  const action = useApplicationAction(id)
  const Icon = kind === "approve" ? CheckCircle2 : kind === "reject" ? XCircle : MessageCircleQuestion
  const submit = () => {
    const body = kind === "request-clarification" ? { question: text } : { remarks: text || undefined }
    action.mutate(
      { action: kind, body },
      {
        onSuccess: () => {
          setOpen(false)
          setText("")
          toast.success(kind === "approve" ? "Application approved — APPLICATION_APPROVED event published" : kind === "reject" ? "Application rejected" : "Clarification requested")
          onDone?.()
        },
      },
    )
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant={copy.variant} size="lg" className="w-full justify-start" data-testid={`officer-${kind}`} />}>
        <Icon className="size-4" /> {copy.label === "Send request" ? "Request clarification" : copy.label}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{copy.title}</DialogTitle>
          <DialogDescription>
            Your decision is recorded in the platform and forwarded to the department system. Source registry records are not modified.
          </DialogDescription>
        </DialogHeader>
        <label className="space-y-1.5 text-sm font-medium">
          {copy.field}
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} maxLength={1000} data-testid="decision-text" />
        </label>
        <DialogFooter>
          <Button variant={copy.variant === "outline" ? "default" : copy.variant} onClick={submit} disabled={action.isPending || (copy.required && text.trim().length < 5)} data-testid="confirm-decision">
            {action.isPending && <Spinner />} {copy.label}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function AuditTab({ id }: { id: string }) {
  const audit = useQuery({ queryKey: ["application-audit", id], queryFn: () => api.get<{ items: AuditEntry[] }>(`applications/${id}/audit-logs`) })
  const access = useQuery({
    queryKey: ["application-access", id],
    queryFn: () => api.get<{ accessed_at: string; data_category: string; accessor: string; purpose: string; connector: string; decision: string }[]>(`applications/${id}/consent-access-logs`),
  })
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Audit trail</CardTitle>
          <CardDescription>Append-only, hash-chained records of every action on this application.</CardDescription>
        </CardHeader>
        <CardContent>
          {audit.isLoading ? (
            <LoadingBlock rows={2} />
          ) : (
            <div className="max-h-[420px] overflow-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Systems</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {audit.data?.items.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="text-xs whitespace-nowrap">{formatDateTime(a.timestamp)}</TableCell>
                      <TableCell className="text-xs">
                        {a.actor}
                        <span className="block text-muted-foreground">{humanize(a.role)}</span>
                      </TableCell>
                      <TableCell className="font-mono text-[11px]">{a.action}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {[a.source_system, a.destination_system].filter(Boolean).join(" → ") || "—"}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={a.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Consent-checked data access</CardTitle>
          <CardDescription>Each read of citizen data verified an active consent first.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-h-80 overflow-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Accessor</TableHead>
                  <TableHead>Decision</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(access.data ?? []).map((l, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs whitespace-nowrap">{formatDateTime(l.accessed_at)}</TableCell>
                    <TableCell className="text-xs">{humanize(l.data_category)}</TableCell>
                    <TableCell className="text-xs">
                      {l.accessor}
                      <span className="block text-muted-foreground">{l.purpose}</span>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={l.decision} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default function OfficerApplicationPage() {
  const { id } = useParams<{ id: string }>()
  const { data: app, isLoading, error } = useApplication(id)

  if (isLoading) return <LoadingBlock rows={4} />
  if (error || !app) return <ErrorState error={error ?? new Error("Not found")} />

  return (
    <>
      <Link href="/officer/applications" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" /> Applications queue
      </Link>
      <PageHeader
        eyebrow={`${app.department} · ${app.service}`}
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span className="font-mono" data-testid="application-number">{app.application_number}</span>
            <StatusBadge status={app.status} className="text-sm" />
          </span>
        }
        description={`Applicant: ${app.applicant_name ?? "—"} · Citizen ID ${app.citizen_id} · submitted ${formatDateTime(app.submitted_at)}`}
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_320px]">
        <Tabs defaultValue="overview" className="min-w-0">
          <TabsList>
            <TabsTrigger value="overview">Consolidated profile</TabsTrigger>
            <TabsTrigger value="verification">Verification</TabsTrigger>
            <TabsTrigger value="workflow">Workflow</TabsTrigger>
            <TabsTrigger value="audit">Audit</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="mt-4 space-y-6">
            <ProfilePanel profile={app.profile} hiddenReason={app.profile_hidden_reason} />
            <Card>
              <CardHeader>
                <CardTitle>Applicant&apos;s choices</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-4 sm:grid-cols-3">
                  {Object.entries(app.form_data).map(([k, v]) => (
                    <KeyValue key={k} label={humanize(k)}>
                      {k === "description" || k === "subject" ? String(v) : humanize(String(v))}
                    </KeyValue>
                  ))}
                </dl>
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="verification" className="mt-4 space-y-6">
            <SourcesPanel sources={app.sources} quality={app.data_quality_report} />
            <EligibilityPanel result={app.eligibility} />
            <DataQualityPanel report={app.data_quality_report} />
          </TabsContent>
          <TabsContent value="workflow" className="mt-4 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Workflow</CardTitle>
                <CardDescription>
                  {app.workflow.definition} v{app.workflow.version} · <StatusBadge status={app.workflow.status} />
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <TimelineProgress steps={app.timeline} />
                <WorkflowTimeline steps={app.timeline} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Workflow history</CardTitle>
              </CardHeader>
              <CardContent>
                <HistoryList history={app.history} />
              </CardContent>
            </Card>
          </TabsContent>
          <TabsContent value="audit" className="mt-4">
            <AuditTab id={app.id} />
          </TabsContent>
        </Tabs>

        <aside className="space-y-4">
          <Card className="border-primary/30">
            <CardHeader>
              <CardTitle>Decision</CardTitle>
              <CardDescription>{app.permissions.can_decide ? "This application is awaiting your review." : app.decision ? "Decision recorded." : "No action needed at this stage."}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {app.permissions.can_decide ? (
                <>
                  <DecisionDialog id={app.id} kind="approve" />
                  <DecisionDialog id={app.id} kind="request-clarification" />
                  <DecisionDialog id={app.id} kind="reject" />
                </>
              ) : app.decision ? (
                <div className="space-y-1 text-sm">
                  <StatusBadge status={app.status} />
                  <p className="text-muted-foreground">
                    {app.decided_by} · {formatDateTime(app.decided_at)}
                  </p>
                  {app.decision_reason && <p>{app.decision_reason}</p>}
                  {app.processing_seconds !== null && <p className="text-xs text-muted-foreground">Processing time: {formatDuration(app.processing_seconds)}</p>}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No action available in the current state.</p>
              )}
            </CardContent>
          </Card>
          {app.clarifications.length > 0 && (
            <Card size="sm">
              <CardHeader>
                <CardTitle className="text-sm">Clarifications</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {app.clarifications.map((c, i) => (
                  <div key={i} className="space-y-1">
                    <p>
                      <span className="font-medium">Q:</span> {c.question}
                    </p>
                    <p className={c.response ? "" : "text-muted-foreground italic"}>
                      <span className="font-medium not-italic">A:</span> {c.response ?? "Awaiting citizen response"}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
          <Alert>
            <Lock className="size-4" />
            <AlertTitle>Read-only source data</AlertTitle>
            <AlertDescription>
              Officers act through the platform. Department registry records cannot be edited from here; data is visible only while the citizen&apos;s
              consent is active.
            </AlertDescription>
          </Alert>
          <Card size="sm">
            <CardContent>
              <dl className="grid gap-3">
                <KeyValue label="Department reference">{app.department_reference ?? "—"}</KeyValue>
                <KeyValue label="Consent">
                  {app.consent ? (
                    <span className="flex items-center gap-2">
                      <StatusBadge status={app.consent.status} /> until {formatDateTime(app.consent.expiry)}
                    </span>
                  ) : (
                    "Not required"
                  )}
                </KeyValue>
                <KeyValue label="Data quality">{app.data_quality ? <StatusBadge status={app.data_quality} /> : "—"}</KeyValue>
              </dl>
            </CardContent>
          </Card>
        </aside>
      </div>
    </>
  )
}
