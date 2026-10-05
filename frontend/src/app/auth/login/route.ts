import { cookies } from "next/headers"
import { NextResponse, type NextRequest } from "next/server"

import { serverConfig } from "@/lib/server/config"
import { authorizeUrl, pkceChallenge, randomToken } from "@/lib/server/oidc"
import { COOKIE, seal } from "@/lib/server/session"

function safeReturnTo(value: string | null): string {
  // Only allow same-site relative paths (prevents open redirects).
  if (!value || !value.startsWith("/") || value.startsWith("//")) return ""
  return value
}

export async function GET(request: NextRequest) {
  const state = randomToken()
  const nonce = randomToken()
  const verifier = randomToken(48)
  const returnTo = safeReturnTo(request.nextUrl.searchParams.get("returnTo"))
  const loginHint = request.nextUrl.searchParams.get("hint")?.slice(0, 60) || undefined

  const jar = await cookies()
  jar.set(COOKIE.oidc, await seal({ state, nonce, verifier, returnTo }, 600), {
    httpOnly: true,
    secure: serverConfig.secureCookies,
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  })
  return NextResponse.redirect(authorizeUrl({ state, nonce, challenge: await pkceChallenge(verifier), loginHint }))
}
