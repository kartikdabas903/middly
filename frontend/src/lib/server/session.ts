// Encrypted, httpOnly session cookies for the BFF. Tokens never reach browser JavaScript.
import { EncryptJWT, jwtDecrypt, decodeJwt } from "jose"
import { cookies } from "next/headers"

import type { Role, SessionUser } from "@/lib/roles"
import { serverConfig } from "@/lib/server/config"

export const COOKIE = {
  access: "mc_at",
  refresh: "mc_rt",
  idToken: "mc_idt",
  user: "mc_user",
  oidc: "mc_oidc",
} as const

const KNOWN_ROLES: Role[] = ["CITIZEN", "OFFICER", "DEPARTMENT_ADMIN", "PLATFORM_ADMIN"]

let cachedKey: { secret: string; key: Uint8Array } | null = null

async function key(): Promise<Uint8Array> {
  const secret = serverConfig.sessionSecret
  if (cachedKey?.secret === secret) return cachedKey.key
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(secret))
  cachedKey = { secret, key: new Uint8Array(digest) }
  return cachedKey.key
}

export async function seal(payload: Record<string, unknown>, maxAgeSeconds: number): Promise<string> {
  return new EncryptJWT(payload)
    .setProtectedHeader({ alg: "dir", enc: "A256GCM" })
    .setIssuedAt()
    .setExpirationTime(`${Math.max(60, maxAgeSeconds)}s`)
    .encrypt(await key())
}

export async function unseal<T = Record<string, unknown>>(value: string | undefined): Promise<T | null> {
  if (!value) return null
  try {
    const { payload } = await jwtDecrypt(value, await key())
    return payload as T
  } catch {
    return null
  }
}

export interface TokenSet {
  access_token: string
  refresh_token?: string
  id_token?: string
  expires_in: number
  refresh_expires_in?: number
}

export function userFromAccessToken(accessToken: string): SessionUser {
  const claims = decodeJwt(accessToken) as Record<string, unknown>
  const realmRoles = ((claims.realm_access as { roles?: string[] } | undefined)?.roles ?? []).filter((r): r is Role =>
    KNOWN_ROLES.includes(r as Role),
  )
  return {
    sub: String(claims.sub),
    username: String(claims.preferred_username ?? claims.sub),
    name: String(claims.name ?? claims.preferred_username ?? "User"),
    email: claims.email ? String(claims.email) : undefined,
    roles: realmRoles,
    citizenId: claims.citizen_id ? String(claims.citizen_id) : undefined,
    department: claims.department ? String(claims.department) : undefined,
  }
}

function cookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: serverConfig.secureCookies,
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  }
}

export async function storeTokens(tokens: TokenSet): Promise<SessionUser> {
  const jar = await cookies()
  const sessionMaxAge = tokens.refresh_expires_in && tokens.refresh_expires_in > 0 ? tokens.refresh_expires_in : 3600
  const accessExp = Math.floor(Date.now() / 1000) + tokens.expires_in
  const user = userFromAccessToken(tokens.access_token)
  jar.set(COOKIE.access, await seal({ t: tokens.access_token, exp_at: accessExp }, sessionMaxAge), cookieOptions(sessionMaxAge))
  if (tokens.refresh_token) jar.set(COOKIE.refresh, await seal({ t: tokens.refresh_token }, sessionMaxAge), cookieOptions(sessionMaxAge))
  if (tokens.id_token) jar.set(COOKIE.idToken, await seal({ t: tokens.id_token }, sessionMaxAge), cookieOptions(sessionMaxAge))
  jar.set(COOKIE.user, await seal({ ...user }, sessionMaxAge), cookieOptions(sessionMaxAge))
  return user
}

export async function clearSession(): Promise<void> {
  const jar = await cookies()
  for (const name of Object.values(COOKIE)) jar.delete(name)
}

export async function getSessionUser(): Promise<SessionUser | null> {
  const jar = await cookies()
  return unseal<SessionUser>(jar.get(COOKIE.user)?.value)
}

export async function readTokens(): Promise<{ accessToken?: string; accessExp?: number; refreshToken?: string; idToken?: string }> {
  const jar = await cookies()
  const at = await unseal<{ t: string; exp_at: number }>(jar.get(COOKIE.access)?.value)
  const rt = await unseal<{ t: string }>(jar.get(COOKIE.refresh)?.value)
  const idt = await unseal<{ t: string }>(jar.get(COOKIE.idToken)?.value)
  return { accessToken: at?.t, accessExp: at?.exp_at, refreshToken: rt?.t, idToken: idt?.t }
}
