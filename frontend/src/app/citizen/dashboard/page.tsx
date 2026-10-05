"use client"

import { ArrowRight, Bell, CheckCircle2, ClipboardList, ShieldCheck } from "lucide-react"
import Link from "next/link"

import { ApplicationsTable } from "@/components/application/applications-table"
import { EmptyState, ErrorState, LoadingBlock, PageHeader, StatCard } from "@/components/common/page"
import { StatusBadge } from "@/components/common/status"
import { buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { WorkflowTimeline } from "@/components/application/timeline"
import { timeAgo } from "@/lib/format"
import { useApplication, useApplications, useConsents, useNotifications } from "@/lib/hooks"
import { cn } from "@/lib/utils"

function LatestApplication({ id }: { id: string }) {
  const { data } = useApplication(id)
  if (!data) return <LoadingBlock rows={2} />
  return (
    <Card>
      <CardHeader>
        <CardDescription>Latest application</CardDescription>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span className="font-mono">{data.application_number}</span>
          <StatusBadge status={data.status} />
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          {data.department} · {data.service}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <WorkflowTimeline steps={data.timeline} compact />
        <Link href={`/citizen/applications/${data.id}`} className={cn(buttonVariants({ variant: "outline" }), "w-full")}>
          View full timeline <ArrowRight className="size-4" />
        </Link>
      </CardContent>
    </Card>
  )
}

export default function CitizenDashboard() {
  const apps = useApplications({ limit: 50 }, 8000)
  const consents = useConsents()
  const notes = useNotifications()

  const items = apps.data?.items ?? []
  const active = items.filter((a) => !["APPROVED", "REJECTED", "RESOLVED", "WITHDRAWN"].includes(a.status)).length
  const approved = items.filter((a) => a.status === "APPROVED" || a.status === "RESOLVED").length
  const activeConsents = consents.data?.items.filter((c) => c.status === "ACTIVE").length ?? 0

  return (
    <>
      <PageHeader
        eyebrow="Unified application tracking"
        title="Welcome back"
        description="All your applications and grievances across departments, in one place."
        actions={
          <Link href="/citizen/apply" className={cn(buttonVariants({ size: "lg" }), "px-4")} data-testid="new-application">
            Apply for a service <ArrowRight className="size-4" />
          </Link>
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active applications" value={active} icon={ClipboardList} />
        <StatCard label="Approved / resolved" value={approved} icon={CheckCircle2} tone="green" />
        <StatCard label="Active consents" value={activeConsents} icon={ShieldCheck} tone="slate" hint="Revocable at any time" />
        <StatCard label="Unread notifications" value={notes.data?.unread ?? 0} icon={Bell} tone="amber" />
      </div>

      {apps.error && <ErrorState error={apps.error} />}
      {apps.isLoading ? (
        <LoadingBlock />
      ) : items.length === 0 ? (
        <EmptyState
          title="No applications yet"
          description="Apply for the Skill Development Training Scheme — your details are fetched from departments with your consent."
          action={
            <Link href="/citizen/apply" className={buttonVariants()}>
              Browse services
            </Link>
          }
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">My applications</h2>
            <ApplicationsTable items={items} hrefBase="/citizen/applications" />
          </div>
          <div className="space-y-6">
            <LatestApplication id={items[0].id} />
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent notifications</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {(notes.data?.items ?? []).slice(0, 4).map((n) => (
                  <div key={n.id} className="text-sm">
                    <p className={cn("font-medium", !n.read && "text-primary")}>{n.title}</p>
                    <p className="line-clamp-2 text-muted-foreground">{n.message}</p>
                    <p className="text-xs text-muted-foreground">{timeAgo(n.created_at)}</p>
                  </div>
                ))}
                {(notes.data?.items.length ?? 0) === 0 && <p className="text-sm text-muted-foreground">No notifications yet.</p>}
                <Link href="/citizen/notifications" className="text-sm font-medium text-primary hover:underline">
                  View all
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </>
  )
}
