// Server-side runtime configuration (read at request time, never bundled to the browser).

function required(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback
  if (!value) throw new Error(`Missing environment variable ${name}`)
  return value
}

export const serverConfig = {
  get frontendUrl() {
    return required("FRONTEND_URL", "http://localhost:3000").replace(/\/$/, "")
  },
  get apiBaseUrl() {
    return required("API_BASE_URL", "http://localhost:8000/api/v1").replace(/\/$/, "")
  },
  get keycloakPublicUrl() {
    return required("KEYCLOAK_PUBLIC_URL", "http://localhost:8080").replace(/\/$/, "")
  },
  get keycloakInternalUrl() {
    return (process.env.KEYCLOAK_INTERNAL_URL || this.keycloakPublicUrl).replace(/\/$/, "")
  },
  get realm() {
    return required("KEYCLOAK_REALM", "middly")
  },
  get clientId() {
    return required("OIDC_CLIENT_ID", "middly-frontend")
  },
  get clientSecret() {
    return required("OIDC_CLIENT_SECRET")
  },
  get sessionSecret() {
    const secret = required("SESSION_SECRET")
    if (secret.length < 32) throw new Error("SESSION_SECRET must be at least 32 characters")
    return secret
  },
  /** Show sample sign-in accounts and sandbox tools (sandbox environments only). */
  get sandbox() {
    return (process.env.DEMO_MODE ?? "true") === "true"
  },
  get secureCookies() {
    return this.frontendUrl.startsWith("https://")
  },
  get links() {
    return {
      grafana: process.env.GRAFANA_URL || "http://localhost:3001",
      prometheus: process.env.PROMETHEUS_URL || "http://localhost:9090",
      rabbitmq: process.env.RABBITMQ_MGMT_URL || "http://localhost:15672",
      swagger: `${process.env.GATEWAY_PUBLIC_URL || "http://localhost:8000"}/docs`,
      keycloak: `${this.keycloakPublicUrl}/admin/`,
    }
  },
}
