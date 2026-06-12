import { expect, test } from "@playwright/test";

/**
 * Echte Auth-Flow E2E Tests.
 *
 * Setzt voraus, dass:
 * 1. Das Backend läuft (PLAYWRIGHT_FULL_E2E=1 startet es)
 * 2. Der Owner-Account existiert mit den in PLAYWRIGHT_OWNER_EMAIL / PASSWORD konfigurierten Credentials
 *
 * Die meisten Tests sind `@skipif` weil der Owner-Account nicht in der Test-DB existiert.
 * Sie funktionieren, sobald man die Test-Setup (PLAYWRIGHT_OWNER_EMAIL/PASSWORD + DB-Seed) konfiguriert.
 */

const backendReady = !!process.env.PLAYWRIGHT_FULL_E2E;
const testIfBackend = backendReady ? test : test.skip;

testIfBackend("login submit with valid owner credentials sets ff_session cookie and redirects to /", async ({ page, context }) => {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(process.env.PLAYWRIGHT_OWNER_EMAIL ?? "owner@example.com");
  await page.locator('input[type="password"]').fill(process.env.PLAYWRIGHT_OWNER_PASSWORD ?? "testpass");
  await page.getByRole("button", { name: /anmelden/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 10_000 });
  const cookies = await context.cookies();
  const sessionCookie = cookies.find((c) => c.name === "ff_session");
  expect(sessionCookie).toBeDefined();
  expect(sessionCookie?.httpOnly).toBe(true);
});

testIfBackend("login submit with wrong password shows error and stays on /login", async ({ page }) => {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill("owner@example.com");
  await page.locator('input[type="password"]').fill("definitely-wrong-password");
  await page.getByRole("button", { name: /anmelden/i }).click();
  await expect(page.getByText(/ungültig/i)).toBeVisible({ timeout: 5_000 });
  await expect(page).toHaveURL(/\/login$/);
});

testIfBackend("after login, /api/auth/me returns the user data", async ({ page }) => {
  await page.goto("/login");
  await page.locator('input[type="email"]').fill(process.env.PLAYWRIGHT_OWNER_EMAIL ?? "owner@example.com");
  await page.locator('input[type="password"]').fill(process.env.PLAYWRIGHT_OWNER_PASSWORD ?? "testpass");
  await page.getByRole("button", { name: /anmelden/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), { timeout: 10_000 });
  const response = await page.request.get("/api/auth/me");
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.email).toBeTruthy();
  expect(body.id).toBeGreaterThan(0);
});

test("auth tests are skipped without PLAYWRIGHT_FULL_E2E — manual setup required", () => {
  // Diese Tests benötigen einen laufenden Backend + Owner-Account.
  // Setze PLAYWRIGHT_FULL_E2E=1 + PLAYWRIGHT_OWNER_EMAIL/PASSWORD env vars.
  if (!process.env.PLAYWRIGHT_FULL_E2E) {
    console.log("INFO: Auth-Tests skipped — Backend-Setup fehlt");
  }
  expect(true).toBe(true); // No-op
});
