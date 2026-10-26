import { expect, test } from "@playwright/test";

/**
 * Pure UI rendering tests — backend-Network-Calls werden blockiert, damit
 * die Form rendert ohne auf /api/auth/me zu warten.
 */

test.beforeEach(async ({ context }) => {
  await context.route("**/api/**", async (route) => {
    if (new URL(route.request().url()).pathname === "/api/auth/me") {
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Unauthorized" }),
      });
    }
    return route.abort();
  });
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
  await page.route("**/api/invoices/123/preview-pdf", (route) =>
    route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%%EOF" }),
  );
  await page.goto("/invoices/123");
  const downloadLink = page.getByRole("main").getByRole("link", { name: /PDF herunterladen/ });
  await expect(downloadLink).toBeVisible();
  await expect(page.getByRole("main").getByRole("button", { name: "Anlage hochladen" }).first()).toBeVisible();
  expect(await downloadLink.getAttribute("href")).toBe("/api/invoices/123/download");
  await page.getByRole("button", { name: "Mehr" }).click();
  await page.getByRole("menuitem", { name: "Vorschau" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("heading", { name: /PDF-Vorschau · Rechnung RE-2026-0001/ })).toBeVisible();
});

test("settings page configures and previews the artist invoice profile", async ({ page }) => {
  const company = {
    id: 1, name: "Daniel S.", first_name: "Daniel", last_name: "Beispiel",
    business_type: "Einzelunternehmen", is_small_business: false,
    street: "Musterstraße 1", postal_code: "10115", city: "Berlin", country: "Deutschland",
    email: "", phone: "", iban: "", bic: "", bank_name: "", account_holder: "",
    tax_id: "", vat_id: "", smtp_server: "", smtp_port: 587, smtp_user: "", smtp_password: "",
    default_sender_email: "", n8n_webhook_url: "", n8n_webhook_url_test: "",
    n8n_webhook_url_prod: "", n8n_secret: "", n8n_enabled: false,
    google_drive_folder_id: "", next_invoice_nr: 10000,
    invoice_number_template: "{seq}", invoice_filename_template: "rechnung_{nr}", logo_url: "",
    stripe_secret_key: "", stripe_publishable_key: "", paypal_email: "", payment_enabled: false,
  };
  let savedCompany: typeof company | undefined;

  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: 1, email: "test@example.com", is_active: true } }));
  await page.route("**/api/company", async (route) => {
    if (route.request().method() === "PUT") {
      savedCompany = { ...company, ...route.request().postDataJSON() };
      return route.fulfill({ json: savedCompany });
    }
    return route.fulfill({ json: company });
  });

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Unternehmen & Kontaktdaten" })).toBeVisible();
  await expect(page.getByLabel("Firmen- / Künstlername")).toHaveValue("Daniel S.");
  await page.getByLabel("Unternehmensform / Branche").selectOption("DJ / Producer");
  await expect(page.getByText(/Daniel S\. ist der Künstlername von Daniel Beispiel/)).toBeVisible();
  await page.getByTestId("settings-save").click();
  await expect(page.getByText("Gespeichert.", { exact: true })).toBeVisible();
  expect(savedCompany?.business_type).toBe("DJ / Producer");
});

const SETTINGS_COMPANY = {
  id: 1, name: "Daniel S.", first_name: "Daniel", last_name: "Beispiel",
  business_type: "DJ / Producer", is_small_business: true,
  street: "Musterstraße 1", postal_code: "10115", city: "Berlin", country: "Deutschland",
  email: "", phone: "", iban: "", bic: "", bank_name: "", account_holder: "",
  tax_id: "", vat_id: "", smtp_server: "", smtp_port: 587, smtp_user: "", smtp_password: "",
  default_sender_email: "", n8n_webhook_url: "", n8n_webhook_url_test: "",
  n8n_webhook_url_prod: "", n8n_secret: "", n8n_enabled: false,
  google_drive_folder_id: "", next_invoice_nr: 10058,
  invoice_number_template: "RE-{seq}", invoice_filename_template: "rechnung_{nr}", logo_url: "",
  stripe_secret_key: "", stripe_publishable_key: "", paypal_email: "", payment_enabled: false,
};

test("settings: the save bar only shows with changes, checks the IBAN and asks before discarding", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: 1, email: "test@example.com", is_active: true } }));
  await page.route("**/api/company", (route) => route.fulfill({ json: SETTINGS_COMPANY }));
  await page.goto("/settings");

  const bar = page.getByRole("region", { name: "Änderungen speichern" });
  await expect(page.getByLabel("Firmen- / Künstlername")).toHaveValue("Daniel S.");
  await expect(bar).toHaveCount(0);
  await expect(page.getByText(/Nächste Rechnung:/)).toContainText("RE-10058");

  await page.getByLabel("IBAN").fill("DE00 1234");
  await expect(bar).toContainText("Bitte prüfen: IBAN");
  await expect(page.getByLabel("IBAN")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByTestId("settings-save")).toBeDisabled();

  await page.getByLabel("IBAN").fill("DE89 3704 0044 0532 0130 00");
  await expect(bar).toContainText("Ungespeicherte Änderungen");
  await expect(page.getByTestId("settings-save")).toBeEnabled();

  await page.getByTestId("settings-discard").click();
  await expect(page.getByRole("alertdialog", { name: "Änderungen verwerfen?" })).toBeVisible();
  await page.getByRole("button", { name: "Verwerfen", exact: true }).last().click();
  await expect(page.getByLabel("IBAN")).toHaveValue("");
  await expect(bar).toHaveCount(0);
});

test("settings: Kleinunternehmer is a switch and the number example follows the template", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: 1, email: "test@example.com", is_active: true } }));
  await page.route("**/api/company", (route) => route.fulfill({ json: SETTINGS_COMPANY }));
  await page.goto("/settings");

  await expect(page.getByRole("switch", { name: "Kleinunternehmer (§ 19 UStG)" })).toBeChecked();
  await page.getByLabel("Rechnungsnummer-Regel").fill("{customer_code}-{seq}");
  await expect(page.getByText(/Nächste Rechnung:/)).toContainText("CLUB-10058");
});

test("new invoice: says what is missing, asks before creating and opens the new invoice", async ({ page }) => {
  let posted: Record<string, unknown> | undefined;
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: 1, email: "test@example.com", is_active: true } }));
  await page.route("**/api/company", (route) => route.fulfill({ json: SETTINGS_COMPANY }));
  await page.route("**/api/customers", (route) =>
    route.fulfill({ json: [{ id: 7, name: "Sisyphos Event GmbH", email: "buchhaltung@sisyphos.example" }] }),
  );
  await page.route("**/api/invoices", async (route) => {
    if (route.request().method() === "POST") {
      posted = route.request().postDataJSON();
      return route.fulfill({ status: 201, json: { id: 42, nr: "10058" } });
    }
    return route.fulfill({ json: [] });
  });
  await page.route("**/api/invoices/preview-pdf", (route) =>
    route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%%EOF" }),
  );

  await page.goto("/invoices/new");
  const create = page.getByRole("button", { name: "Rechnung erstellen" });
  await expect(create).toBeDisabled();
  await expect(page.getByText("Noch nötig: Kunde auswählen · mindestens eine Position anlegen")).toBeVisible();
  await expect(page.getByLabel("Umsatzsteuer ausweisen")).not.toBeChecked();

  await page.getByLabel(/Kunde/).selectOption({ label: "Sisyphos Event GmbH" });
  await page.getByRole("button", { name: "Neue Position" }).click();
  await expect(page.getByText("Noch nötig: Position 1 beschreiben")).toBeVisible();
  await page.getByLabel("Beschreibung Position 1").fill("DJ Performance");
  await page.getByLabel("Einzelpreis Position 1").fill("400");
  await expect(page.getByText(/Noch nötig/)).toHaveCount(0);
  await expect(page.getByText("400,00 €").last()).toBeVisible();

  await create.click();
  const confirm = page.getByRole("alertdialog", { name: "Rechnung erstellen?" });
  await expect(confirm).toContainText("lässt sich danach nicht mehr ändern");
  expect(posted).toBeUndefined();
  await confirm.getByRole("button", { name: "Erstellen" }).click();

  await expect(page).toHaveURL(/\/invoices\/42$/);
  expect(posted).toMatchObject({ customer_id: 7, ust_enabled: false, items: [{ description: "DJ Performance", unit_price: 400 }] });
});

test("settings: leaving with unsaved changes asks first", async ({ page }) => {
  await page.route("**/api/auth/me", (route) => route.fulfill({ json: { id: 1, email: "test@example.com", is_active: true } }));
  await page.route("**/api/company", (route) => route.fulfill({ json: SETTINGS_COMPANY }));
  await page.goto("/settings");

  await page.getByLabel("Kontoinhaber").fill("Daniel Beispiel");
  await page.getByRole("link", { name: "Rechnungen" }).first().click({ noWaitAfter: true });
  const leave = page.getByRole("alertdialog", { name: "Seite verlassen?" });
  await expect(leave).toBeVisible();
  await leave.getByRole("button", { name: "Bleiben" }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByLabel("Kontoinhaber")).toHaveValue("Daniel Beispiel");

  await page.getByRole("link", { name: "Rechnungen" }).first().click({ noWaitAfter: true });
  await page.getByRole("alertdialog", { name: "Seite verlassen?" }).getByRole("button", { name: "Seite verlassen" }).click();
  await expect(page).toHaveURL(/\/invoices/);
});
