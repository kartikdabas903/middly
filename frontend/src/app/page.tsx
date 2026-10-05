import {
  ArrowRight,
  Bell,
  Cable,
  CheckCircle2,
  CircleDot,
  FileCheck2,
  Fingerprint,
  GitBranch,
  KeyRound,
  Layers,
  Lock,
  Radio,
  ScrollText,
  ShieldCheck,
  Workflow,
} from "lucide-react"
import Link from "next/link"

import { PublicFooter, PublicHeader } from "@/components/layout/public-header"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const FEATURES = [
  { icon: Cable, title: "Connectors, not migrations", text: "Each department system plugs in through a standard connector. Existing portals, registries and databases stay exactly where they are." },
  { icon: ShieldCheck, title: "Consent built in", text: "Citizens see who wants which data and why, approve it explicitly, and can revoke it at any time. Every access is logged." },
  { icon: Layers, title: "One citizen profile", text: "Different field names, formats and identifiers are normalised into a single profile — with the source of every field." },
  { icon: FileCheck2, title: "Data quality checks", text: "Conflicting names or dates, duplicates, missing fields and stale records are flagged before an officer ever sees them." },
  { icon: Workflow, title: "Configurable workflows", text: "Verification, eligibility rules and officer review run as versioned workflows. Every step is recorded and resumable." },
  { icon: Radio, title: "Event-driven updates", text: "Decisions flow back to department systems and to citizens as notifications — reliably, even when a system is briefly offline." },
]

const STEPS = [
  { title: "Apply once", text: "The citizen fills only what is specific to the service." },
  { title: "Approve sharing", text: "Purpose-bound, time-bound consent for each data category." },
  { title: "Verified automatically", text: "Records are fetched, normalised, checked and evaluated." },
  { title: "Decided and notified", text: "Officers review a consolidated file; everyone sees one timeline." },
]

const SECURITY = [
  { icon: KeyRound, title: "Single sign-on", text: "OpenID Connect with role-based access for citizens, officers and administrators." },
  { icon: Lock, title: "Least-privilege data access", text: "Departments only see data a citizen has consented to, for the stated purpose." },
  { icon: ScrollText, title: "Tamper-evident audit", text: "An append-only, hash-chained record of every access and decision." },
  { icon: Fingerprint, title: "Traceable requests", text: "Each request carries a correlation ID across gateway, services and connectors." },
]

function ProductPreview() {
  const steps = [
    { label: "Application submitted", done: true },
    { label: "Consent granted", done: true },
    { label: "Identity verified", done: true, meta: "Identity Service" },
    { label: "Education verified", done: true, meta: "Education Registry" },
    { label: "Employment verified", done: true, meta: "Employment Registry" },
    { label: "Eligibility checked", done: true },
    { label: "Officer review", current: true },
    { label: "Decision" },
  ]
  return (
    <div className="surface relative overflow-hidden p-0 shadow-xl shadow-slate-900/5">
      <div className="flex items-center gap-1.5 border-b bg-muted/50 px-4 py-2.5">
        <span className="size-2.5 rounded-full bg-slate-300" />
        <span className="size-2.5 rounded-full bg-slate-300" />
        <span className="size-2.5 rounded-full bg-slate-300" />
        <span className="ml-3 text-xs text-muted-foreground">Application APP-2026-0042</span>
      </div>
      <div className="grid gap-0 sm:grid-cols-[1fr_1.1fr]">
        <div className="border-b p-5 sm:border-r sm:border-b-0">
          <p className="text-xs font-medium text-muted-foreground">Skill Development Training Scheme</p>
          <p className="mt-1 flex items-center gap-2 text-sm font-semibold">
            Under officer review
            <span className="rounded-full bg-info-soft px-2 py-0.5 text-[11px] font-medium text-blue-700">In progress</span>
          </p>
          <ol className="mt-4 space-y-2.5">
            {steps.map((s) => (
              <li key={s.label} className="flex items-center gap-2.5 text-[13px]">
                {s.done ? (
                  <CheckCircle2 className="size-4 text-emerald-600" />
                ) : s.current ? (
                  <CircleDot className="size-4 text-primary" />
                ) : (
                  <span className="size-4 rounded-full border-2 border-slate-200" />
                )}
                <span className={cn(!s.done && !s.current && "text-muted-foreground", s.current && "font-medium")}>{s.label}</span>
                {s.meta && <span className="ml-auto text-[11px] text-muted-foreground">{s.meta}</span>}
              </li>
            ))}
          </ol>
        </div>
        <div className="space-y-3 p-5">
          <p className="text-xs font-medium text-muted-foreground">Consolidated profile</p>
          {[
            ["Full name", "Rahul Sharma", "Identity"],
            ["Date of birth", "14 Mar 2002", "Identity"],
            ["Highest qualification", "B.Tech · 2024", "Education"],
            ["Employment status", "Job seeker", "Employment"],
          ].map(([k, v, src]) => (
            <div key={k} className="flex items-start justify-between gap-3 border-b pb-2.5 last:border-0">
              <div>
                <p className="text-[11px] text-muted-foreground">{k}</p>
                <p className="text-[13px] font-medium">{v}</p>
              </div>
              <span className="rounded-md bg-accent px-1.5 py-0.5 text-[10px] font-medium text-accent-foreground">{src}</span>
            </div>
          ))}
          <div className="flex items-center gap-2 rounded-lg bg-success-soft px-3 py-2 text-[12px] text-emerald-800">
            <ShieldCheck className="size-3.5" /> Consent active · 3 categories · 180 days
          </div>
        </div>
      </div>
    </div>
  )
}

export default function HomePage() {
  return (
    <>
      <PublicHeader />
      <main className="flex-1">
        <section className="relative overflow-hidden border-b">
          <div className="bg-dots absolute inset-0 [mask-image:linear-gradient(to_bottom,black,transparent)]" aria-hidden />
          <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_1.15fr] lg:py-24">
            <div className="space-y-6">
              <span className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground">
                <GitBranch className="size-3.5 text-primary" /> Interoperability for public services
              </span>
              <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl sm:leading-[1.08]">
                Every department.
                <br />
                One application.
              </h1>
              <p className="max-w-lg text-lg leading-relaxed text-muted-foreground">
                Middly connects the systems departments already run, so citizens stop re-submitting the same documents — and officers
                decide on verified, consolidated records.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "h-11 px-5 text-[15px]")}>
                  Get started <ArrowRight className="size-4" />
                </Link>
                <Link href="/about" className={cn(buttonVariants({ variant: "outline", size: "lg" }), "h-11 bg-card px-5 text-[15px]")}>
                  See how it works
                </Link>
              </div>
              <dl className="grid max-w-md grid-cols-3 gap-6 pt-4">
                {[
                  ["0", "documents to upload"],
                  ["3", "registries checked"],
                  ["1", "timeline to follow"],
                ].map(([v, l]) => (
                  <div key={l}>
                    <dt className="text-2xl font-semibold tracking-tight">{v}</dt>
                    <dd className="text-xs text-muted-foreground">{l}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <ProductPreview />
          </div>
        </section>

        <section className="border-b bg-card">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-4 py-6 text-sm text-muted-foreground sm:px-6">
            <span className="font-medium text-foreground">Connects to</span>
            {["Identity services", "Education registries", "Employment exchanges", "Skill development systems", "Grievance portals"].map((s) => (
              <span key={s}>{s}</span>
            ))}
          </div>
        </section>

        <section id="platform" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-medium text-primary">Platform</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">A shared layer between citizens and departments</h2>
            <p className="mt-3 text-muted-foreground">
              Departments keep their systems. Middly handles identity, consent, data normalisation, workflows and notifications in one place.
            </p>
          </div>
          <div className="mt-12 grid gap-px overflow-hidden rounded-xl border bg-border sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="bg-card p-6">
                <f.icon className="size-5 text-primary" />
                <p className="mt-4 font-semibold">{f.title}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{f.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="border-y bg-card">
          <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6">
            <p className="text-sm font-medium text-primary">How it works</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">From application to decision</h2>
            <ol className="mt-12 grid gap-8 md:grid-cols-4">
              {STEPS.map((s, i) => (
                <li key={s.title} className="relative">
                  <span className="flex size-8 items-center justify-center rounded-full border bg-background text-sm font-semibold">{i + 1}</span>
                  {i < STEPS.length - 1 && <span className="absolute top-4 left-10 hidden h-px w-[calc(100%-2.5rem)] bg-border md:block" aria-hidden />}
                  <p className="mt-4 font-semibold">{s.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{s.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="security" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 sm:px-6">
          <div className="grid gap-12 lg:grid-cols-[1fr_1.4fr]">
            <div>
              <p className="text-sm font-medium text-primary">Security & trust</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight">Built for sensitive public data</h2>
              <p className="mt-3 text-muted-foreground">
                Access is authenticated, authorised, consented and recorded — and department records are never edited by the platform.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              {SECURITY.map((s) => (
                <div key={s.title} className="surface p-5">
                  <s.icon className="size-5 text-primary" />
                  <p className="mt-3 font-semibold">{s.title}</p>
                  <p className="mt-1 text-sm text-muted-foreground">{s.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
          <div className="flex flex-col items-start justify-between gap-6 rounded-2xl bg-foreground px-8 py-10 text-background md:flex-row md:items-center">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight">Ready to apply or review?</h2>
              <p className="mt-1 text-background/70">Sign in as a citizen, a department officer or an administrator.</p>
            </div>
            <div className="flex gap-3">
              <Link href="/login" className={cn(buttonVariants({ size: "lg" }), "h-11 bg-background px-5 text-foreground hover:bg-background/90")}>
                Sign in <ArrowRight className="size-4" />
              </Link>
              <Link href="/services" className={cn(buttonVariants({ variant: "ghost", size: "lg" }), "h-11 px-5 text-background hover:bg-white/10 hover:text-background")}>
                <Bell className="size-4" /> Browse services
              </Link>
            </div>
          </div>
        </section>
      </main>
      <PublicFooter />
    </>
  )
}
