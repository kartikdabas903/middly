import { redirect } from "next/navigation"

import { AppShell } from "@/components/layout/app-shell"
import { serverConfig } from "@/lib/server/config"
import { getSessionUser } from "@/lib/server/session"

export default async function OfficerLayout({ children }: LayoutProps<"/officer">) {
  const user = await getSessionUser()
  if (!user) redirect("/login?returnTo=/officer/dashboard")
  return (
    <AppShell area="officer" user={user} sandbox={serverConfig.sandbox}>
      {children}
    </AppShell>
  )
}
