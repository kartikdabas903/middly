import { redirect } from "next/navigation"

import { AppShell } from "@/components/layout/app-shell"
import { serverConfig } from "@/lib/server/config"
import { getSessionUser } from "@/lib/server/session"

export default async function CitizenLayout({ children }: LayoutProps<"/citizen">) {
  const user = await getSessionUser()
  if (!user) redirect("/login?returnTo=/citizen/dashboard")
  return (
    <AppShell area="citizen" user={user} sandbox={serverConfig.sandbox}>
      {children}
    </AppShell>
  )
}
