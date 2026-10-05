#!/usr/bin/env node
// `npm run dev:all` — full development mode:
//   * Docker: everything except the frontend, with source bind-mounts and backend auto-reload
//   * Frontend: `next dev` on http://localhost:3000 with hot reload (reads the root .env)
// Ctrl+C stops the frontend; the Docker services keep running (`npm run stop` to stop them).
import { spawn, spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const isWin = process.platform === "win32"
const COMPOSE = ["compose", "-f", "docker-compose.yml", "-f", "docker-compose.dev.yml"]

function run(cmd, args, opts = {}) {
  const res = isWin
    ? spawnSync([cmd, ...args].join(" "), { cwd: root, stdio: "inherit", shell: true, ...opts })
    : spawnSync(cmd, args, { cwd: root, stdio: "inherit", ...opts })
  if (res.status !== 0) {
    console.error(`\n✗ Command failed: ${cmd} ${args.join(" ")}`)
    process.exit(res.status ?? 1)
  }
}

function loadEnv() {
  const file = join(root, ".env")
  if (!existsSync(file)) {
    console.log("▶ No .env found — creating one from .env.example")
    run(isWin ? "powershell" : "bash", isWin ? ["-ExecutionPolicy", "Bypass", "-File", "scripts\\install-dev.ps1"] : ["scripts/init-env.sh"])
  }
  const env = {}
  for (const line of readFileSync(file, "utf8").split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$/)
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g, "")
  }
  return env
}

async function waitFor(url, label, seconds = 240) {
  process.stdout.write(`▶ Waiting for ${label} `)
  for (let i = 0; i < seconds / 3; i++) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(2500) })
      if (res.ok) {
        console.log("✔")
        return
      }
    } catch {
      /* not up yet */
    }
    process.stdout.write(".")
    await new Promise((r) => setTimeout(r, 3000))
  }
  console.error(`\n✗ ${label} did not become ready — check: docker compose logs`)
  process.exit(1)
}

const env = loadEnv()
const gatewayPort = env.GATEWAY_PORT || "8000"
const keycloakUrl = env.KEYCLOAK_PUBLIC_URL || "http://localhost:8080"

console.log("▶ Starting backend services in Docker (dev mode: code mounted, auto-reload)…")
run("docker", [...COMPOSE, "stop", "frontend"], { stdio: "ignore" })
run("docker", [...COMPOSE, "up", "-d", "--build", "--scale", "frontend=0"])

await waitFor(`http://localhost:${gatewayPort}/health`, "API (gateway → backend)")
await waitFor(`${keycloakUrl}/realms/${env.KEYCLOAK_REALM || "middly"}/.well-known/openid-configuration`, "Keycloak")

const frontendDir = join(root, "frontend")
if (!existsSync(join(frontendDir, "node_modules"))) {
  console.log("▶ Installing frontend dependencies…")
  run("npm", ["install", "--no-audit", "--no-fund"], { cwd: frontendDir })
}

const devEnv = {
  ...process.env,
  FRONTEND_URL: env.FRONTEND_URL || "http://localhost:3000",
  API_BASE_URL: `http://localhost:${gatewayPort}/api/v1`,
  KEYCLOAK_PUBLIC_URL: keycloakUrl,
  KEYCLOAK_INTERNAL_URL: keycloakUrl,
  KEYCLOAK_REALM: env.KEYCLOAK_REALM || "middly",
  OIDC_CLIENT_ID: env.OIDC_CLIENT_ID || "middly-frontend",
  OIDC_CLIENT_SECRET: env.OIDC_CLIENT_SECRET,
  SESSION_SECRET: env.SESSION_SECRET,
  DEMO_MODE: env.DEMO_MODE ?? "true",
  GRAFANA_URL: `http://localhost:${env.GRAFANA_PORT || "3001"}`,
  PROMETHEUS_URL: `http://localhost:${env.PROMETHEUS_PORT || "9090"}`,
  RABBITMQ_MGMT_URL: `http://localhost:${env.RABBITMQ_MGMT_PORT || "15672"}`,
  GATEWAY_PUBLIC_URL: `http://localhost:${gatewayPort}`,
}

console.log(`
✔ Middly dev environment
  Portal (hot reload):  ${devEnv.FRONTEND_URL}
  API docs:             http://localhost:${gatewayPort}/docs
  Backend (direct):     http://localhost:8001/docs   (auto-reloads on backend/ changes)
  Keycloak:             ${keycloakUrl}
  Grafana:              ${devEnv.GRAFANA_URL}
  Ctrl+C stops the frontend; run "npm run stop" to stop Docker services.
`)

const next = spawn(isWin ? "npm run dev" : "npm", isWin ? [] : ["run", "dev"], { cwd: frontendDir, env: devEnv, stdio: "inherit", shell: isWin })
const stop = () => next.kill("SIGINT")
process.on("SIGINT", stop)
process.on("SIGTERM", stop)
next.on("exit", (code) => process.exit(code ?? 0))
