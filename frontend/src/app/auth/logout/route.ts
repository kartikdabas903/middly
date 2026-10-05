import { NextResponse } from "next/server"

import { endSessionUrl } from "@/lib/server/oidc"
import { clearSession, readTokens } from "@/lib/server/session"

export async function GET() {
  const { idToken } = await readTokens()
  await clearSession()
  return NextResponse.redirect(endSessionUrl(idToken))
}
