import { expect, type APIRequestContext, type Page } from "@playwright/test"

export const GATEWAY = process.env.E2E_GATEWAY_URL ?? "http://localhost:8000"
export const KEYCLOAK = process.env.E2E_KEYCLOAK_URL ?? "http://localhost:8080"

export const PASSWORDS: Record<string, string> = {
  citizen: process.env.DEMO_CITIZEN_PASSWORD ?? "Citizen@123",
  officer: process.env.DEMO_OFFICER_PASSWORD ?? "Officer@123",
  admin: process.env.DEMO_ADMIN_PASSWORD ?? "Admin@123",
}

function passwordFor(username: string): string {
  if (username.startsWith("citizen")) return PASSWORDS.citizen
  if (username.startsWith("officer")) return PASSWORDS.officer
  return PASSWORDS.admin
}

/** Signs in through the real Keycloak login page (OIDC authorization code + PKCE). */
export async function login(page: Page, username: string) {
  await page.context().clearCookies()
  await page.goto("/login")
  await page.getByTestId(`login-${username}`).click()
  await page.waitForURL(/\/realms\/middly\/protocol\/openid-connect\/auth/)
  await page.locator("#username").fill(username)
  await page.locator("#password").fill(passwordFor(username))
  await page.locator("#kc-login").click()
  await page.waitForURL((url) => url.origin === new URL(page.url()).origin && !url.pathname.startsWith("/auth/"), { timeout: 30_000 })
  await expect(page.getByTestId("user-menu")).toBeVisible()
}

export async function apiToken(request: APIRequestContext, username: string): Promise<string> {
  const res = await request.post(`${KEYCLOAK}/realms/middly/protocol/openid-connect/token`, {
    form: { grant_type: "password", client_id: "middly-demo-cli", username, password: passwordFor(username) },
  })
  expect(res.ok()).toBeTruthy()
  return (await res.json()).access_token as string
}

export async function chooseOption(page: Page, field: string, value: string) {
  await page.getByTestId(`field-${field}`).click()
  await page.getByTestId(`option-${value}`).click()
}
