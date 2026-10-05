// Backend-for-frontend proxy: attaches the user's access token (from the encrypted
// session cookie) and forwards the call to the platform API through the gateway.
import { NextResponse, type NextRequest } from "next/server"

import { serverConfig } from "@/lib/server/config"
import { getValidAccessToken } from "@/lib/server/oidc"

export const dynamic = "force-dynamic"

const SAFE_SEGMENT = /^[A-Za-z0-9._~-]+$/

async function proxy(request: NextRequest, ctx: RouteContext<"/bff/[...path]">) {
  const { path } = await ctx.params
  if (!path.length || path.some((seg) => !SAFE_SEGMENT.test(seg) || seg === "." || seg === "..")) {
    return NextResponse.json({ error: { code: "BAD_PATH", message: "Invalid API path" } }, { status: 400 })
  }
  const token = await getValidAccessToken()
  if (!token) {
    return NextResponse.json({ error: { code: "UNAUTHENTICATED", message: "Session expired — please sign in again" } }, { status: 401 })
  }
  const requestId = request.headers.get("x-request-id") || crypto.randomUUID()
  const target = `${serverConfig.apiBaseUrl}/${path.join("/")}${request.nextUrl.search}`
  const hasBody = !["GET", "HEAD"].includes(request.method)
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-Request-ID": requestId,
        "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
      },
      body: hasBody ? await request.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(90_000),
    })
    const body = await upstream.text()
    return new NextResponse(body, {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        "X-Request-ID": upstream.headers.get("x-request-id") ?? requestId,
        "Cache-Control": "no-store",
      },
    })
  } catch {
    return NextResponse.json(
      { error: { code: "GATEWAY_UNREACHABLE", message: "Platform API is unreachable", correlation_id: requestId } },
      { status: 502 },
    )
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as DELETE }
