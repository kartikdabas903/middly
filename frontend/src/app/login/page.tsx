import { ArrowRight, Building2, ChevronRight, ShieldCheck, UserRound } from "lucide-react"
import type { Metadata } from "next"
import Link from "next/link"

import { Brand } from "@/components/layout/brand"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { buttonVariants } from "@/components/ui/button"
import { serverConfig } from "@/lib/server/config"
import { cn } from "@/lib/utils"

export const metadata: Metadata = { title: "Sign in" }

const SANDBOX_ACCOUNTS = [
  { group: "Citizens", icon: UserRound, password: "Citizen@123", accounts: [
    { username: "citizen1", note: "Rahul Sharma · Pune" },
    { username: "citizen2", note: "Priya Deshmukh · Nagpur" },
    { username: "citizen3", note: "Amit Verma · Indore" },
  ] },
  { group: "Department officers", icon: Building2, password: "Officer@123", accounts: [
    { username: "officer1", note: "Skill Development Department" },
    { username: "officer2", note: "Public Grievance Cell" },
  ] },
  { group: "Administrators", icon: ShieldCheck, password: "Admin@123", accounts: [
    { username: "admin1", note: "Platform administrator" },
    { username: "deptadmin1", note: "Department admin · DeptAdmin@123" },
  ] },
]

const ERRORS: Record<string, string> = {
  session_expired: "Your session expired. Please sign in again.",
  invalid_state: "The sign-in request expired. Please try again.",
  token_exchange_failed: "We couldn't complete sign-in with the identity provider.",
  no_role: "Your account has not been granted access to Middly yet.",
  access_denied: "Sign-in was cancelled.",
}

export default async function LoginPage(props: PageProps<"/login">) {
  const params = await props.searchParams
  const error = typeof params.error === "string" ? params.error : undefined
  const returnTo = typeof params.returnTo === "string" && params.returnTo.startsWith("/") && !params.returnTo.startsWith("//") ? params.returnTo : ""
  const suffix = returnTo ? `returnTo=${encodeURIComponent(returnTo)}` : ""

  return (
    <main className="grid min-h-screen flex-1 lg:grid-cols-[1fr_1.05fr]">
      <section className="relative hidden overflow-hidden bg-foreground p-12 text-background lg:flex lg:flex-col">
        <div className="bg-dots absolute inset-0 opacity-40" aria-hidden />
        <div className="relative">
          <Brand className="[&_span]:text-background" />
        </div>
        <div className="relative mt-auto max-w-md space-y-6">
          <p className="text-3xl font-semibold leading-tight tracking-tight">Apply once. Share with consent. Track everything.</p>
          <ul className="space-y-3 text-sm text-background/70">
            {["Records fetched from departments — no uploads", "You decide who sees which data, and for how long", "One timeline across every department"].map((t) => (
              <li key={t} className="flex items-center gap-2.5">
                <ShieldCheck className="size-4 text-background/90" /> {t}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="flex flex-col px-6 py-10 sm:px-12">
        <div className="flex items-center justify-between lg:justify-end">
          <Brand className="lg:hidden" />
          <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
            Back to home
          </Link>
        </div>
        <div className="mx-auto my-auto w-full max-w-sm py-10">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">Sign in</h1>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">Citizens, department officers and administrators use the same secure sign-in.</p>
          {error && (
            <Alert variant="destructive" className="mt-6">
              <AlertTitle>Couldn&apos;t sign you in</AlertTitle>
              <AlertDescription>{ERRORS[error] ?? "Something went wrong. Please try again."}</AlertDescription>
            </Alert>
          )}
          <a href={`/auth/login${suffix ? `?${suffix}` : ""}`} className={cn(buttonVariants({ size: "lg" }), "mt-8 h-11 w-full text-[15px]")} data-testid="login-sso">
            Continue with Middly ID <ArrowRight className="size-4" />
          </a>
          <p className="mt-3 text-center text-xs text-muted-foreground">Secured with OpenID Connect. We never see your password.</p>

          {serverConfig.sandbox && (
            <details className="group mt-10 rounded-xl border bg-card" open>
              <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-sm font-medium">
                Sandbox accounts
                <ChevronRight className="size-4 text-muted-foreground transition group-open:rotate-90" />
              </summary>
              <div className="space-y-4 border-t px-4 py-4">
                {SANDBOX_ACCOUNTS.map((g) => (
                  <div key={g.group}>
                    <p className="mb-1.5 flex items-center justify-between text-xs font-medium text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <g.icon className="size-3.5" /> {g.group}
                      </span>
                      <code className="font-mono text-[11px]">{g.password}</code>
                    </p>
                    <div className="space-y-1">
                      {g.accounts.map((a) => (
                        <a
                          key={a.username}
                          href={`/auth/login?hint=${a.username}${suffix ? `&${suffix}` : ""}`}
                          className="group/acc flex items-center justify-between rounded-lg px-2.5 py-2 text-sm transition hover:bg-muted"
                          data-testid={`login-${a.username}`}
                        >
                          <span>
                            <span className="font-mono text-[13px] font-medium">{a.username}</span>
                            <span className="ml-2 text-xs text-muted-foreground">{a.note}</span>
                          </span>
                          <ChevronRight className="size-3.5 text-muted-foreground opacity-0 transition group-hover/acc:opacity-100" />
                        </a>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </section>
    </main>
  )
}
