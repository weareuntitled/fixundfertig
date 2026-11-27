import { z } from "zod";

/**
 * Zod-Mirror des Backend `app/schemas/invoice.py:InvoiceDraft`.
 * Source of Truth ist das Backend-Pydantic-Schema; dieses Zod-Schema
 * wird per `satisfies z.ZodType<InvoiceDraft>` validiert (siehe Backend-Tests).
 *
 * Wenn Backend oder Frontend divergieren, bricht entweder der Backend-Test
 * (`test_invoice_schemas.py`) oder der TypeScript-Build. So bleibt der Kontrakt
 * stabil ohne doppelte Definition.
 */

export const invoiceItemSchema = z.object({
  id: z.number().int().optional(),
  description: z.string().min(1, "Beschreibung erforderlich").max(500),
  quantity: z.number().positive("Menge muss > 0 sein").lte(100_000),
  unit_price: z.number().nonnegative("Preis darf nicht negativ sein").lte(1_000_000_000),
});

export type InvoiceItem = z.infer<typeof invoiceItemSchema>;

const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Datum muss YYYY-MM-DD sein")
  .or(z.literal(""));

const optionalIsoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/)
  .or(z.literal(""));

export const invoiceStatusSchema = z.enum([
  "DRAFT",
  "OPEN",
  "SENT",
  "PAID",
  "FINALIZED",
  "CANCELLED",
  // Nur Angebote (siehe lib/quote-status.ts)
  "ACCEPTED",
  "REJECTED",
]);

export type InvoiceStatus = z.infer<typeof invoiceStatusSchema>;

/** Rechnung oder Angebot; beide laufen über `/api/invoices`. */
export const documentTypeSchema = z.enum(["INVOICE", "QUOTE"]);

export type DocumentType = z.infer<typeof documentTypeSchema>;

/** Tage zwischen Angebotsdatum und „gültig bis“, wenn nichts anderes gewählt ist. */
export const QUOTE_VALIDITY_DAYS = 30;

/** ISO-Datum plus `days` Tage, oder "" wenn das Datum fehlt. */
export function addDaysIso(isoDate: string, days: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate);
  if (!match) return "";
  const d = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + days));
  return d.toISOString().slice(0, 10);
}

/** Eine Rate des Zahlungsplans eines Angebots: Prozent vom Bruttobetrag und Anlass. */
export const paymentInstallmentSchema = z.object({
  percent: z.number().positive("Prozent muss > 0 sein").lte(100),
  label: z.string().max(200).default(""),
});

export type PaymentInstallment = z.infer<typeof paymentInstallmentSchema>;

/** Rate mit Betrag, vom Backend aus dem Bruttobetrag berechnet (nicht gespeichert). */
export const paymentInstallmentReadSchema = paymentInstallmentSchema.extend({
  amount: z.number().default(0),
});

export type PaymentInstallmentRead = z.infer<typeof paymentInstallmentReadSchema>;

export const invoiceDraftSchema = z.object({
  customer_id: z.number().int().positive("Kunde erforderlich"),
  document_type: documentTypeSchema.default("INVOICE"),
  title: z.string().max(200).default("Rechnung"),
  subject: z.string().max(200).default(""),
  date: isoDate.default(""),
  delivery_date: optionalIsoDate.default(""),
  service_from: optionalIsoDate.default(""),
  service_to: optionalIsoDate.default(""),
  valid_until: optionalIsoDate.default(""),
  recipient_name: z.string().max(200).default(""),
  recipient_street: z.string().max(200).default(""),
  recipient_postal_code: z.string().max(20).default(""),
  recipient_city: z.string().max(100).default(""),
  vat_rate: z.number().nonnegative().lte(100).default(19.0),
  ust_enabled: z.boolean().default(true),
  intro_text: z.string().max(2000).default(""),
  items: z.array(invoiceItemSchema).default([]),
  notes: z.string().max(2000).default(""),
  status: invoiceStatusSchema.default("OPEN"),
  payment_plan: z.array(paymentInstallmentSchema).default([]),
});

export type InvoiceDraft = z.infer<typeof invoiceDraftSchema>;

export const emptyInvoiceDraft = (customerId: number): InvoiceDraft => ({
  customer_id: customerId,
  document_type: "INVOICE",
  title: "Rechnung",
  subject: "",
  date: new Date().toISOString().slice(0, 10),
  delivery_date: "",
  service_from: "",
  service_to: "",
  valid_until: "",
  recipient_name: "",
  recipient_street: "",
  recipient_postal_code: "",
  recipient_city: "",
  vat_rate: 19.0,
  ust_enabled: true,
  intro_text: "",
  items: [],
  notes: "",
  status: "OPEN",
  payment_plan: [],
});

/** Ein neues Angebot: Entwurf, „gültig bis“ = Angebotsdatum plus 30 Tage. */
export const emptyQuoteDraft = (
  customerId: number,
  date: string = new Date().toISOString().slice(0, 10),
): InvoiceDraft => ({
  ...emptyInvoiceDraft(customerId),
  document_type: "QUOTE",
  title: "Angebot",
  date,
  valid_until: addDaysIso(date, QUOTE_VALIDITY_DAYS),
  status: "DRAFT",
});

export const invoiceAttachmentSchema = z.object({
  id: z.number().int(),
  document_id: z.number().int(),
  title: z.string().default(""),
  filename: z.string().default(""),
  mime: z.string().default(""),
  size: z.number().int().default(0),
  created_at: z.string().default(""),
});

export type InvoiceAttachment = z.infer<typeof invoiceAttachmentSchema>;

/** Mirror of `app/schemas/invoice.py:LinkedInvoiceRead`. */
export const linkedInvoiceSchema = z.object({
  id: z.number().int(),
  nr: z.string().nullable().optional(),
  status: invoiceStatusSchema.default("DRAFT"),
  total_brutto: z.number().default(0),
  /** Abschlagsrechnung: Index der abgerechneten Rate im Zahlungsplan. */
  installment_index: z.number().int().nullable().default(null),
  is_down_payment: z.boolean().default(false),
  /** Schlussrechnung: eigener Marker, keine Abschlagsrechnung. */
  is_final_invoice: z.boolean().default(false),
});

export type LinkedInvoice = z.infer<typeof linkedInvoiceSchema>;

/** Mirror of `app/schemas/invoice.py:BillingActionRead` — erlaubt oder gesperrt mit Grund. */
export const billingActionSchema = z.object({
  allowed: z.boolean().default(true),
  reason: z.string().default(""),
  invoice_id: z.number().int().nullable().default(null),
  invoice_nr: z.string().nullable().default(null),
});

export type BillingAction = z.infer<typeof billingActionSchema>;

/** Mirror of `app/schemas/invoice.py:QuoteBillingRead`. */
export const quoteBillingSchema = z.object({
  convert: billingActionSchema,
  down_payment: billingActionSchema,
  final_invoice: billingActionSchema,
  /** Gesendet, aber nicht angenommen: Abrechnen nimmt das Angebot an. */
  requires_acceptance: z.boolean().default(false),
});

export type QuoteBilling = z.infer<typeof quoteBillingSchema>;

/** Mirror of `app/schemas/invoice.py:QuoteSettlementRead` — der Abrechnungsstand. */
export const quoteSettlementSchema = z.object({
  /** Bruttosumme der gestellten Rechnungen zum Angebot. */
  billed_brutto: z.number().default(0),
  /** Bruttobetrag des Angebots. */
  total_brutto: z.number().default(0),
  /** Was noch offen ist. */
  open_brutto: z.number().default(0),
  /** Zahl der gestellten Rechnungen zum Angebot. */
  billed_count: z.number().int().default(0),
});

export type QuoteSettlement = z.infer<typeof quoteSettlementSchema>;

export const finalBreakdownSchema = z.object({
  net: z.number(), tax: z.number(), gross: z.number(),
  deductions: z.array(z.object({ id: z.number(), nr: z.string(), date: z.string(), net: z.number(), tax: z.number(), total: z.number() })),
  rest_net: z.number(), rest_tax: z.number(), rest: z.number(),
});
export type FinalBreakdownRead = z.infer<typeof finalBreakdownSchema>;

/** Mirror of `app/schemas/invoice.py:TotalsRead` — die Belegsummen aus dem Backend. */
export const totalsSchema = z.object({
  net: z.number(),
  /** Steuersatz in Prozent; 0 ohne USt (Kleinunternehmer, 0 %). */
  vat_rate: z.number(),
  tax: z.number(),
  gross: z.number(),
  /** Zahlbarer Betrag, entspricht `total_brutto`. */
  payable: z.number(),
});
export type TotalsRead = z.infer<typeof totalsSchema>;

/**
 * Read-side mirror of `app/schemas/invoice.py:InvoiceRead`.
 * Backend liefert: id, customer_id, nr, title, date, delivery_date,
 * recipient_*, total_brutto, status, revision_nr, updated_at,
 * related_invoice_id, items (optional, default []).
 */
export const invoiceReadSchema = z.object({
  id: z.number().int(),
  customer_id: z.number().int(),
  document_type: documentTypeSchema.default("INVOICE"),
  nr: z.string().nullable().optional(),
  title: z.string().default("Rechnung"),
  subject: z.string().default(""),
  intro_text: z.string().default(""),
  date: z.string().default(""),
  delivery_date: z.string().default(""),
  valid_until: z.string().default(""),
  recipient_name: z.string().default(""),
  recipient_street: z.string().default(""),
  recipient_postal_code: z.string().default(""),
  recipient_city: z.string().default(""),
  legacy: z.boolean().default(false),
  total_brutto: z.number().default(0),
  /** Nettobetrag aus den Positionen. */
  total_net: z.number().default(0),
  /** Steuersatz des Dokuments in Prozent. */
  vat_rate: z.number().default(0),
  /** Belegsummen; null, wenn die Abzüge einer Schlussrechnung beschädigt sind. */
  totals: totalsSchema.nullable().default(null),
  status: invoiceStatusSchema.default("OPEN"),
  revision_nr: z.number().int().default(0),
  updated_at: z.string().default(""),
  related_invoice_id: z.number().int().nullable().optional(),
  /** Rechnung aus einem Angebot: dessen ID und Nummer. */
  quote_id: z.number().int().nullable().default(null),
  quote_nr: z.string().nullable().default(null),
  /** Abschlagsrechnung: Index der abgerechneten Rate, sonst null. */
  down_payment_index: z.number().int().nullable().default(null),
  /** Schlussrechnung: eigener Marker. */
  is_final_invoice: z.boolean().default(false),
  final_breakdown: finalBreakdownSchema.nullable().default(null),
  /** Angebot: die daraus entstandenen Rechnungen. */
  linked_invoices: z.array(linkedInvoiceSchema).default([]),
  payment_link_url: z.string().default(""),
  payment_provider: z.string().default(""),
  items: z.array(invoiceItemSchema).default([]),
  attachments: z.array(invoiceAttachmentSchema).default([]),
  payment_plan: z.array(paymentInstallmentReadSchema).default([]),
  /** Angebot: die erlaubten Abrechnungsaktionen mit dem Grund für gesperrte. */
  billing: quoteBillingSchema.nullable().default(null),
  /** Angebot: der Abrechnungsstand (abgerechnet, gesamt, offen). */
  settlement: quoteSettlementSchema.nullable().default(null),
});

export type InvoiceRead = z.infer<typeof invoiceReadSchema>;
