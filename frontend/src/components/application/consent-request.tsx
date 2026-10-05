"use client"

import { Building2, CalendarClock, Lock, ShieldCheck, Target } from "lucide-react"
import { useState } from "react"

import { Spinner } from "@/components/common/page"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { CATEGORY_INFO } from "@/lib/format"

export interface ConsentRequestInfo {
  department: string
  categories: string[]
  purpose: string
  validity_days: number
}

export function ConsentRequestCard({
  request,
  onAllow,
  onDecline,
  pending,
}: {
  request: ConsentRequestInfo
  onAllow: (categories: string[]) => void
  onDecline?: () => void
  pending?: boolean
}) {
  const [allowed, setAllowed] = useState<Record<string, boolean>>(() => Object.fromEntries(request.categories.map((c) => [c, true])))
  const allAllowed = request.categories.every((c) => allowed[c])

  return (
    <Card className="border-2 border-primary/25 shadow-md" data-testid="consent-request">
      <CardHeader>
        <span className="mb-1 flex size-10 items-center justify-center rounded-full bg-primary/10">
          <Lock className="size-5 text-primary" />
        </span>
        <CardTitle className="text-xl">Your consent is required</CardTitle>
        <CardDescription className="text-base text-foreground/80">
          Allow <strong>{request.department}</strong> to access your{" "}
          {request.categories.map((c, i) => (
            <span key={c}>
              {i > 0 && (i === request.categories.length - 1 ? " and " : ", ")}
              {(CATEGORY_INFO[c]?.label ?? c).replace(" Information", "").toLowerCase()}
            </span>
          ))}{" "}
          information?
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 text-sm sm:grid-cols-3">
          <p className="flex items-start gap-2">
            <Building2 className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <span>
              <span className="block text-xs text-muted-foreground">Requesting department</span>
              {request.department}
            </span>
          </p>
          <p className="flex items-start gap-2 sm:col-span-2">
            <Target className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <span>
              <span className="block text-xs text-muted-foreground">Purpose</span>
              {request.purpose}
            </span>
          </p>
          <p className="flex items-start gap-2">
            <CalendarClock className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
            <span>
              <span className="block text-xs text-muted-foreground">Valid for</span>
              {request.validity_days} days · revocable anytime
            </span>
          </p>
        </div>
        <ul className="divide-y rounded-lg border bg-white">
          {request.categories.map((c) => {
            const info = CATEGORY_INFO[c]
            return (
              <li key={c} className="flex items-center justify-between gap-4 p-3">
                <div className="min-w-0">
                  <p className="font-semibold">{info?.label ?? c}</p>
                  <p className="text-xs text-muted-foreground">
                    {info?.description} · from <span className="font-medium text-foreground">{info?.source}</span>
                  </p>
                </div>
                <label className="flex shrink-0 items-center gap-2 text-sm font-semibold">
                  <span className={allowed[c] ? "text-emerald-700" : "text-muted-foreground"}>{allowed[c] ? "Allowed" : "Not allowed"}</span>
                  <Switch
                    checked={allowed[c]}
                    onCheckedChange={(v) => setAllowed((s) => ({ ...s, [c]: Boolean(v) }))}
                    aria-label={`Allow ${info?.label ?? c}`}
                    data-testid={`consent-toggle-${c}`}
                  />
                </label>
              </li>
            )
          })}
        </ul>
        {!allAllowed && (
          <p className="rounded-md bg-warning-soft p-2 text-xs text-amber-900">
            All listed categories are required to verify eligibility for this service. Without them the application cannot proceed.
          </p>
        )}
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="size-3.5" /> Every access is logged and visible to you under Consents. The department never edits your source records.
        </p>
      </CardContent>
      <CardFooter className="flex flex-wrap justify-end gap-2">
        {onDecline && (
          <Button variant="outline" size="lg" onClick={onDecline} disabled={pending}>
            Decline
          </Button>
        )}
        <Button
          size="lg"
          className="px-4"
          disabled={!allAllowed || pending}
          onClick={() => onAllow(request.categories.filter((c) => allowed[c]))}
          data-testid="consent-allow"
        >
          {pending && <Spinner />} Allow &amp; continue
        </Button>
      </CardFooter>
    </Card>
  )
}
