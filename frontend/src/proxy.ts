// Route guard for the portals. The backend enforces RBAC on every API call;
// this only keeps users out of portal pages they cannot use.
import { jwtDecrypt } from "jose"
import { NextResponse, type NextRequest } from "next/server"

import { canAccess, homeFor, type SessionUser } from "@/lib/roles"

async function readUser(request: NextRequest): Promise<SessionUser | null> {
  const value = request.cookies.get("mc_user")?.value
  const secret = process.env.SESSION_SECRET
  if (!value || !secret) return null
  try {
    const key = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret)))
    const { payload } = await jwtDecrypt(value, key)
    return payload as unknown as SessionUser
  } catch {
    return null
  }
}

export async function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const user = await readUser(request)
  if (!user) {
    const login = new URL("/login", request.url)
    login.searchParams.set("returnTo", pathname + search)
    return NextResponse.redirect(login)
  }
  if (!canAccess(pathname, user.roles)) {
    return NextResponse.redirect(new URL(homeFor(user.roles), request.url))
  }
  return NextResponse.next()
}

export const config = {
  matcher: ["/citizen/:path*", "/officer/:path*", "/admin/:path*"],
}
