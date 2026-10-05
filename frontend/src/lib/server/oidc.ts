// OpenID Connect authorization-code flow with PKCE against Keycloak (confidential BFF client).
import { decodeJwt } from "jose"

import { serverConfig } from "@/lib/server/config"
import { readTokens, storeTokens, type TokenSet } from "@/lib/server/session"

function b64url(bytes: Uint8Array): string {
  return Buffer.from(bytes).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "")
}

export function randomToken(size = 32): string {
  return b64url(crypto.getRandomValues(new Uint8Array(size)))
}

export async function pkceChallenge(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))
  return b64url(new Uint8Array(digest))
}

const realmPath = () => `/realms/${serverConfig.realm}/protocol/openid-connect`

export function authorizeUrl(params: { state: string; nonce: string; challenge: string; loginHint?: string }): string {
  const url = new URL(`${serverConfig.keycloakPublicUrl}${realmPath()}/auth`)
  url.searchParams.set("client_id", serverConfig.clientId)
  url.searchParams.set("redirect_uri", `${serverConfig.frontendUrl}/auth/callback`)
  url.searchParams.set("response_type", "code")
  url.searchParams.set("scope", "openid profile email")
  url.searchParams.set("state", params.state)
  url.searchParams.set("nonce", params.nonce)
  url.searchParams.set("code_challenge", params.challenge)
  url.searchParams.set("code_challenge_method", "S256")
  if (params.loginHint) url.searchParams.set("login_hint", params.loginHint)
  return url.toString()
}

async function tokenRequest(body: Record<string, string>): Promise<TokenSet> {
  const res = await fetch(`${serverConfig.keycloakInternalUrl}${realmPath()}/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_id: serverConfig.clientId, client_secret: serverConfig.clientSecret, ...body }),
    cache: "no-store",
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Token endpoint returned ${res.status}: ${text.slice(0, 200)}`)
  }
  return (await res.json()) as TokenSet
}

export async function exchangeCode(code: string, verifier: string, expectedNonce: string): Promise<TokenSet> {
  const tokens = await tokenRequest({
    grant_type: "authorization_code",
    code,
    code_verifier: verifier,
    redirect_uri: `${serverConfig.frontendUrl}/auth/callback`,
  })
  if (tokens.id_token) {
    const claims = decodeJwt(tokens.id_token)
    if (claims.nonce !== expectedNonce) throw new Error("OIDC nonce mismatch")
  }
  return tokens
}

/** Returns a valid access token, refreshing it (and rewriting cookies) when it is about to expire. */
export async function getValidAccessToken(): Promise<string | null> {
  const { accessToken, accessExp, refreshToken } = await readTokens()
  const now = Math.floor(Date.now() / 1000)
  if (accessToken && accessExp && accessExp - now > 30) return accessToken
  if (!refreshToken) return null
  try {
    const tokens = await tokenRequest({ grant_type: "refresh_token", refresh_token: refreshToken })
    await storeTokens(tokens)
    return tokens.access_token
  } catch {
    return null
  }
}

export function endSessionUrl(idToken?: string): string {
  const url = new URL(`${serverConfig.keycloakPublicUrl}${realmPath()}/logout`)
  url.searchParams.set("post_logout_redirect_uri", `${serverConfig.frontendUrl}/`)
  url.searchParams.set("client_id", serverConfig.clientId)
  if (idToken) url.searchParams.set("id_token_hint", idToken)
  return url.toString()
}
