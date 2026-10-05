import { request } from "@playwright/test"

import { GATEWAY, KEYCLOAK, PASSWORDS } from "./helpers"

/** Resets the demo environment so the live demo starts at APP-2026-0001. */
export default async function globalSetup() {
  if (process.env.E2E_SKIP_RESET === "1") return
  const ctx = await request.newContext()
  const tokenRes = await ctx.post(`${KEYCLOAK}/realms/middly/protocol/openid-connect/token`, {
    form: { grant_type: "password", client_id: "middly-demo-cli", username: "admin1", password: PASSWORDS.admin },
  })
  if (!tokenRes.ok()) throw new Error(`Could not obtain admin token: ${tokenRes.status()}`)
  const token = (await tokenRes.json()).access_token
  const reset = await ctx.post(`${GATEWAY}/api/v1/demo/reset`, { headers: { Authorization: `Bearer ${token}` }, timeout: 120_000 })
  if (!reset.ok()) throw new Error(`Demo reset failed: ${reset.status()} ${await reset.text()}`)
  await ctx.dispose()
}
