import Link from "next/link"

import { Brand, LogoMark } from "@/components/layout/brand"
import { buttonVariants } from "@/components/ui/button"
import { homeFor } from "@/lib/roles"
import { getSessionUser } from "@/lib/server/session"
import { cn } from "@/lib/utils"

const NAV = [
  { href: "/#platform", label: "Platform" },
  { href: "/services", label: "Services" },
  { href: "/about", label: "How it works" },
  { href: "/#security", label: "Security" },
]

export async function PublicHeader() {
  const user = await getSessionUser()
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <Brand />
        </div>
        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href} className="rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <Link href={homeFor(user.roles)} className={cn(buttonVariants(), "h-9 px-4")}>
              Go to dashboard
            </Link>
          ) : (
            <>
              <Link href="/login" className={cn(buttonVariants({ variant: "ghost" }), "hidden h-9 px-3 sm:inline-flex")}>
                Sign in
              </Link>
              <Link href="/login" className={cn(buttonVariants(), "h-9 px-4")}>
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

const FOOTER = [
  { title: "Product", links: [["Platform", "/#platform"], ["Services", "/services"], ["How it works", "/about"]] },
  { title: "Trust", links: [["Security", "/#security"], ["Consent & privacy", "/about#consent"], ["Data quality", "/about#data"]] },
  { title: "Access", links: [["Citizen sign in", "/login"], ["Department sign in", "/login"], ["Administrators", "/login"]] },
]

export function PublicFooter() {
  return (
    <footer className="mt-auto border-t bg-card">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="space-y-3">
          <div className="flex items-center gap-2.5">
            <LogoMark className="size-7" />
            <span className="font-semibold tracking-tight">Middly</span>
          </div>
          <p className="max-w-xs text-sm text-muted-foreground">
            The interoperability layer for public services. Connect existing department systems — apply once, share with consent, track everything.
          </p>
        </div>
        {FOOTER.map((col) => (
          <div key={col.title} className="space-y-3 text-sm">
            <p className="font-medium">{col.title}</p>
            <ul className="space-y-2">
              {col.links.map(([label, href]) => (
                <li key={label}>
                  <Link href={href} className="text-muted-foreground hover:text-foreground">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-5 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>© {new Date().getFullYear()} Middly</p>
        </div>
      </div>
    </footer>
  )
}
