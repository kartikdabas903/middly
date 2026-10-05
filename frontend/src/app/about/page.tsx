import type { Metadata } from "next"

import { PublicFooter, PublicHeader } from "@/components/layout/public-header"

export const metadata: Metadata = { title: "How it works" }

const SECTIONS = [
  {
    id: "problem",
    title: "Why departments need an interoperability layer",
    body: [
      "Departments run independent portals, registries and workflow systems, each with its own data formats, identifiers, authentication and APIs.",
      "Citizens end up re-submitting the same documents to every department, applications stall between systems, and nobody has a single view of where a request stands.",
    ],
  },
  {
    id: "connectors",
    title: "Connect, don't replace",
    body: [
      "Middly sits between existing systems. Each department integrates through a connector that implements one standard interface: authenticate, health check, fetch a citizen record, fetch or submit an application, transform the response and handle errors.",
      "The core platform never depends on a department's internals, so a new department is onboarded by adding a connector — not by changing the platform.",
    ],
  },
  {
    id: "consent",
    title: "Consent first",
    body: [
      "Before any department reads a citizen's data, the citizen sees who is asking, for which categories, for what purpose and for how long — and explicitly allows it.",
      "Every access is checked against an active consent and logged. Citizens can review the access history and revoke consent at any time; access stops immediately.",
    ],
  },
  {
    id: "data",
    title: "One profile, with its sources",
    body: [
      "One registry says fullName, another student_name, a third candidateName — with different date formats, state codes and status codes.",
      "Middly maps every response into a single citizen profile, validates each field, records which system it came from, and flags conflicts, duplicates and stale records for review.",
    ],
  },
  {
    id: "workflow",
    title: "Workflows that survive outages",
    body: [
      "Verification, eligibility rules and officer review run as versioned workflows with every step recorded. If a department system is unavailable, the application waits safely and resumes automatically — completed steps are never repeated.",
      "Decisions are published as events, delivered to citizens as notifications and synchronised back to the department's own system.",
    ],
  },
  {
    id: "security",
    title: "Security and accountability",
    body: [
      "Sign-in uses OpenID Connect with role-based access. Tokens stay on the server, every request is traceable end to end, and an append-only, hash-chained audit trail records each access and decision.",
      "Operations teams monitor API traffic, connector health and processing times on live dashboards.",
    ],
  },
]

export default function AboutPage() {
  return (
    <>
      <PublicHeader />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-16 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-primary">How it works</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">The interoperability layer for public services</h1>
          <p className="mt-4 text-lg text-muted-foreground">
            How Middly links existing department systems into one consent-based, traceable service for citizens and officers.
          </p>
        </div>
        <div className="mt-14 grid gap-12 lg:grid-cols-[220px_1fr]">
          <nav aria-label="On this page" className="hidden lg:block">
            <ul className="sticky top-24 space-y-2 border-l text-sm">
              {SECTIONS.map((s) => (
                <li key={s.id}>
                  <a href={`#${s.id}`} className="-ml-px block border-l border-transparent pl-4 text-muted-foreground hover:border-foreground hover:text-foreground">
                    {s.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="max-w-2xl space-y-12">
            {SECTIONS.map((s) => (
              <section key={s.id} id={s.id} className="scroll-mt-24">
                <h2 className="text-xl font-semibold tracking-tight">{s.title}</h2>
                <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-foreground/80">
                  {s.body.map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </div>
      </main>
      <PublicFooter />
    </>
  )
}
