// Browser-side API client. All calls go through the Next.js BFF (/bff/*), which
// attaches the access token server-side and forwards to the API gateway.

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
    public correlationId?: string,
  ) {
    super(message)
  }
}

type Query = Record<string, string | number | boolean | undefined | null>

function buildUrl(path: string, query?: Query): string {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v))
  }
  const suffix = qs.toString() ? `?${qs}` : ""
  return `/bff/${path.replace(/^\/+/, "")}${suffix}`
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const res = await fetch(buildUrl(path, query), {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  })
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    const err = data?.error ?? {}
    if (res.status === 401 && typeof window !== "undefined") {
      // Full reload on purpose: clears client state before re-authenticating.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = `/login?returnTo=${encodeURIComponent(window.location.pathname)}&error=session_expired`
    }
    throw new ApiError(res.status, err.code ?? "ERROR", err.message ?? `Request failed (${res.status})`, err.details, err.correlation_id)
  }
  return data as T
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, undefined, query),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const ref = err.correlationId ? ` (ref ${err.correlationId.slice(0, 8)})` : ""
    return `${err.message}${ref}`
  }
  return err instanceof Error ? err.message : "Something went wrong"
}
