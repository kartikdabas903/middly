"use client"

import { Search } from "lucide-react"
import { useState } from "react"

import { ApplicationsTable } from "@/components/application/applications-table"
import { EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/common/page"
import { Input } from "@/components/ui/input"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useApplications } from "@/lib/hooks"

const FILTERS: Record<string, string | undefined> = {
  review: "UNDER_REVIEW",
  clarification: "CLARIFICATION_REQUESTED",
  waiting: "WAITING_FOR_SOURCE,CONSENT_PENDING,PROCESSING,FORWARDED_TO_DEPARTMENT,IN_PROGRESS",
  decided: "APPROVED,REJECTED,RESOLVED,WITHDRAWN",
  all: undefined,
}

export default function OfficerQueuePage() {
  const [tab, setTab] = useState("review")
  const [q, setQ] = useState("")
  const { data, isLoading, error } = useApplications({ status: FILTERS[tab], q: q || undefined, limit: 200 }, 8000)

  return (
    <>
      <PageHeader eyebrow="Department workspace" title="Applications" description="Unified queue of applications submitted to your department through Middly." />
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <Tabs value={tab} onValueChange={(v) => setTab(String(v))}>
          <TabsList>
            <TabsTrigger value="review">Pending review</TabsTrigger>
            <TabsTrigger value="clarification">Clarification</TabsTrigger>
            <TabsTrigger value="waiting">In process</TabsTrigger>
            <TabsTrigger value="decided">Decided</TabsTrigger>
            <TabsTrigger value="all">All</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="relative w-full md:w-72">
          <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
          <Input className="h-9 pl-8" placeholder="Search application or citizen ID" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      {isLoading && <LoadingBlock />}
      {error && <ErrorState error={error} />}
      {data && (data.items.length ? <ApplicationsTable items={data.items} hrefBase="/officer/applications" showApplicant /> : <EmptyState title="No applications in this view" />)}
    </>
  )
}
