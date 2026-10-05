"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { api, errorMessage } from "@/lib/api"
import type { SessionUser } from "@/lib/roles"
import type {
  AdminOverview,
  ApplicationDetail,
  ApplicationSummary,
  CitizenProfile,
  Consent,
  ConnectorCard,
  NotificationItem,
  Page,
  ServiceInfo,
} from "@/lib/types"

const ACTIVE_STATES = new Set(["SUBMITTED", "PROCESSING", "WAITING_FOR_SOURCE", "FORWARDED_TO_DEPARTMENT", "IN_PROGRESS"])

export function useServices() {
  return useQuery({ queryKey: ["services"], queryFn: () => api.get<ServiceInfo[]>("services") })
}

export function useService(code: string) {
  return useQuery({ queryKey: ["services", code], queryFn: () => api.get<ServiceInfo>(`services/${code}`) })
}

export function useApplications(params: { status?: string; q?: string; limit?: number; offset?: number } = {}, refetchMs?: number) {
  return useQuery({
    queryKey: ["applications", params],
    queryFn: () => api.get<Page<ApplicationSummary>>("applications", params),
    refetchInterval: refetchMs,
  })
}

export function useApplication(id: string) {
  return useQuery({
    queryKey: ["application", id],
    queryFn: () => api.get<ApplicationDetail>(`applications/${id}`),
    // Keep polling while the platform or the event pipeline is still working.
    refetchInterval: (q) => {
      const d = q.state.data
      if (!d) return false
      if (ACTIVE_STATES.has(d.status) || d.workflow_status === "WAITING_FOR_EVENT" || d.workflow_status === "WAITING_FOR_EXTERNAL") return 3000
      return 15000
    },
  })
}

export function useApplicationAction(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ action, body }: { action: string; body?: unknown }) => api.post<ApplicationDetail>(`applications/${id}/${action}`, body),
    onSuccess: (data) => {
      qc.setQueryData(["application", id], data)
      qc.invalidateQueries({ queryKey: ["applications"] })
      qc.invalidateQueries({ queryKey: ["notifications"] })
    },
    onError: (err) => toast.error(errorMessage(err)),
  })
}

export function useConsents() {
  return useQuery({ queryKey: ["consents"], queryFn: () => api.get<Page<Consent>>("consents") })
}

export function useNotifications() {
  return useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => api.get<Page<NotificationItem> & { unread: number }>("notifications", { limit: 100 }),
    refetchInterval: 5000,
  })
}

export function useMyProfile() {
  return useQuery({ queryKey: ["profile", "me"], queryFn: () => api.get<CitizenProfile>("citizens/me/profile") })
}

export function useAdminOverview() {
  return useQuery({ queryKey: ["admin", "overview"], queryFn: () => api.get<AdminOverview>("admin/overview"), refetchInterval: 10000 })
}

export function useConnectors() {
  return useQuery({ queryKey: ["connectors"], queryFn: () => api.get<ConnectorCard[]>("connectors"), refetchInterval: 10000 })
}

export function useSession() {
  return useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      const res = await fetch("/api/session", { cache: "no-store" })
      return (await res.json()) as { user: SessionUser | null; links: Record<string, string>; environment: { sandbox: boolean } }
    },
    staleTime: Infinity,
  })
}
