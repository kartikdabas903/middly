"use client"

import { DemoScenarios } from "@/components/admin/demo-controls"
import { ErrorState, LoadingBlock, PageHeader } from "@/components/common/page"
import { useConnectors, useSession } from "@/lib/hooks"

export default function SandboxPage() {
  const connectors = useConnectors()
  const session = useSession()
  const canControl = (session.data?.user?.roles.includes("PLATFORM_ADMIN") ?? false) && (session.data?.environment.sandbox ?? false)

  return (
    <>
      <PageHeader
        eyebrow="Environment"
        title="Sandbox tools"
        description="Walkthroughs, outage simulation and data reset for this sandbox environment. Not available in production."
      />
      {connectors.isLoading && <LoadingBlock rows={3} />}
      {connectors.error && <ErrorState error={connectors.error} />}
      {connectors.data && <DemoScenarios connectors={connectors.data} canControl={canControl} />}
    </>
  )
}
