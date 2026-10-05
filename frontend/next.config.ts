import type { NextConfig } from "next"
import { PHASE_DEVELOPMENT_SERVER } from "next/constants"

function securityHeaders(dev: boolean) {
  return [
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    {
      key: "Content-Security-Policy",
      value: [
        "default-src 'self'",
        // React dev tooling needs eval(); production builds stay strict.
        `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        `connect-src 'self'${dev ? " ws: wss:" : ""}`,
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
      ].join("; "),
    },
  ]
}

export default function config(phase: string): NextConfig {
  const dev = phase === PHASE_DEVELOPMENT_SERVER
  return {
    output: "standalone",
    poweredByHeader: false,
    devIndicators: { position: "bottom-right" },
    async headers() {
      return [{ source: "/:path*", headers: securityHeaders(dev) }]
    },
  }
}
