import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * WCAG 2.1 AA on the quote and invoice pages (#500): axe must not find
 * "serious" or "critical" violations. All API calls are mocked.
 */

const ME = { id: 1, email: "test@example.com", is_active: true };
const COMPANY = {
  id: 1, name: "Daniel S.", first_name: "Daniel", last_name: "Beispiel", business_type: "DJ / Producer",
  is_small_business: false, street: "Musterstraße 1", postal_code: "10115", city: "Berlin", country: "Deutschland",
  email: "", phone: "", iban: "", bic: "", bank_name: "", account_holder: "", tax_id: "", vat_id: "",
  smtp_server: "", smtp_port: 587, smtp_user: "", smtp_password: "", default_sender_email: "",
  next_invoice_nr: 10058, invoice_number_template: "RE-{seq}", invoice_filename_template: "rechnung_{nr}",
  logo_url: "", payment_enabled: false,
};
const QUOTES = [
  { id: 42, customer_id: 7, document_type: "QUOTE", nr: "A-10000", title: "Website", date: "2026-10-23",
    valid_until: "2099-11-22", recipient_name: "Sisyphos Event GmbH", total_brutto: 4760, status: "ACCEPTED" },
  { id: 41, customer_id: 7, document_type: "QUOTE", nr: "A-09999", title: "Logo", date: "2026-09-01",
    valid_until: "2026-10-01", recipient_name: "Sisyphos Event GmbH", total_brutto: 714, status: "SENT" },
  { id: 40, customer_id: 7, document_type: "QUOTE", nr: "A-09998", title: "Flyer", date: "2026-09-01",
    valid_until: "2099-10-01", recipient_name: "Sisyphos Event GmbH", total_brutto: 300, status: "DRAFT" },
  { id: 39, customer_id: 7, document_type: "QUOTE", nr: "A-09997", title: "Shop", date: "2026-09-01",
    valid_until: "2099-10-01", recipient_name: "Sisyphos Event GmbH", total_brutto: 900, status: "REJECTED" },
];
const DOWN_PAYMENT = {
  id: 43, customer_id: 7, document_type: "INVOICE", nr: "10000", title: "Abschlagsrechnung", date: "2026-10-24",
  recipient_name: "Sisyphos Event GmbH", total_brutto: 2380, total_net: 2000, vat_rate: 19, status: "OPEN",
  quote_id: 42, quote_nr: "A-10000", down_payment_index: 0, installment_index: 0,
  is_down_payment: true, is_final_invoice: false,
  items: [{ id: 2, description: "Abschlag 50 % gemäß Angebot A-10000 – bei Auftrag", quantity: 1, unit_price: 2000 }],
};
const QUOTE = {
  ...QUOTES[0],
  total_net: 4000,
  vat_rate: 19,
  items: [
    { id: 1, description: "SEO-Grundeinrichtung für die neue Seite", quantity: 1, unit_price: 4000 },
  ],
  payment_plan: [
    { percent: 50, label: "bei Auftrag", amount: 2380 },
    { percent: 50, label: "nach Livegang", amount: 2380 },
  ],
  settlement: { billed_brutto: 2380, total_brutto: 4760, open_brutto: 2380, billed_count: 1 },
  billing: {
    convert: { allowed: false, reason: "Es gibt schon eine Abschlagsrechnung.", invoice_id: null, invoice_nr: null },
    down_payment: { allowed: false, reason: "Es gibt schon eine Abschlagsrechnung.", invoice_id: null, invoice_nr: null },
    final_invoice: { allowed: true, reason: "", invoice_id: null, invoice_nr: null },
    requires_acceptance: false,
  },
  linked_invoices: [DOWN_PAYMENT],
};

async function mockApi(page: Page) {
  await page.route("**/api/**", (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/auth/me") return route.fulfill({ json: ME });
    if (path === "/api/company") return route.fulfill({ json: COMPANY });
    if (path === "/api/customers") return route.fulfill({ json: [{ id: 7, name: "Sisyphos Event GmbH", email: "a@b.example" }] });
    if (path === "/api/customers/7") return route.fulfill({ json: { id: 7, kdnr: 1, name: "Sisyphos Event GmbH", email: "a@b.example" } });
    if (path.endsWith("preview-pdf")) return route.fulfill({ contentType: "application/pdf", body: "%PDF-1.4\n%%EOF" });
    if (path === "/api/invoices/42") return route.fulfill({ json: QUOTE });
    if (path === "/api/invoices/43") return route.fulfill({ json: DOWN_PAYMENT });
    if (path === "/api/invoices" && url.searchParams.get("document_type") === "QUOTE") return route.fulfill({ json: QUOTES });
    return route.fulfill({ json: [] });
  });
}

/**
 * axe runs every rule; only "serious" and "critical" fail the test.
 * The report lists every violation so a new one is easy to place.
 */
async function expectNoSeriousViolations(page: Page) {
  const results = await new AxeBuilder({ page }).analyze();
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const report = results.violations.map((v) => `[${v.impact}] ${v.id}`);
  expect(blocking, `axe-Verstöße: ${report.join(", ")}`).toEqual([]);
}

test.beforeEach(async ({ page }) => {
  // Fade-in animations would let axe measure half-transparent text.
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mockApi(page);
});

test("a11y: Angebotsliste", async ({ page }) => {
  await page.goto("/quotes");
  await expect(page.getByRole("heading", { level: 1, name: "Angebote" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("link", { name: /A-10000/ })).toBeVisible();
  await expect(page).toHaveTitle("Angebote · FixundFertig");
  await expectNoSeriousViolations(page);
});

test("a11y: Angebotsseite", async ({ page }) => {
  await page.goto("/quotes/42");
  await expect(page.getByRole("heading", { level: 1, name: "Angebot A-10000" })).toBeVisible();
  await expect(page).toHaveTitle("Angebot A-10000 · FixundFertig");
  // Die Seite trägt Positionen, Zahlungsplan und Abrechnungsstand.
  await expect(page.getByTestId("position-description").first()).toBeVisible();
  await expectNoSeriousViolations(page);
});

test("a11y: Neues Angebot", async ({ page }) => {
  await page.goto("/quotes/new");
  await expect(page.getByRole("heading", { level: 1, name: "Neues Angebot" })).toBeVisible();
  await expect(page).toHaveTitle("Neues Angebot · FixundFertig");
  await expectNoSeriousViolations(page);
});

test("a11y: Rechnungsseite", async ({ page }) => {
  await page.goto("/invoices/43");
  await expect(page.getByRole("heading", { level: 1, name: /Abschlagsrechnung 10000/ })).toBeVisible();
  await expect(page).toHaveTitle("Rechnung 10000 · FixundFertig");
  await expectNoSeriousViolations(page);
});

/**
 * A11Y-01: Der Fokusring war ein Schein mit 12 % Deckkraft und in der
 * Seitenleiste gar nicht sichtbar. Jetzt ist es eine Outline, die auch neben
 * eigenen shadow-Klassen sichtbar bleibt (mindestens 3:1 gegen den Grund).
 */
test("Fokus: die Seitenleiste zeigt beim Tab einen sichtbaren Ring", async ({ page }) => {
  await page.goto("/quotes");
  await expect(page.getByRole("heading", { level: 1, name: "Angebote" })).toBeVisible();
  await page.keyboard.press("Tab");
  // Der Ring läuft mit (transition-all animiert outline-color mit).
  await page.waitForTimeout(400);
  const ring = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return null;
    const style = getComputedStyle(el);
    let background = "rgba(0, 0, 0, 0)";
    for (let node: HTMLElement | null = el; node; node = node.parentElement) {
      const value = getComputedStyle(node).backgroundColor;
      if (value && !value.startsWith("rgba(0, 0, 0, 0)")) { background = value; break; }
    }
    return {
      name: el.textContent?.trim().slice(0, 40) ?? "",
      width: style.outlineWidth,
      style: style.outlineStyle,
      color: style.outlineColor,
      background,
    };
  });
  expect(ring, "nichts war fokussiert").not.toBeNull();
  expect(ring!.style, `Fokusring fehlt bei „${ring!.name}“`).toBe("solid");
  expect(parseFloat(ring!.width)).toBeGreaterThanOrEqual(2);
  expect(contrast(ring!.color, ring!.background)).toBeGreaterThanOrEqual(3);
});

/** Kontrastverhältnis zweier CSS-Farben nach WCAG 2.1. */
function contrast(foreground: string, background: string): number {
  const luminance = (color: string) => {
    const [r, g, b] = color.match(/[\d.]+/g)!.slice(0, 3).map((v) => Number(v) / 255);
    const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  };
  const [hi, lo] = [luminance(foreground), luminance(background)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
