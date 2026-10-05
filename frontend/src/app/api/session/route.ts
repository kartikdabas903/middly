import { NextResponse } from "next/server"

import { serverConfig } from "@/lib/server/config"
import { getSessionUser } from "@/lib/server/session"

export const dynamic = "force-dynamic"

export async function GET() {
  const user = await getSessionUser()
  return NextResponse.json(
    {
      user,
      links: serverConfig.links,
      environment: { sandbox: serverConfig.sandbox },
    },
    { headers: { "Cache-Control": "no-store" } },
  )
}
