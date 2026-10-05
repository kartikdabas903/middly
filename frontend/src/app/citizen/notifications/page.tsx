"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Bell, CheckCheck, CheckCircle2, Info, XCircle } from "lucide-react"
import Link from "next/link"

import { EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/common/page"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api"
import { formatDateTime, timeAgo } from "@/lib/format"
import { useNotifications } from "@/lib/hooks"
import { cn } from "@/lib/utils"

const ICONS = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info }
const TONE = { success: "text-emerald-600", error: "text-red-600", warning: "text-amber-600", info: "text-primary" }

export default function NotificationsPage() {
  const qc = useQueryClient()
  const { data, isLoading, error } = useNotifications()
  const markAll = useMutation({
    mutationFn: () => api.post("notifications/read-all"),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  })
  const markOne = useMutation({
    mutationFn: (id: string) => api.post(`notifications/${id}/read`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  })

  return (
    <>
      <PageHeader
        eyebrow="Event-driven notifications"
        title="Notifications"
        description="Delivered by the notification service after consuming platform events from RabbitMQ."
        actions={
          <Button variant="outline" onClick={() => markAll.mutate()} disabled={!data?.unread}>
            <CheckCheck className="size-4" /> Mark all as read
          </Button>
        }
      />
      {isLoading && <LoadingBlock />}
      {error && <ErrorState error={error} />}
      {data && data.items.length === 0 && <EmptyState icon={Bell} title="No notifications yet" />}
      <ul className="space-y-2" data-testid="notifications">
        {data?.items.map((n) => {
          const Icon = ICONS[n.severity] ?? Info
          return (
            <li
              key={n.id}
              className={cn("flex gap-3 rounded-xl border bg-white p-4", !n.read && "border-primary/30 bg-secondary/40")}
              data-testid="notification"
            >
              <Icon className={cn("mt-0.5 size-5 shrink-0", TONE[n.severity])} />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">
                    {n.title} {!n.read && <span className="ml-1 rounded-full bg-primary px-1.5 py-px text-[10px] font-bold text-white">NEW</span>}
                  </p>
                  <time className="text-xs text-muted-foreground" title={formatDateTime(n.created_at)}>
                    {timeAgo(n.created_at)}
                  </time>
                </div>
                <p className="mt-0.5 text-sm text-foreground/80">{n.message}</p>
                <div className="mt-2 flex gap-3 text-xs">
                  {n.application_id && (
                    <Link href={`/citizen/applications/${n.application_id}`} className="font-medium text-primary hover:underline">
                      Open application
                    </Link>
                  )}
                  {!n.read && (
                    <button className="font-medium text-muted-foreground hover:text-foreground" onClick={() => markOne.mutate(n.id)}>
                      Mark as read
                    </button>
                  )}
                </div>
              </div>
            </li>
          )
        })}
      </ul>
    </>
  )
}
