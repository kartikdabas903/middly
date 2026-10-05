"use client"

import Link from "next/link"

import { ApplicationsTable } from "@/components/application/applications-table"
import { EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/common/page"
import { buttonVariants } from "@/components/ui/button"
import { useApplications } from "@/lib/hooks"

export default function CitizenApplicationsPage() {
  const { data, isLoading, error } = useApplications({ limit: 100 }, 8000)
  return (
    <>
      <PageHeader
        eyebrow="Unified tracking"
        title="My applications"
        description="Applications and grievances across every connected department."
        actions={
          <Link href="/citizen/apply" className={buttonVariants({ size: "lg" })}>
            New application
          </Link>
        }
      />
      {isLoading && <LoadingBlock />}
      {error && <ErrorState error={error} />}
      {data && (data.items.length ? <ApplicationsTable items={data.items} hrefBase="/citizen/applications" /> : <EmptyState title="No applications yet" />)}
    </>
  )
}
