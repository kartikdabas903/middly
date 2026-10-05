"use client"

import { ErrorState, LoadingBlock, PageHeader } from "@/components/common/page"
import { ServiceCard } from "@/components/common/service-card"
import { useServices } from "@/lib/hooks"

export default function ApplyIndexPage() {
  const { data, isLoading, error } = useServices()
  return (
    <>
      <PageHeader
        eyebrow="Services"
        title="Apply for a service"
        description="Only scheme-specific details are asked. Identity, education and employment records are fetched from departments with your consent."
      />
      {isLoading && <LoadingBlock rows={2} />}
      {error && <ErrorState error={error} />}
      <div className="grid gap-5 md:grid-cols-2">{data?.map((s) => <ServiceCard key={s.code} service={s} />)}</div>
    </>
  )
}
