import { expect, test } from "@playwright/test"

import { GATEWAY, apiToken, chooseOption, login } from "./helpers"

// The complete SIH demonstration, driven through the real UI, Keycloak, gateway,
// connectors, workflow engine and RabbitMQ (no database manipulation).
test.describe.serial("Middly demo", () => {
  let appUrlPath = ""
  let appNumber = ""

  test("Scenario 1a — citizen applies, grants consent, data is fetched and verified", async ({ page }) => {
    await login(page, "citizen1")
    await expect(page).toHaveURL(/\/citizen\/dashboard/)

    await page.goto("/citizen/apply")
    await page.getByTestId("apply-SKILL_DEV_SCHEME").click()
    await expect(page.getByRole("heading", { name: /Skill Development Training Scheme/ })).toBeVisible()

    // Minimal input only.
    await chooseOption(page, "preferred_trade", "SOFTWARE_DEVELOPMENT")
    await chooseOption(page, "preferred_district", "Pune")
    await chooseOption(page, "training_mode", "HYBRID")
    await page.getByTestId("submit-application").click()

    // Explicit consent request.
    const consent = page.getByTestId("consent-request")
    await expect(consent).toBeVisible()
    await expect(consent).toContainText("Skill Development Department")
    for (const label of ["Identity Information", "Education Information", "Employment Information"]) {
      await expect(consent).toContainText(label)
    }
    await page.getByTestId("consent-allow").click()

    // Live verification, then redirect to the tracking page.
    await expect(page.getByTestId("processing")).toBeVisible()
    await page.waitForURL(/\/citizen\/applications\/[0-9a-f-]{36}$/, { timeout: 60_000 })
    appUrlPath = new URL(page.url()).pathname
    appNumber = (await page.getByTestId("application-number").innerText()).trim()
    expect(appNumber).toBe("APP-2026-0001")

    await expect(page.locator('[data-status="UNDER_REVIEW"]').first()).toBeVisible()
    for (const src of ["identity", "education", "employment"]) {
      await expect(page.getByTestId(`source-${src}`)).toHaveAttribute("data-state", "VERIFIED")
    }
    const timeline = page.getByTestId("timeline")
    await expect(timeline.locator('[data-step="FETCH_EMPLOYMENT"]')).toHaveAttribute("data-state", "done")
    await expect(timeline.locator('[data-step="ELIGIBILITY_CHECK"]')).toHaveAttribute("data-state", "done")
    await expect(timeline.locator('[data-step="OFFICER_REVIEW"]')).toHaveAttribute("data-state", "current")
    await expect(page.getByTestId("eligibility")).toContainText("Eligible")
  })

  test("Scenario 1b — officer reviews consolidated data and approves", async ({ page }) => {
    await login(page, "officer1")
    await page.goto("/officer/applications")
    await page.locator(`[data-app="${appNumber}"] a`).first().click()
    await expect(page.getByTestId("application-number")).toHaveText(appNumber)

    const profile = page.getByTestId("profile")
    await expect(profile).toContainText("Rahul Sharma")
    await expect(profile).toContainText("Identity Service") // field provenance
    await expect(profile).toContainText("B.Tech")
    await expect(profile).toContainText("Unemployed")

    await page.getByTestId("officer-approve").click()
    await page.getByTestId("decision-text").fill("Identity, education and employment verified via registries.")
    await page.getByTestId("confirm-decision").click()
    await expect(page.locator('[data-status="APPROVED"]').first()).toBeVisible()
  })

  test("Scenario 1c — approval event reaches the citizen as a notification", async ({ page }) => {
    await login(page, "citizen1")
    await page.goto("/citizen/notifications")
    await expect(page.getByTestId("notifications")).toContainText(`Application ${appNumber} approved.`, { timeout: 30_000 })

    await page.goto(appUrlPath)
    await expect(page.getByTestId("approved-banner")).toContainText(`Application ${appNumber} approved.`)
    // Timeline completes once the notification consumer marks the final step.
    await expect(page.getByTestId("timeline").locator('[data-step="NOTIFICATION_SENT"]')).toHaveAttribute("data-state", "done", { timeout: 30_000 })
  })

  test("Scenario 1d — admin sees connector calls, workflow, events, audit and processing time", async ({ page }) => {
    await login(page, "admin1")
    await expect(page).toHaveURL(/\/admin\/dashboard/)
    await expect(page.getByTestId("kpi-connector-calls")).toBeVisible()
    await expect(page.getByTestId("kpi-processing")).not.toContainText("—")
    await expect(page.getByTestId("connector-identity")).toHaveAttribute("data-status", "HEALTHY")

    await page.goto("/admin/events")
    await expect(page.getByTestId("events-table").locator('[data-event="APPLICATION_APPROVED"]').first()).toBeVisible()

    await page.goto("/admin/audit-logs")
    await expect(page.getByTestId("audit-table")).toContainText("OFFICER_APPROVED_APPLICATION")
    await page.getByTestId("verify-chain").click()
    await expect(page.getByText("Audit chain intact")).toBeVisible()

    await page.goto("/admin/workflows")
    await expect(page.getByText(appNumber).first()).toBeVisible()
  })

  test("Scenario 2 — eligibility failure is explained to the citizen", async ({ page }) => {
    await login(page, "citizen3")
    await page.goto("/citizen/apply/SKILL_DEV_SCHEME")
    await chooseOption(page, "preferred_trade", "DATA_ENTRY")
    await chooseOption(page, "preferred_district", "Nagpur")
    await chooseOption(page, "training_mode", "ONLINE")
    await page.getByTestId("submit-application").click()
    await page.getByTestId("consent-allow").click()
    await page.waitForURL(/\/citizen\/applications\/[0-9a-f-]{36}$/, { timeout: 60_000 })

    await expect(page.getByTestId("rejected-banner")).toBeVisible()
    const eligibility = page.getByTestId("eligibility")
    await expect(eligibility.locator('[data-rule="MAHARASHTRA_RESIDENT"]')).toHaveAttribute("data-passed", "false")
    await expect(eligibility.locator('[data-rule="AGE_RANGE"]')).toHaveAttribute("data-passed", "false")
    await expect(eligibility.locator('[data-rule="EDUCATION_REQUIREMENT"]')).toHaveAttribute("data-passed", "true")
  })

  test("Scenario 3 — department outage, graceful waiting state and retry", async ({ page, request }) => {
    const admin = await apiToken(request, "admin1")
    const setFault = (mode: string) =>
      request.post(`${GATEWAY}/api/v1/demo/connectors/employment/fault`, { headers: { Authorization: `Bearer ${admin}` }, data: { mode } })
    expect((await setFault("DOWN")).ok()).toBeTruthy()
    try {
      await login(page, "citizen2")
      await page.goto("/citizen/apply/SKILL_DEV_SCHEME")
      await chooseOption(page, "preferred_trade", "ELECTRONICS_REPAIR")
      await chooseOption(page, "preferred_district", "Nagpur")
      await chooseOption(page, "training_mode", "CLASSROOM")
      await page.getByTestId("submit-application").click()
      await page.getByTestId("consent-allow").click()
      await page.waitForURL(/\/citizen\/applications\/[0-9a-f-]{36}$/, { timeout: 60_000 })

      await expect(page.getByTestId("source-unavailable")).toContainText("Employment Registry")
      await expect(page.getByTestId("source-unavailable")).toContainText("Temporarily unavailable")
      await expect(page.getByTestId("source-employment")).toHaveAttribute("data-state", "UNAVAILABLE")
    } finally {
      expect((await setFault("HEALTHY")).ok()).toBeTruthy()
    }
    await page.getByTestId("retry-button").click()
    await expect(page.getByTestId("source-employment")).toHaveAttribute("data-state", "VERIFIED", { timeout: 30_000 })
    await expect(page.locator('[data-status="UNDER_REVIEW"]').first()).toBeVisible()
  })

  test("Consent can be revoked by the citizen", async ({ page }) => {
    await login(page, "citizen2")
    await page.goto("/citizen/consents")
    const active = page.locator('[data-testid="consent-card"][data-status="ACTIVE"]').first()
    await expect(active).toBeVisible()
    await active.getByTestId("revoke-consent").click()
    await page.getByTestId("confirm-revoke").click()
    await expect(page.locator('[data-testid="consent-card"][data-status="REVOKED"]').first()).toBeVisible()
  })
})
