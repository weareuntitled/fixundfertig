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
]);

export type InvoiceStatus = z.infer<typeof invoiceStatusSchema>;

export const invoiceDraftSchema = z.object({
  customer_id: z.number().int().positive("Kunde erforderlich"),
  title: z.string().max(200).default("Rechnung"),
  subject: z.string().max(200).default(""),
  date: isoDate.default(""),
  delivery_date: optionalIsoDate.default(""),
  service_from: optionalIsoDate.default(""),
  service_to: optionalIsoDate.default(""),
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
});

export type InvoiceDraft = z.infer<typeof invoiceDraftSchema>;

export const emptyInvoiceDraft = (customerId: number): InvoiceDraft => ({
  customer_id: customerId,
  title: "Rechnung",
  subject: "",
  date: new Date().toISOString().slice(0, 10),
  delivery_date: "",
  service_from: "",
  service_to: "",
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
});

/**
 * Read-side mirror of `app/schemas/invoice.py:InvoiceRead`.
 * Backend liefert: id, customer_id, nr, title, date, delivery_date,
 * recipient_*, total_brutto, status, revision_nr, updated_at,
 * related_invoice_id, items (optional, default []).
 */
export const invoiceReadSchema = z.object({
  id: z.number().int(),
  customer_id: z.number().int(),
  nr: z.string().nullable().optional(),
  title: z.string().default("Rechnung"),
  subject: z.string().default(""),
  date: z.string().default(""),
  delivery_date: z.string().default(""),
  recipient_name: z.string().default(""),
  recipient_street: z.string().default(""),
  recipient_postal_code: z.string().default(""),
  recipient_city: z.string().default(""),
  total_brutto: z.number().default(0),
  status: invoiceStatusSchema.default("OPEN"),
  revision_nr: z.number().int().default(0),
  updated_at: z.string().default(""),
  related_invoice_id: z.number().int().nullable().optional(),
  payment_link_url: z.string().default(""),
  payment_provider: z.string().default(""),
  items: z.array(invoiceItemSchema).default([]),
});

export type InvoiceRead = z.infer<typeof invoiceReadSchema>;
