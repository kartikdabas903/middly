"use client"

import { useMutation } from "@tanstack/react-query"
import { CheckCircle2, CircleDashed, Info, Loader2, TriangleAlert } from "lucide-react"
import { useParams, useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { ConsentRequestCard } from "@/components/application/consent-request"
import { ServiceForm } from "@/components/application/service-form"
import { ErrorState, LoadingBlock, PageHeader } from "@/components/common/page"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ApiError, api, errorMessage } from "@/lib/api"
import { useService } from "@/lib/hooks"
import type { ApplicationDetail } from "@/lib/types"
import { cn } from "@/lib/utils"

type Phase = "form" | "consent" | "processing" | "done"

const STAGES = [
  { key: "IDENTITY", label: "Contacting Identity Service" },
  { key: "EDUCATION", label: "Contacting Education Registry" },
  { key: "EMPLOYMENT", label: "Contacting Employment Registry" },
  { key: "VALIDATION", label: "Normalising responses & running data-quality checks" },
  { key: "ELIGIBILITY", label: "Evaluating eligibility" },
]

function ProcessingView({ result }: { result: ApplicationDetail | null }) {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setTick((v) => v + 1), 650)
    return () => clearInterval(t)
  }, [])

  const stateOf = (key: string, idx: number): "done" | "running" | "waiting" | "blocked" => {
    if (result) {
      const src = result.sources.find((s) => s.category === key)
      if (src) return src.state === "UNAVAILABLE" ? "blocked" : src.state === "PENDING" ? "waiting" : "done"
      const step = result.timeline.find((s) => (key === "VALIDATION" ? s.type === "validation" : s.type === "eligibility"))
      return step?.state === "done" ? "done" : "waiting"
    }
    if (idx < tick % (STAGES.length + 1)) return "done"
    return idx === tick % (STAGES.length + 1) ? "running" : "waiting"
  }

  return (
    <Card className="border-2 border-primary/20" data-testid="processing">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {!result && <Loader2 className="size-5 animate-spin text-primary" />}
          {result ? "Verification finished" : "Verifying your details with departments…"}
        </CardTitle>
        <CardDescription>The platform is calling each department system through its connector, with your consent.</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {STAGES.map((s, i) => {
            const st = stateOf(s.key, i)
            return (
              <li key={s.key} className="flex items-center gap-3 text-sm">
                {st === "done" && <CheckCircle2 className="size-5 text-emerald-600" />}
                {st === "running" && <Loader2 className="size-5 animate-spin text-primary" />}
                {st === "waiting" && <CircleDashed className="size-5 text-slate-300" />}
                {st === "blocked" && <TriangleAlert className="size-5 text-amber-600" />}
                <span className={cn(st === "waiting" && "text-muted-foreground", st === "blocked" && "font-semibold text-amber-800")}>
                  {s.label}
                  {st === "blocked" && " — temporarily unavailable"}
                </span>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}

export default function ApplyPage() {
  const { code } = useParams<{ code: string }>()
  const router = useRouter()
  const { data: service, isLoading, error } = useService(code)
  const [phase, setPhase] = useState<Phase>("form")
  const [app, setApp] = useState<ApplicationDetail | null>(null)
  const [result, setResult] = useState<ApplicationDetail | null>(null)

  const create = useMutation({
    mutationFn: (form: Record<string, string>) => api.post<ApplicationDetail>("applications", { service_code: code, form_data: form }),
    onSuccess: (created) => {
      setApp(created)
      if (created.permissions.can_grant_consent && created.consent_request) {
        setPhase("consent")
      } else {
        toast.success(`${created.application_number} submitted`)
        router.push(`/citizen/applications/${created.id}`)
      }
    },
    onError: (err) => {
      if (err instanceof ApiError && err.code === "CONFLICT" && (err.details as { application_id?: string })?.application_id) {
        toast.error(err.message, {
          action: { label: "Open", onClick: () => router.push(`/citizen/applications/${(err.details as { application_id: string }).application_id}`) },
        })
      } else {
        toast.error(errorMessage(err))
      }
    },
  })

  const consentAndProcess = useMutation({
    mutationFn: async (categories: string[]) => {
      if (!app) throw new Error("No application")
      await api.post("consents", { application_id: app.id, data_categories: categories })
      setPhase("processing")
      const [processed] = await Promise.all([
        api.post<ApplicationDetail>(`applications/${app.id}/process`),
        new Promise((r) => setTimeout(r, 2200)), // let citizens see the verification steps
      ])
      return processed
    },
    onSuccess: (processed) => {
      setResult(processed)
      setTimeout(() => router.push(`/citizen/applications/${processed.id}`), 1600)
    },
    onError: (err) => {
      toast.error(errorMessage(err))
      if (app) router.push(`/citizen/applications/${app.id}`)
    },
  })

  const decline = useMutation({
    mutationFn: () => api.post(`applications/${app!.id}/withdraw`, { reason: "Consent declined by citizen" }),
    onSuccess: () => {
      toast.info("Consent declined — the application was withdrawn and no data was shared.")
      router.push("/citizen/applications")
    },
    onError: (err) => toast.error(errorMessage(err)),
  })

  if (isLoading) return <LoadingBlock />
  if (error || !service) return <ErrorState error={error ?? new Error("Service not found")} />

  return (
    <>
      <PageHeader
        eyebrow={service.department}
        title={
          <span className="flex flex-wrap items-center gap-2">
           {service.name}
          </span>
        }
        description={service.description}
      />
      <ol className="mb-6 flex flex-wrap items-center gap-2 text-xs font-medium" aria-label="Progress">
        {(service.required_categories.length ? ["Details", "Consent", "Verification"] : ["Details"]).map((label, i) => {
          const active = (["form", "consent", "processing"] as Phase[]).indexOf(phase) >= i
          return (
            <li key={label} className={cn("flex items-center gap-2 rounded-full px-3 py-1", active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground")}>
              <span className="font-mono">{i + 1}</span> {label}
            </li>
          )
        })}
      </ol>

      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div>
          {phase === "form" && (
            <Card>
              <CardHeader>
                <CardTitle>Application details</CardTitle>
                <CardDescription>Only information specific to this service is needed.</CardDescription>
              </CardHeader>
              <CardContent>
                <ServiceForm
                  fields={service.form_schema.fields}
                  submitting={create.isPending}
                  submitLabel={service.required_categories.length ? "Continue" : "Submit"}
                  onSubmit={(values) => create.mutate(values)}
                />
              </CardContent>
            </Card>
          )}
          {phase === "consent" && app?.consent_request && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Application <span className="font-mono font-semibold text-foreground">{app.application_number}</span> created. Before any data is
                fetched, please review the request below.
              </p>
              <ConsentRequestCard
                request={app.consent_request}
                pending={consentAndProcess.isPending || decline.isPending}
                onAllow={(cats) => consentAndProcess.mutate(cats)}
                onDecline={() => decline.mutate()}
              />
            </div>
          )}
          {(phase === "processing" || phase === "done") && <ProcessingView result={result} />}
        </div>
        <aside className="space-y-4">
          <Card size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Info className="size-4 text-primary" /> What happens next
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              {service.required_categories.length ? (
                <>
                  <p>1. You review and grant consent for the listed data.</p>
                  <p>2. Middly fetches records from each department and normalises them.</p>
                  <p>3. Data-quality and eligibility checks run automatically.</p>
                  <p>4. Eligible applications go to a department officer for review.</p>
                </>
              ) : (
                <p>Your request is registered in the department&apos;s own system and tracked here alongside your other applications.</p>
              )}
            </CardContent>
          </Card>
          {service.eligibility && (
            <Card size="sm">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-sm">
                  Eligibility criteria
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
                  {service.eligibility.rules.map((r) => (
                    <li key={r.id}>{r.description}</li>
                  ))}
                </ul>
                {service.eligibility.disclaimer && <p className="mt-2 text-[11px] text-muted-foreground">{service.eligibility.disclaimer}</p>}
              </CardContent>
            </Card>
          )}
        </aside>
      </div>
    </>
  )
}
