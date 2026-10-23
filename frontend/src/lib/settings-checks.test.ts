import { describe, expect, it } from "vitest";
import {
  invoiceFilenameExample,
  invoiceNumberExample,
  isValidEmail,
  isValidIban,
  isValidVatId,
} from "./settings-checks";

describe("isValidIban", () => {
  it("accepts a correct IBAN with or without spaces", () => {
    expect(isValidIban("DE89370400440532013000")).toBe(true);
    expect(isValidIban("de89 3704 0044 0532 0130 00")).toBe(true);
  });
  it("rejects a wrong check digit or a wrong shape", () => {
    expect(isValidIban("DE89370400440532013001")).toBe(false);
    expect(isValidIban("DE00 0000 0000 0000 0000 00")).toBe(false);
    expect(isValidIban("12345")).toBe(false);
  });
});

describe("isValidVatId", () => {
  it("checks German VAT IDs strictly", () => {
    expect(isValidVatId("DE359551929")).toBe(true);
    expect(isValidVatId("DE35955192")).toBe(false);
  });
  it("accepts the general shape for other countries", () => {
    expect(isValidVatId("ATU12345678")).toBe(true);
    expect(isValidVatId("1234")).toBe(false);
  });
});

describe("isValidEmail", () => {
  it("accepts and rejects", () => {
    expect(isValidEmail("daniel@example.com")).toBe(true);
    expect(isValidEmail("daniel@example")).toBe(false);
  });
});

describe("invoiceNumberExample", () => {
  it("fills the placeholders like the backend", () => {
    expect(invoiceNumberExample("RE-{date}-{seq}", 10058, "2026-10-23")).toBe("RE-2026-10-23-10058");
    expect(invoiceNumberExample("{customer_code}-{seq}", 7, "2026-10-23")).toBe("CLUB-7");
  });
  it("uses {seq} when the template is empty and leaves unknown keys empty", () => {
    expect(invoiceNumberExample("  ", 42, "2026-10-23")).toBe("42");
    expect(invoiceNumberExample("X{nope}-{seq}", 1, "2026-10-23")).toBe("X-1");
  });
});

describe("invoiceFilenameExample", () => {
  it("cleans the name and appends .pdf", () => {
    expect(invoiceFilenameExample("{nr}_{customer_code}", "10058", "2026-10-23")).toBe("10058_CLUB.pdf");
    expect(invoiceFilenameExample("Rechnung {nr}", "10058", "2026-10-23")).toBe("Rechnung_10058.pdf");
    expect(invoiceFilenameExample("", "10058", "2026-10-23")).toBe("rechnung_10058.pdf");
  });
});
