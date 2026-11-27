import { expect, test, type Page } from "@playwright/test";

/**
 * Handy-Darstellung der Angebotsseiten (#498): bei 375×812 kein seitliches Scrollen,
 * keine überlappenden Beträge, alle Knöpfe sichtbar, Speichern am Formularende,
 * Toast und Dialog verdecken sich nicht.
 */

const PHONE = { width: 375, height: 812 };

const COMPANY = {
  id: 1, name: "Daniel S.", first_name: "Daniel", last_name: "Beispiel",
  business_type: "DJ / Producer", is_small_business: false,
  street: "Musterstraße 1", postal_code: "10115", city: "Berlin", country: "Deutschland",
  email: "", phone: "", iban: "", bic: "", bank_name: "", account_holder: "",
  tax_id: "", vat_id: "", smtp_server: "", smtp_port: 587, smtp_user: "", smtp_password: "",
  default_sender_email: "", n8n_webhook_url: "", n8n_webhook_url_test: "",
  n8n_webhook_url_prod: "", n8n_secret: "", n8n_enabled: false,
  google_drive_folder_id: "", next_invoice_nr: 10058,
  invoice_number_template: "{seq}", invoice_filename_template: "rechnung_{nr}", logo_url: "",
  stripe_secret_key: "", stripe_publishable_key: "", paypal_email: "", payment_enabled: false,
};

const QUOTE = {
  id: 42, customer_id: 7, document_type: "QUOTE", nr: "A-10000", title: "Angebot",
  subject: "DJ-Set Hammahalle, Sa auf So",
  date: "2026-10-23", valid_until: "2026-11-22", recipient_name: "Sisyphos Event GmbH",
  total_brutto: 1785, total_net: 1500, vat_rate: 19, status: "SENT",
  totals: { net: 1500, vat_rate: 19, tax: 285, gross: 1785, payable: 1785 },
  items: [
    { id: 1, description: "SEO-Grundeinrichtung für die neue Seite", quantity: 1, unit_price: 380 },
    { id: 2, description: "DJ-Set", quantity: 1, unit_price: 1400 },
  ],
  payment_plan: [
    { percent: 40, label: "bei Auftrag", amount: 714 },
    { percent: 60, label: "nach Livegang", amount: 1071 },
  ],
  settlement: { billed_brutto: 0, total_brutto: 1785, open_brutto: 1785, billed_count: 0 },
  billing: {
    convert: { allowed: true, reason: "", invoice_id: null, invoice_nr: null },
    down_payment: { allowed: true, reason: "", invoice_id: null, invoice_nr: null },
    final_invoice: { allowed: true, reason: "", invoice_id: null, invoice_nr: null },
    requires_acceptance: false,
  },
};

type Box = { x: number; y: number; width: number; height: number };

/** true, wenn sich zwei Rechtecke überschneiden. */
function overlaps(a: Box, b: Box): boolean {
  return !(a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y);
}

/** Die Seite darf nicht seitlich scrollen. */
async function expectNoHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(0);
}

/** Jeder sichtbare Knopf liegt vollständig im Bildschirm. */
async function expectButtonsInsideScreen(page: Page) {
  const buttons = page.getByRole("main").getByRole("button");
  const count = await buttons.count();
  for (let index = 0; index < count; index += 1) {
    const box = await buttons.nth(index).boundingBox();
    if (!box) continue;
    expect(box.x, `Knopf ${index} ragt links heraus`).toBeGreaterThanOrEqual(-1);
    expect(box.x + box.width, `Knopf ${index} ragt rechts heraus`).toBeLessThanOrEqual(PHONE.width + 1);
  }
}

/** Ein Betrag steht in einer Zeile: er ist nicht umgebrochen. */
async function expectSingleLine(page: Page, testId: string) {
  const box = await page.getByTestId(testId).first().boundingBox();
  expect(box).not.toBeNull();
  expect(box!.height, `${testId} ist umgebrochen`).toBeLessThan(32);
}

test.use({ viewport: PHONE });

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

async function mockAuth(page: Page) {
  await page.route("**/api/auth/me", (route) =>
    route.fulfill({ json: { id: 1, email: "test@example.com", is_active: true } }),
  );
  await page.route("**/api/company", (route) => route.fulfill({ json: COMPANY }));
}

test("Angebotsseite am Handy: kein seitliches Scrollen, Beträge ohne Überlappung", async ({ page }) => {
  await mockAuth(page);
  await page.route("**/api/invoices/42", (route) => route.fulfill({ json: QUOTE }));
  await page.route("**/api/customers/7", (route) =>
    route.fulfill({ json: { id: 7, name: "Sisyphos Event GmbH", email: "buchhaltung@sisyphos.example" } }),
  );

  await page.goto("/quotes/42");
  await expect(page.getByRole("heading", { name: "Angebot A-10000" })).toBeVisible();

  await expectNoHorizontalScroll(page);
  await expectButtonsInsideScreen(page);

  // Die Position: Beschreibung und Betrag dürfen sich nicht überlappen.
  const position = page.getByTestId("position-row").first();
  const description = await position.getByTestId("position-description").boundingBox();
  const amount = await position.getByTestId("position-amount").boundingBox();
  expect(description).not.toBeNull();
  expect(amount).not.toBeNull();
  expect(overlaps(description!, amount!), "Beschreibung und Betrag überlappen").toBe(false);
  await expectSingleLine(page, "position-amount");

  // Die Rate: Anlass und Betrag dürfen sich nicht überlappen.
  const rate = page.getByTestId("rate-row").first();
  const label = await rate.getByTestId("rate-label").boundingBox();
  const rateAmount = await rate.getByTestId("rate-amount").boundingBox();
  expect(label).not.toBeNull();
  expect(rateAmount).not.toBeNull();
  expect(overlaps(label!, rateAmount!), "Anlass und Betrag überlappen").toBe(false);
  await expectSingleLine(page, "rate-amount");

  // Der Betrag steht rechts, die Beschreibung links: nichts liegt übereinander.
  expect(amount!.x).toBeGreaterThanOrEqual(0);
  expect(amount!.x + amount!.width).toBeLessThanOrEqual(PHONE.width + 1);
});

test("Angebotsseite am Handy: die Kopfaktionen liegen im Menü, der Hauptknopf bleibt", async ({ page }) => {
  await mockAuth(page);
  await page.route("**/api/invoices/42", (route) => route.fulfill({ json: { ...QUOTE, status: "DRAFT" } }));
  await page.route("**/api/customers/7", (route) =>
    route.fulfill({ json: { id: 7, name: "Sisyphos Event GmbH", email: "buchhaltung@sisyphos.example" } }),
  );

  await page.goto("/quotes/42");
  const main = page.getByRole("main");

  // Der nächste Schritt ist der Hauptknopf und bleibt gut erreichbar.
  const primary = main.getByRole("button", { name: "Senden" });
  await expect(primary).toBeVisible();
  const primaryBox = await primary.boundingBox();
  expect(primaryBox).not.toBeNull();
  expect(primaryBox!.x + primaryBox!.width).toBeLessThanOrEqual(PHONE.width + 1);

  // Der Download steht am Handy im Menü statt in der Kopfzeile.
  await expect(main.getByRole("link", { name: /PDF herunterladen/ })).toHaveCount(0);
  await main.getByRole("button", { name: "Mehr" }).click();
  await expect(main.getByRole("menuitem", { name: "PDF herunterladen" })).toBeVisible();
  await expect(main.getByRole("menuitem", { name: "Vorschau" })).toBeVisible();

  await expectNoHorizontalScroll(page);
});

test("Neues Angebot am Handy: Einzelpreis und Betrag sichtbar, Speichern am Formularende", async ({ page }) => {
  let posted: Record<string, unknown> | undefined;
  await mockAuth(page);
  await page.route("**/api/customers", (route) =>
    route.fulfill({ json: [{ id: 7, name: "Sisyphos Event GmbH", email: "buchhaltung@sisyphos.example" }] }),
  );
  await page.route("**/api/invoices**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/invoices" && route.request().method() === "POST") {
      posted = route.request().postDataJSON();
      return route.fulfill({ status: 201, json: { id: 42, nr: "A-10000" } });
    }
    if (url.pathname === "/api/invoices/preview-pdf") {
      return route.fulfill({ status: 200, contentType: "application/pdf", body: "%PDF-1.4\n%%EOF" });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/quotes/new");
  await page.getByRole("combobox", { name: /Kunde/ }).selectOption({ label: "Sisyphos Event GmbH" });
  await page.getByRole("button", { name: "Neue Position" }).click();
  await page.getByLabel("Beschreibung Position 1").fill("DJ-Set");
  await page.getByLabel("Einzelpreis Position 1").fill("400");

  await expectNoHorizontalScroll(page);
  await expectButtonsInsideScreen(page);

  // Einzelpreis und Betrag stehen im Bild, nicht außerhalb.
  const unitPrice = await page.getByLabel("Einzelpreis Position 1").boundingBox();
  expect(unitPrice).not.toBeNull();
  expect(unitPrice!.x).toBeGreaterThanOrEqual(0);
  expect(unitPrice!.x + unitPrice!.width).toBeLessThanOrEqual(PHONE.width + 1);
  await expect(page.getByTestId("form-position-amount")).toContainText("400,00 €");
  const amountBox = await page.getByTestId("form-position-amount").boundingBox();
  expect(amountBox).not.toBeNull();
  expect(amountBox!.x).toBeGreaterThanOrEqual(0);
  expect(amountBox!.x + amountBox!.width).toBeLessThanOrEqual(PHONE.width + 1);
  await expectSingleLine(page, "form-position-amount");

  // Speichern ist auch am Ende des Formulars erreichbar.
  const saveEnd = page.getByTestId("quote-save-end");
  await expect(saveEnd).toBeVisible();
  await expect(saveEnd).toBeEnabled();
  await saveEnd.click();

  await expect(page).toHaveURL(/\/quotes\/42$/);
  expect(posted).toMatchObject({ document_type: "QUOTE", status: "DRAFT" });
});

test("Angebotsliste am Handy: Kunde und Betreff lesbar, kein seitliches Scrollen", async ({ page }) => {
  await mockAuth(page);
  await page.route("**/api/invoices**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/invoices" && url.searchParams.get("document_type") === "QUOTE") {
      return route.fulfill({ json: [QUOTE] });
    }
    return route.fulfill({ json: [] });
  });

  await page.goto("/quotes");
  const row = page.getByRole("main").getByRole("link", { name: /A-10000/ });
  await expect(row).toBeVisible();
  await expect(row.getByText("Sisyphos Event GmbH")).toBeVisible();
  await expect(row.getByText("DJ-Set Hammahalle, Sa auf So")).toBeVisible();

  // Nichts ist abgeschnitten: der Text passt in seinen Kasten.
  const clipped = await row
    .getByText("DJ-Set Hammahalle, Sa auf So")
    .evaluate((element) => element.scrollWidth > element.clientWidth + 1);
  expect(clipped, "Der Betreff ist abgeschnitten").toBe(false);

  await expectNoHorizontalScroll(page);
  await expectButtonsInsideScreen(page);
});

test("Positionsdialog am Handy: vollständig sichtbar, der Toast verdeckt ihn nicht", async ({ page }) => {
  await mockAuth(page);
  await page.route("**/api/invoices/42", (route) => route.fulfill({ json: { ...QUOTE, status: "DRAFT" } }));
  // Der Kunde hat keine E-Mail-Adresse: das Versenden meldet einen Fehler.
  await page.route("**/api/customers/7", (route) =>
    route.fulfill({ json: { id: 7, name: "Sisyphos Event GmbH", email: "" } }),
  );

  await page.goto("/quotes/42");
  const main = page.getByRole("main");
  await main.getByRole("button", { name: "Senden" }).click();

  const toast = page.getByText("Der Kunde hat keine E-Mail-Adresse.");
  await expect(toast).toBeVisible();
  const toastBox = (await toast.boundingBox())!;
  expect(toastBox).not.toBeNull();

  await main.getByRole("button", { name: "+ Position" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const dialogBox = (await dialog.boundingBox())!;

  // Der Dialog liegt vollständig im Bild.
  expect(dialogBox.x).toBeGreaterThanOrEqual(0);
  expect(dialogBox.y).toBeGreaterThanOrEqual(0);
  expect(dialogBox.x + dialogBox.width).toBeLessThanOrEqual(PHONE.width + 1);
  expect(dialogBox.y + dialogBox.height).toBeLessThanOrEqual(PHONE.height + 1);

  // Toast und Dialog überlappen sich nicht.
  expect(overlaps(toastBox, dialogBox), "Der Toast verdeckt den Dialog").toBe(false);
});
