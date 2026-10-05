import { redirect } from "next/navigation"

import { AppShell } from "@/components/layout/app-shell"
import { serverConfig } from "@/lib/server/config"
import { getSessionUser } from "@/lib/server/session"

export default async function AdminLayout({ children }: LayoutProps<"/admin">) {
  const user = await getSessionUser()
  if (!user) redirect("/login?returnTo=/admin/dashboard")
  return (
    <AppShell area="admin" user={user} sandbox={serverConfig.sandbox}>
      {children}
    </AppShell>
  )
}
