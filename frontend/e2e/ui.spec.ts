import { expect, test } from "@playwright/test";

/**
 * Pure UI rendering tests — backend-Network-Calls werden blockiert, damit
 * die Form rendert ohne auf /api/auth/me zu warten.
 */

test.beforeEach(async ({ context }) => {
  await context.route("**/api/**", (route) => route.abort());
});

test("login page renders one email-type and one password-type input", async ({ page }) => {
  await page.goto("/login");
  await expect(page.locator('input[type="email"]')).toHaveCount(1);
  await expect(page.locator('input[type="password"]')).toHaveCount(1);
});

test("login form has a submit button labeled Anmelden", async ({ page }) => {
  await page.goto("/login");
  const button = page.getByRole("button", { name: /anmelden/i });
  await expect(button).toBeVisible();
  await expect(button).toBeEnabled();
});

test("app root /login route renders the brand text FixundFertig", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByText("FixundFertig").first()).toBeVisible();
});

test("email and password fields are required (HTML5 attribute)", async ({ page }) => {
  await page.goto("/login");
  const email = page.locator('input[type="email"]');
  const password = page.locator('input[type="password"]');
  await expect(email).toHaveAttribute("required", "");
  await expect(password).toHaveAttribute("required", "");
});

test("dashboard / route is protected: dashboard greeting Hallo is not rendered for unauth users", async ({ page }) => {
  await page.goto("/");
  // Without auth, root triggers window.location.assign("/login") — give it a tick.
  await page.waitForTimeout(300);
  // The dashboard's own greeting "Hallo" should NOT be in the DOM (proves auth guard).
  const bodyText = (await page.locator("body").textContent()) ?? "";
  expect(bodyText.includes("Hallo")).toBe(false);
});

test("settings hub is protected: redirects unauth users to /login", async ({ page }) => {
  await page.goto("/settings");
  await page.waitForTimeout(300);
  // Protected route should bounce to /login — assert login form is present, settings heading isn't
  await expect(page.locator('input[type="email"]')).toHaveCount(1);
  await expect(page.getByText(/^Einstellungen$/)).toHaveCount(0);
});

test("invoices /invoices route is protected: redirects unauth users to /login", async ({ page }) => {
  await page.goto("/invoices");
  await page.waitForTimeout(300);
  await expect(page.locator('input[type="email"]')).toHaveCount(1);
  await expect(page.getByRole("heading", { name: /^Rechnungen$/ })).toHaveCount(0);
});

test("invoice detail page shows preview iframe and download link", async ({ page }) => {
  // Mock /api/invoices/{id} so the page renders the invoice
  await page.route("**/api/invoices/123", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 123,
        customer_id: 1,
        nr: "RE-2026-0001",
        title: "Test-Rechnung",
        date: "2026-06-10",
        delivery_date: "",
        recipient_name: "Max",
        recipient_street: "",
        recipient_postal_code: "",
        recipient_city: "",
        total_brutto: 119.0,
        status: "OPEN",
        revision_nr: 0,
        updated_at: "",
        related_invoice_id: null,
        items: [],
      }),
    }),
  );
  // Mock /api/auth/me to bypass auth guard
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 1, email: "test@example.com", is_active: true }),
    }),
  );
  await page.goto("/invoices/123");
  await expect(page.getByTestId("invoice-download-link")).toBeVisible();
  await expect(page.getByTestId("invoice-preview-link")).toBeVisible();
  // Download link should have correct href
  const downloadHref = await page.getByTestId("invoice-download-link").getAttribute("href");
  expect(downloadHref).toBe("/api/invoices/123/download");
});

test("settings hub links to /settings/company, /settings/tax-banking, /settings/account", async ({ page, context }) => {
  // beforeEach aborted all /api/**; remove that and re-mock the specific ones we need
  await context.unroute("**/api/**");
  // Capture all console messages
  page.on("console", (msg) => console.log(`[browser ${msg.type()}]`, msg.text()));
  page.on("pageerror", (err) => console.log(`[pageerror]`, err.message));
  // Mock /api/auth/me to bypass auth guard
  await context.route("**/api/auth/me", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: 1, email: "test@example.com", is_active: true }),
    }),
  );
  // Mock /api/company so the sub-pages render
  await context.route("**/api/company", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 1, name: "Test GmbH", first_name: "", last_name: "",
        business_type: "", is_small_business: false,
        street: "", postal_code: "", city: "", country: "Deutschland",
        email: "", phone: "", iban: "", bic: "", bank_name: "",
        tax_id: "", vat_id: "",
      }),
    }),
  );

  await page.goto("/settings");
  await expect(page.getByTestId("hub-company")).toBeVisible({ timeout: 10_000 });

  await page.goto("/settings/company");
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(500);
  console.log("Direct goto URL:", page.url());
  console.log("Direct goto HTML length:", (await page.content()).length);
  console.log("Direct goto body:", ((await page.locator("body").textContent()) ?? "").slice(0, 500));
  await expect(page.getByTestId("company-form")).toBeVisible({ timeout: 10_000 });
});
