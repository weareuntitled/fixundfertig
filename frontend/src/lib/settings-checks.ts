/** Checks and live examples for the settings page. They mirror what the backend does with the values. */

export function isValidIban(raw: string): boolean {
  const iban = raw.replace(/\s+/g, "").toUpperCase();
  if (!/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(iban)) return false;
  const rearranged = iban.slice(4) + iban.slice(0, 4);
  let remainder = 0;
  for (const char of rearranged) {
    const value = char >= "A" ? char.charCodeAt(0) - 55 : Number(char);
    remainder = (remainder * (value >= 10 ? 100 : 10) + value) % 97;
  }
  return remainder === 1;
}

export function isValidVatId(raw: string): boolean {
  const id = raw.replace(/\s+/g, "").toUpperCase();
  if (id.startsWith("DE")) return /^DE\d{9}$/.test(id);
  return /^[A-Z]{2}[A-Z0-9]{2,12}$/.test(id);
}

export function isValidEmail(raw: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(raw.trim());
}

type TemplateValues = Record<string, string | number>;

/** Like Python's str.format_map with unknown keys left empty. */
export function expandTemplate(template: string, values: TemplateValues): string {
  return template.replace(/\{(\w+)\}/g, (_match, key: string) => String(values[key] ?? ""));
}

const SAMPLE = { customer_code: "CLUB", customer_kdnr: 7 };

export function invoiceNumberExample(template: string, nextNumber: number, isoDate: string): string {
  const pattern = template.trim() || "{seq}";
  return expandTemplate(pattern, { ...SAMPLE, seq: nextNumber, date: isoDate });
}

export function invoiceFilenameExample(template: string, invoiceNumber: string, isoDate: string): string {
  const pattern = template.trim() || "rechnung_{nr}";
  const seq = Number.parseInt(invoiceNumber, 10);
  const expanded = expandTemplate(pattern, {
    ...SAMPLE,
    nr: invoiceNumber,
    seq: Number.isNaN(seq) ? "" : seq,
    date: isoDate,
  });
  const cleaned = expanded.trim().replace(/[^\p{L}\p{N}_.-]+/gu, "_") || "rechnung";
  return cleaned.toLowerCase().endsWith(".pdf") ? cleaned : `${cleaned}.pdf`;
}
