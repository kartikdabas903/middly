import type { Metadata } from "next"

import { ErrorState } from "@/components/common/page"
import { ServiceCard } from "@/components/common/service-card"
import { PublicFooter, PublicHeader } from "@/components/layout/public-header"
import { fetchServices } from "@/lib/server/public-api"

export const metadata: Metadata = { title: "Services" }
export const dynamic = "force-dynamic"

export default async function ServicesPage() {
  const services = await fetchServices()
  return (
    <>
      <PublicHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-16 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-primary">Services</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Services available on Middly</h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Information departments already hold is fetched with your consent, so you only enter what is specific to the service.
          </p>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-2">
          {services ? services.map((s) => <ServiceCard key={s.code} service={s} />) : <ErrorState error={new Error("Services are temporarily unavailable. Please try again shortly.")} />}
        </div>
      </main>
      <PublicFooter />
    </>
  )
}
