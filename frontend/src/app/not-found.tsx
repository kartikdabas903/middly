import Link from "next/link"

import { LogoMark } from "@/components/layout/brand"
import { buttonVariants } from "@/components/ui/button"

export default function NotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-4 px-4 py-24 text-center">
      <LogoMark className="size-10" />
      <p className="font-mono text-sm text-muted-foreground">404</p>
      <h1 className="text-2xl font-semibold tracking-tight">We couldn&apos;t find that page</h1>
      <p className="max-w-md text-muted-foreground">The link may be broken or the page may have moved.</p>
      <Link href="/" className={buttonVariants({ size: "lg" })}>
        Back to home
      </Link>
    </main>
  )
}
