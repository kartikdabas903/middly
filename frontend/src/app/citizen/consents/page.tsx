"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Eye, ShieldCheck, ShieldOff } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/common/page"
import { StatusBadge } from "@/components/common/status"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Textarea } from "@/components/ui/textarea"
import { api, errorMessage } from "@/lib/api"
import { CATEGORY_INFO, formatDateTime, humanize } from "@/lib/format"
import { useConsents } from "@/lib/hooks"
import type { Consent } from "@/lib/types"

function AccessLog({ consentId }: { consentId: string }) {
  const { data, isLoading } = useQuery({ queryKey: ["consent", consentId], queryFn: () => api.get<Consent>(`consents/${consentId}`) })
  if (isLoading) return <LoadingBlock rows={2} />
  const logs = data?.access_logs ?? []
  if (!logs.length) return <p className="text-sm text-muted-foreground">No data has been accessed under this consent yet.</p>
  return (
    <div className="max-h-96 overflow-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>When</TableHead>
            <TableHead>Data</TableHead>
            <TableHead>Accessed by</TableHead>
            <TableHead>Decision</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((l, i) => (
            <TableRow key={i}>
              <TableCell className="text-xs whitespace-nowrap">{formatDateTime(l.accessed_at)}</TableCell>
              <TableCell className="text-xs">
                {humanize(l.data_category)}
                {l.connector && <span className="block text-muted-foreground">via {l.connector} connector</span>}
              </TableCell>
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
  )
}

function ConsentCard({ consent }: { consent: Consent }) {
  const qc = useQueryClient()
  const [reason, setReason] = useState("")
  const [open, setOpen] = useState(false)
  const revoke = useMutation({
    mutationFn: () => api.post<Consent>(`consents/${consent.consent_id}/revoke`, { reason: reason || undefined }),
    onSuccess: () => {
      toast.success("Consent revoked. The department can no longer access your data.")
      setOpen(false)
      qc.invalidateQueries({ queryKey: ["consents"] })
      qc.invalidateQueries({ queryKey: ["application"] })
    },
    onError: (e) => toast.error(errorMessage(e)),
  })
  return (
    <Card data-testid="consent-card" data-status={consent.status}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle>{consent.requesting_department}</CardTitle>
            <CardDescription>{consent.application_number ? `For application ${consent.application_number}` : "General consent"}</CardDescription>
          </div>
          <StatusBadge status={consent.status} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex flex-wrap gap-1.5">
          {consent.data_categories.map((c) => (
            <span key={c} className="rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-secondary-foreground">
              {CATEGORY_INFO[c]?.label ?? c} · Allowed
            </span>
          ))}
        </div>
        <p className="text-muted-foreground">{consent.purpose}</p>
        <dl className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <dt className="text-muted-foreground">Granted</dt>
            <dd>{formatDateTime(consent.timestamp)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">{consent.status === "REVOKED" ? "Revoked" : "Expires"}</dt>
            <dd>{formatDateTime(consent.status === "REVOKED" ? consent.revoked_at : consent.expiry)}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-muted-foreground">Data accesses recorded</dt>
            <dd>{consent.access_count}</dd>
          </div>
          {consent.revocation_reason && (
            <div className="col-span-2">
              <dt className="text-muted-foreground">Reason</dt>
              <dd>{consent.revocation_reason}</dd>
            </div>
          )}
        </dl>
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        <Dialog>
          <DialogTrigger render={<Button variant="outline" />}>
            <Eye className="size-4" /> Access history
          </DialogTrigger>
          <DialogContent className="sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Who accessed your data</DialogTitle>
              <DialogDescription>Every access under this consent, including the connector used.</DialogDescription>
            </DialogHeader>
            <AccessLog consentId={consent.consent_id} />
          </DialogContent>
        </Dialog>
        {consent.status === "ACTIVE" && (
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger render={<Button variant="destructive" data-testid="revoke-consent" />}>
              <ShieldOff className="size-4" /> Revoke
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Revoke consent?</DialogTitle>
                <DialogDescription>
                  {consent.requesting_department} will immediately lose access to your {consent.data_categories.map((c) => humanize(c).toLowerCase()).join(", ")} data.
                  Pending applications that depend on it cannot be approved.
                </DialogDescription>
              </DialogHeader>
              <Textarea placeholder="Reason (optional)" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
              <DialogFooter>
                <Button variant="destructive" onClick={() => revoke.mutate()} disabled={revoke.isPending} data-testid="confirm-revoke">
                  Revoke consent
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        )}
      </CardFooter>
    </Card>
  )
}

export default function ConsentsPage() {
  const { data, isLoading, error } = useConsents()
  const items = data?.items ?? []
  const active = items.filter((c) => c.status === "ACTIVE")
  const history = items.filter((c) => c.status !== "ACTIVE")
  return (
    <>
      <PageHeader
        eyebrow="Privacy"
        title="Consent management"
        description="You decide which department can access which of your records, for what purpose and for how long."
      />
      {isLoading && <LoadingBlock />}
      {error && <ErrorState error={error} />}
      {data && (
        <div className="space-y-8">
          <section>
            <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold">
              <ShieldCheck className="size-5 text-emerald-600" /> Active consents ({active.length})
            </h2>
            {active.length ? (
              <div className="grid gap-4 md:grid-cols-2">{active.map((c) => <ConsentCard key={c.consent_id} consent={c} />)}</div>
            ) : (
              <EmptyState title="No active consents" description="Consents appear here when you allow a department to access your data for an application." />
            )}
          </section>
          <section>
            <h2 className="mb-3 text-lg font-semibold">Consent history ({history.length})</h2>
            {history.length ? (
              <div className="grid gap-4 md:grid-cols-2">{history.map((c) => <ConsentCard key={c.consent_id} consent={c} />)}</div>
            ) : (
              <p className="text-sm text-muted-foreground">No revoked or expired consents.</p>
            )}
          </section>
        </div>
      )}
    </>
  )
}
