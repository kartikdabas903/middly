import { cookies } from "next/headers"
import { NextResponse, type NextRequest } from "next/server"

import { homeFor } from "@/lib/roles"
import { serverConfig } from "@/lib/server/config"
import { exchangeCode } from "@/lib/server/oidc"
import { COOKIE, storeTokens, unseal } from "@/lib/server/session"

export async function GET(request: NextRequest) {
  const base = serverConfig.frontendUrl
  const params = request.nextUrl.searchParams
  const jar = await cookies()
  const pending = await unseal<{ state: string; nonce: string; verifier: string; returnTo: string }>(jar.get(COOKIE.oidc)?.value)
  jar.delete(COOKIE.oidc)

  if (params.get("error")) {
    return NextResponse.redirect(`${base}/login?error=${encodeURIComponent(params.get("error") ?? "login_failed")}`)
  }
  const code = params.get("code")
  if (!pending || !code || params.get("state") !== pending.state) {
    return NextResponse.redirect(`${base}/login?error=invalid_state`)
  }
  try {
    const tokens = await exchangeCode(code, pending.verifier, pending.nonce)
    const user = await storeTokens(tokens)
    if (user.roles.length === 0) return NextResponse.redirect(`${base}/login?error=no_role`)
    return NextResponse.redirect(`${base}${pending.returnTo || homeFor(user.roles)}`)
  } catch (err) {
    console.error("OIDC callback failed", err)
    return NextResponse.redirect(`${base}/login?error=token_exchange_failed`)
  }
}
