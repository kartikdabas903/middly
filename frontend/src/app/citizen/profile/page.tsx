"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { RefreshCw } from "lucide-react"
import { toast } from "sonner"

import { ProfilePanel } from "@/components/application/panels"
import { ErrorState, LoadingBlock, PageHeader, Spinner } from "@/components/common/page"
import { StatusBadge } from "@/components/common/status"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { api, errorMessage } from "@/lib/api"
import { formatDateTime, humanize } from "@/lib/format"
import { useMyProfile } from "@/lib/hooks"
import type { CitizenProfile, Profile } from "@/lib/types"

export default function MyRecordsPage() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useMyProfile()
  const refresh = useMutation({
    mutationFn: () => api.post<CitizenProfile>("citizens/me/profile/refresh"),
    onSuccess: (d) => {
      qc.setQueryData(["profile", "me"], d)
      const down = Object.keys(d.unavailable_sources ?? {})
      if (down.length) toast.warning(`Some systems were unavailable: ${down.join(", ")}`)
      else toast.success("Records refreshed from all departments")
    },
    onError: (e) => toast.error(errorMessage(e)),
  })

  if (isLoading) return <LoadingBlock rows={3} />
  if (error || !data) return <ErrorState error={error} />

  const profile: Profile = {
    citizen_id: data.citizen_id,
    full_name: data.full_name ?? undefined,
    date_of_birth: data.date_of_birth ?? undefined,
    gender: data.gender ?? undefined,
    mobile: data.mobile ?? undefined,
    email: data.email ?? undefined,
    address: data.address ?? undefined,
    district: data.district ?? undefined,
    state: data.state ?? undefined,
    pincode: data.pincode ?? undefined,
    education: data.education ?? undefined,
    employment_status: data.employment_status ?? undefined,
    provenance: data.provenance ?? {},
  }

  return (
    <>
      <PageHeader
        eyebrow={`Citizen ID ${data.citizen_id}`}
        title="My records across departments"
        description="Your consolidated profile, built from the records each department already holds. You can view it any time; departments need your consent."
        actions={
          <Button size="lg" onClick={() => refresh.mutate()} disabled={refresh.isPending} data-testid="refresh-profile">
            {refresh.isPending ? <Spinner /> : <RefreshCw className="size-4" />} Refresh from departments
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <ProfilePanel profile={data.full_name ? profile : null} title="Consolidated profile" hiddenReason="Click ‘Refresh from departments’ to load your records." />
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Source status <StatusBadge status={data.quality_status} className="ml-auto" />
              </CardTitle>
              <CardDescription>Last synchronised {formatDateTime(data.last_synced_at)}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {Object.entries(data.sources).map(([system, s]) => (
                <div key={system} className="flex items-start justify-between gap-2 rounded-lg border bg-white p-2.5">
                  <div>
                    <p className="text-sm font-medium">{system}</p>
                    {s.reason && <p className="text-xs text-muted-foreground">{s.reason}</p>}
                  </div>
                  <StatusBadge status={s.status} />
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Data-quality findings</CardTitle>
              <CardDescription>Differences between department records. Contact the department to correct a source record.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.open_issues.length === 0 && <p className="text-sm text-muted-foreground">No open issues.</p>}
              {data.open_issues.map((i) => (
                <div key={i.id} className="text-sm">
                  <div className="flex items-center gap-2">
                    <StatusBadge status={i.severity} />
                    <span className="font-medium">{humanize(i.issue_type)}</span>
                  </div>
                  <p className="text-muted-foreground">{i.message}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
