import { serverConfig } from "@/lib/server/config"
import type { ServiceInfo } from "@/lib/types"

/** Public (unauthenticated) catalogue, fetched server-side through the gateway. */
export async function fetchServices(): Promise<ServiceInfo[] | null> {
  try {
    const res = await fetch(`${serverConfig.apiBaseUrl}/services`, { cache: "no-store", signal: AbortSignal.timeout(8000) })
    if (!res.ok) return null
    return (await res.json()) as ServiceInfo[]
  } catch {
    return null
  }
}
