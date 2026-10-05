"use client"

import { ArrowRight, CheckCircle2, ClipboardCheck, Hourglass, MessageCircleQuestion, XCircle } from "lucide-react"
import Link from "next/link"

import { ApplicationsTable } from "@/components/application/applications-table"
import { EmptyState, ErrorState, LoadingBlock, PageHeader, StatCard } from "@/components/common/page"
import { buttonVariants } from "@/components/ui/button"
import { useApplications } from "@/lib/hooks"
import { cn } from "@/lib/utils"

export default function OfficerDashboard() {
  const { data, isLoading, error } = useApplications({ limit: 200 }, 8000)
  const items = data?.items ?? []
  const count = (s: string) => items.filter((a) => a.status === s).length
  const queue = items.filter((a) => a.status === "UNDER_REVIEW")

  return (
    <>
      <PageHeader
        eyebrow="Department workspace"
        title="Officer dashboard"
        description="Applications are verified against department registries before they reach you. Source records are read-only."
        actions={
          <Link href="/officer/applications" className={cn(buttonVariants({ size: "lg" }), "px-4")}>
            Open queue <ArrowRight className="size-4" />
          </Link>
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Awaiting review" value={count("UNDER_REVIEW")} icon={ClipboardCheck} testId="stat-review" />
        <StatCard label="Clarification asked" value={count("CLARIFICATION_REQUESTED")} icon={MessageCircleQuestion} tone="amber" />
        <StatCard label="Waiting for source" value={count("WAITING_FOR_SOURCE") + count("CONSENT_PENDING")} icon={Hourglass} tone="slate" />
        <StatCard label="Approved" value={count("APPROVED") + count("RESOLVED")} icon={CheckCircle2} tone="green" />
        <StatCard label="Rejected" value={count("REJECTED")} icon={XCircle} tone="red" />
      </div>
      <h2 className="mb-3 text-lg font-semibold">Review queue</h2>
      {isLoading && <LoadingBlock />}
      {error && <ErrorState error={error} />}
      {data &&
        (queue.length ? (
          <ApplicationsTable items={queue} hrefBase="/officer/applications" showApplicant />
        ) : (
          <EmptyState icon={ClipboardCheck} title="Queue is clear" description="New verified applications will appear here automatically." />
        ))}
    </>
  )
}
