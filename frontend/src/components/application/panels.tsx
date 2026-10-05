import { BadgeCheck, CircleCheck, CircleX, Database, GraduationCap, IdCard, Info, Briefcase, ShieldAlert } from "lucide-react"

import { KeyValue, Tag } from "@/components/common/page"
import { HealthDot, StatusBadge } from "@/components/common/status"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ageFrom, formatDate, formatDateTime, humanize } from "@/lib/format"
import type { EligibilityResult, Profile, QualityReport, SourceState } from "@/lib/types"
import { cn } from "@/lib/utils"

const CATEGORY_ICON: Record<string, typeof IdCard> = { IDENTITY: IdCard, EDUCATION: GraduationCap, EMPLOYMENT: Briefcase }

export function SourcesPanel({ sources, quality }: { sources: SourceState[]; quality?: QualityReport | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Database className="size-4 text-primary" /> Data sources
        </CardTitle>
        <CardDescription>Records retrieved from department systems through platform connectors</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2.5">
        {sources.length === 0 && <p className="text-sm text-muted-foreground">This service does not pull data from other departments.</p>}
        {sources.map((s) => {
          const Icon = CATEGORY_ICON[s.category] ?? Database
          const dq = quality?.sources?.[s.system]
          const shown = s.state === "VERIFIED" && dq ? dq.status : s.state
          return (
            <div
              key={s.step}
              data-testid={`source-${s.category.toLowerCase()}`}
              data-state={s.state}
              className={cn(
                "flex items-start gap-3 rounded-lg border p-3",
                s.state === "UNAVAILABLE" ? "border-amber-300 bg-warning-soft" : "bg-white",
              )}
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Icon className="size-4.5" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">{s.system}</p>
                  {s.state === "UNAVAILABLE" ? (
                    <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-amber-800">
                      <HealthDot status="DOWN" /> Temporarily unavailable
                    </span>
                  ) : (
                    <StatusBadge status={shown} />
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {humanize(s.category)} data
                  {s.fetched_at && ` · fetched ${formatDateTime(s.fetched_at)}`}
                  {s.attempts > 1 && ` · ${s.attempts} attempts`}
                </p>
                {dq?.reason && s.state === "VERIFIED" && dq.status !== "VERIFIED" && (
                  <p className="mt-1 text-xs font-medium text-amber-800">Reason: {dq.reason}</p>
                )}
                {s.state === "UNAVAILABLE" && s.error && <p className="mt-1 text-xs text-amber-900/80">{s.error}</p>}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

export function DataQualityPanel({ report }: { report: QualityReport | null }) {
  if (!report) return null
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="size-4 text-primary" /> Data quality
          <StatusBadge status={report.overall} className="ml-auto" />
        </CardTitle>
        <CardDescription>Automated checks across sources: completeness, formats, cross-system consistency, duplicates, staleness</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-3">
          {Object.entries(report.sources).map(([system, s]) => (
            <div key={system} className="rounded-lg border bg-white p-2.5" data-testid="dq-source">
              <p className="text-xs text-muted-foreground">{system}</p>
              <div className="mt-1 flex items-center justify-between gap-2">
                <StatusBadge status={s.status} />
              </div>
              {s.reason && <p className="mt-1 text-[11px] text-muted-foreground">{s.reason}</p>}
            </div>
          ))}
        </div>
        {report.issues.length > 0 ? (
          <ul className="space-y-1.5">
            {report.issues.map((i, idx) => (
              <li key={idx} className="flex items-start gap-2 text-sm">
                <StatusBadge status={i.severity} className="mt-0.5" />
                <span>
                  <span className="font-medium">{humanize(i.issue_type)}</span> — {i.message}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-2 text-sm text-emerald-700">
            <BadgeCheck className="size-4" /> All checks passed
          </p>
        )}
      </CardContent>
    </Card>
  )
}

export function EligibilityPanel({ result }: { result: EligibilityResult | null }) {
  if (!result) return null
  return (
    <Card data-testid="eligibility">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Eligibility
          <Tag>{result.ruleset}</Tag>
          <StatusBadge status={result.eligible ? "APPROVED" : "REJECTED"} label={result.eligible ? "Eligible" : "Not eligible"} className="ml-auto" />
        </CardTitle>
        <CardDescription>
          Evaluated on {formatDate(result.evaluated_on)} against the scheme’s configured rule set.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y rounded-lg border bg-white">
          {result.outcomes.map((o) => (
            <li key={o.id} className="flex items-start gap-3 p-3" data-rule={o.id} data-passed={o.passed}>
              {o.passed ? <CircleCheck className="mt-0.5 size-5 shrink-0 text-emerald-600" /> : <CircleX className="mt-0.5 size-5 shrink-0 text-red-600" />}
              <div className="min-w-0">
                <p className="text-sm font-semibold">
                  {o.description} <span className="font-mono text-[11px] font-normal text-muted-foreground">{o.id}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  {o.reason}
                  {o.actual !== null && o.actual !== undefined && ` · found: ${String(o.actual)}`}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}

function Source({ p }: { p?: { source: string } }) {
  if (!p) return null
  return <span className="ml-1.5 rounded bg-primary/8 px-1.5 py-px text-[10px] font-semibold text-primary ring-1 ring-primary/15">{p.source}</span>
}

export function ProfilePanel({ profile, hiddenReason, title = "Consolidated citizen profile" }: { profile: Profile | null; hiddenReason?: string | null; title?: string }) {
  if (!profile) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Info className="size-4" /> {hiddenReason ?? "Profile will appear once department data has been retrieved."}
          </p>
        </CardContent>
      </Card>
    )
  }
  const pv = profile.provenance ?? {}
  const age = ageFrom(profile.date_of_birth)
  return (
    <Card data-testid="profile">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>Normalised into the canonical model. Each field shows the system it came from (read-only — source records are never edited).</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
          <KeyValue label={<>Full name <Source p={pv.full_name} /></>}>{profile.full_name}</KeyValue>
          <KeyValue label={<>Date of birth <Source p={pv.date_of_birth} /></>}>
            {formatDate(profile.date_of_birth)} {age !== null && <span className="text-muted-foreground">({age} yrs)</span>}
          </KeyValue>
          <KeyValue label={<>Gender <Source p={pv.gender} /></>}>{humanize(profile.gender)}</KeyValue>
          <KeyValue label={<>Mobile <Source p={pv.mobile} /></>}>{profile.mobile ?? "—"}</KeyValue>
          <KeyValue label={<>Email <Source p={pv.email} /></>}>{profile.email ?? "—"}</KeyValue>
          <KeyValue label={<>Address <Source p={pv.address} /></>}>{profile.address ?? "—"}</KeyValue>
          <KeyValue label={<>District / State <Source p={pv.state} /></>}>
            {profile.district ?? "—"}, {profile.state ?? "—"} {profile.pincode && <span className="text-muted-foreground">– {profile.pincode}</span>}
          </KeyValue>
          <KeyValue label={<>Highest qualification <Source p={pv.education} /></>}>
            {profile.education ? (
              <>
                {profile.education.highest_qualification}
                {profile.education.stream && ` (${profile.education.stream})`}
                <span className="block text-xs font-normal text-muted-foreground">
                  {profile.education.institution} {profile.education.passing_year && `· ${profile.education.passing_year}`}
                </span>
              </>
            ) : (
              "—"
            )}
          </KeyValue>
          <KeyValue label={<>Employment status <Source p={pv.employment_status} /></>}>
            {humanize(profile.employment_status)}
            {profile.employment?.registration_id && (
              <span className="block text-xs font-normal text-muted-foreground">Reg. {profile.employment.registration_id}</span>
            )}
          </KeyValue>
        </dl>
        {profile.department_record && (
          <div className="mt-4 rounded-lg border border-emerald-200 bg-success-soft p-3 text-sm">
            <p className="font-semibold text-emerald-900">Department system record</p>
            <p className="text-emerald-900/80">
              {profile.department_record.reference} · {humanize(profile.department_record.status)}
              {profile.department_record.batch_code && ` · Batch ${profile.department_record.batch_code}`}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function HistoryList({ history }: { history: { to_status: string; note: string | null; actor: string; actor_role: string; at: string }[] }) {
  return (
    <ol className="space-y-3">
      {[...history].reverse().map((h, i) => (
        <li key={i} className="flex gap-3 text-sm">
          <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary/60" aria-hidden />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={h.to_status} />
              <span className="text-xs text-muted-foreground">
                {formatDateTime(h.at)} · {h.actor} ({humanize(h.actor_role)})
              </span>
            </div>
            {h.note && <p className="mt-0.5 text-muted-foreground">{h.note}</p>}
          </div>
        </li>
      ))}
    </ol>
  )
}
