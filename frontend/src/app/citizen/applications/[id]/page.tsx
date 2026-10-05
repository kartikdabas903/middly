"use client"

import { ArrowLeft, CheckCircle2, MessageSquareReply, RefreshCw, RotateCcw, TriangleAlert, Undo2, XCircle } from "lucide-react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { useState } from "react"
import { toast } from "sonner"

import { ConsentRequestCard } from "@/components/application/consent-request"
import { DataQualityPanel, EligibilityPanel, HistoryList, ProfilePanel, SourcesPanel } from "@/components/application/panels"
import { TimelineProgress, WorkflowTimeline } from "@/components/application/timeline"
import { ErrorState, KeyValue, LoadingBlock, PageHeader, Spinner } from "@/components/common/page"
import { StatusBadge } from "@/components/common/status"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { formatDateTime, formatDuration, humanize } from "@/lib/format"
import { useApplication, useApplicationAction } from "@/lib/hooks"
import { cn } from "@/lib/utils"

export default function CitizenApplicationPage() {
  const { id } = useParams<{ id: string }>()
  const { data: app, isLoading, error, refetch, isFetching } = useApplication(id)
  const action = useApplicationAction(id)
  const [response, setResponse] = useState("")
  const [withdrawOpen, setWithdrawOpen] = useState(false)

  if (isLoading) return <LoadingBlock rows={4} />
  if (error || !app) return <ErrorState error={error ?? new Error("Not found")} />

  const blocked = app.sources.find((s) => s.state === "UNAVAILABLE")
  const openClarification = app.clarifications.find((c) => !c.response)

  return (
    <>
      <Link href="/citizen/applications" className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" /> All applications
      </Link>
      <PageHeader
        eyebrow={app.department}
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span className="font-mono" data-testid="application-number">{app.application_number}</span>
            <StatusBadge status={app.status} className="text-sm" />
          </span>
        }
        description={app.service}
        actions={
          <>
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
              <RefreshCw className={cn("size-4", isFetching && "animate-spin")} /> Refresh
            </Button>
            {app.permissions.can_sync && (
              <Button variant="outline" onClick={() => action.mutate({ action: "sync" })} disabled={action.isPending}>
                <RotateCcw className="size-4" /> Sync status from department
              </Button>
            )}
            {app.permissions.can_withdraw && (
              <Dialog open={withdrawOpen} onOpenChange={setWithdrawOpen}>
                <DialogTrigger render={<Button variant="ghost" className="text-destructive" />}>
                  <Undo2 className="size-4" /> Withdraw
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Withdraw {app.application_number}?</DialogTitle>
                    <DialogDescription>The application will be closed and any consent bound to it will be revoked.</DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <Button
                      variant="destructive"
                      onClick={() => action.mutate({ action: "withdraw", body: { reason: "Withdrawn by citizen" } }, { onSuccess: () => setWithdrawOpen(false) })}
                    >
                      Withdraw application
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            )}
          </>
        }
      />

      {/* State-specific call-outs */}
      <div className="mb-6 space-y-4">
        {app.status === "APPROVED" && (
          <Alert className="border-emerald-300 bg-success-soft" data-testid="approved-banner">
            <CheckCircle2 className="size-4 text-emerald-700" />
            <AlertTitle className="text-emerald-900">Application {app.application_number} approved.</AlertTitle>
            <AlertDescription className="text-emerald-900/80">
              Decided by {app.decided_by} on {formatDateTime(app.decided_at)}. {app.decision_reason}
            </AlertDescription>
          </Alert>
        )}
        {app.status === "RESOLVED" && (
          <Alert className="border-emerald-300 bg-success-soft">
            <CheckCircle2 className="size-4 text-emerald-700" />
            <AlertTitle className="text-emerald-900">Resolved by the department</AlertTitle>
            <AlertDescription className="text-emerald-900/80">{app.decision_reason}</AlertDescription>
          </Alert>
        )}
        {app.status === "REJECTED" && (
          <Alert variant="destructive" data-testid="rejected-banner">
            <XCircle className="size-4" />
            <AlertTitle>Application not approved</AlertTitle>
            <AlertDescription>
              {app.decision_reason}
              {app.decided_by === "SYSTEM" && " This decision was made automatically from department records using the scheme’s eligibility rules."}
            </AlertDescription>
          </Alert>
        )}
        {blocked && (
          <Card className="border-amber-300 bg-warning-soft" data-testid="source-unavailable">
            <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-start gap-3">
                <TriangleAlert className="mt-0.5 size-5 shrink-0 text-amber-700" />
                <div>
                  <p className="font-semibold text-amber-950">
                    {blocked.system} <span className="font-normal">● Temporarily unavailable</span>
                  </p>
                  <p className="text-sm text-amber-900/80">
                    Your application is safe and waiting (workflow state <code className="font-mono">WAITING_FOR_SOURCE</code>). The platform retries
                    automatically, or you can retry now.
                  </p>
                </div>
              </div>
              <Button onClick={() => action.mutate({ action: "retry" })} disabled={action.isPending} data-testid="retry-button" className="shrink-0">
                {action.isPending ? <Spinner /> : <RotateCcw className="size-4" />} Retry now
              </Button>
            </CardContent>
          </Card>
        )}
        {app.permissions.can_grant_consent && app.consent_request && (
          <ConsentRequestCard
            request={app.consent_request}
            pending={action.isPending}
            onAllow={async (cats) => {
              action.mutate(
                { action: "consent", body: { application_id: app.id, data_categories: cats } },
                { onSuccess: () => action.mutate({ action: "process" }) },
              )
            }}
          />
        )}
        {app.permissions.can_respond && openClarification && (
          <Card className="border-amber-300">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquareReply className="size-4 text-amber-700" /> The officer needs a clarification
              </CardTitle>
              <CardDescription>
                “{openClarification.question}” — {openClarification.asked_by}, {formatDateTime(openClarification.asked_at)}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea value={response} onChange={(e) => setResponse(e.target.value)} placeholder="Type your response" rows={3} maxLength={2000} />
              <Button
                disabled={response.trim().length < 2 || action.isPending}
                onClick={() => action.mutate({ action: "clarification-response", body: { response } }, { onSuccess: () => toast.success("Response sent to officer") })}
              >
                Send response
              </Button>
            </CardContent>
          </Card>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Application timeline</CardTitle>
              <CardDescription>
                <TimelineProgress steps={app.timeline} />
              </CardDescription>
            </CardHeader>
            <CardContent>
              <WorkflowTimeline steps={app.timeline} />
            </CardContent>
          </Card>
          <Card size="sm">
            <CardContent>
              <dl className="grid grid-cols-2 gap-4">
                <KeyValue label="Submitted">{formatDateTime(app.submitted_at)}</KeyValue>
                <KeyValue label="Last updated">{formatDateTime(app.updated_at)}</KeyValue>
                <KeyValue label="Current step">{app.current_step_label ?? "—"}</KeyValue>
                <KeyValue label="Department reference">{app.department_reference ?? "—"}</KeyValue>
                <KeyValue label="Expected next action" className="col-span-2">
                  {app.expected_next_action}
                </KeyValue>
                {app.processing_seconds !== null && <KeyValue label="Processing time">{formatDuration(app.processing_seconds)}</KeyValue>}
              </dl>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="verification">
          <TabsList>
            <TabsTrigger value="verification">Verification</TabsTrigger>
            <TabsTrigger value="data">My data</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>
          <TabsContent value="verification" className="mt-4 space-y-6">
            {app.sources.length > 0 && <SourcesPanel sources={app.sources} quality={app.data_quality_report} />}
            <EligibilityPanel result={app.eligibility} />
            <DataQualityPanel report={app.data_quality_report} />
            {app.sources.length === 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Submitted details</CardTitle>
                </CardHeader>
                <CardContent>
                  <dl className="grid gap-4 sm:grid-cols-2">
                    {Object.entries(app.form_data).map(([k, v]) => (
                      <KeyValue key={k} label={humanize(k)}>
                        {String(v)}
                      </KeyValue>
                    ))}
                  </dl>
                </CardContent>
              </Card>
            )}
          </TabsContent>
          <TabsContent value="data" className="mt-4 space-y-6">
            <ProfilePanel profile={app.profile} title="Data used for this application" />
            <Card>
              <CardHeader>
                <CardTitle>Your inputs</CardTitle>
              </CardHeader>
              <CardContent>
                <dl className="grid gap-4 sm:grid-cols-3">
                  {Object.entries(app.form_data).map(([k, v]) => (
                    <KeyValue key={k} label={humanize(k)}>
                      {humanize(String(v))}
                    </KeyValue>
                  ))}
                </dl>
              </CardContent>
            </Card>
            {app.consent && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    Consent <StatusBadge status={app.consent.status} />
                  </CardTitle>
                  <CardDescription>
                    {app.consent.requesting_department} · {app.consent.data_categories.map(humanize).join(", ")} · expires {formatDateTime(app.consent.expiry)}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Link href="/citizen/consents" className={buttonVariants({ variant: "outline" })}>
                    Manage consents
                  </Link>
                </CardContent>
              </Card>
            )}
          </TabsContent>
          <TabsContent value="history" className="mt-4">
            <Card>
              <CardHeader>
                <CardTitle>Status history</CardTitle>
              </CardHeader>
              <CardContent>
                <HistoryList history={app.history} />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </>
  )
}
