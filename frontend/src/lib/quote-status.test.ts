import { describe, expect, it } from "vitest";
import { isQuoteLocked, quoteDisplayStatus } from "./quote-status";

const today = "2026-11-25";

describe("quoteDisplayStatus", () => {
  it("shows a sent quote past its valid-until date as expired", () => {
    expect(quoteDisplayStatus({ status: "SENT", valid_until: "2026-11-24" }, today)).toBe("EXPIRED");
  });

  it("keeps a sent quote valid on its last day", () => {
    expect(quoteDisplayStatus({ status: "SENT", valid_until: "2026-11-25" }, today)).toBe("SENT");
  });

  it("keeps a sent quote without valid-until date as sent", () => {
    expect(quoteDisplayStatus({ status: "SENT", valid_until: "" }, today)).toBe("SENT");
  });

  it.each(["DRAFT", "ACCEPTED", "REJECTED"] as const)("never marks a %s quote as expired", (status) => {
    expect(quoteDisplayStatus({ status, valid_until: "2020-01-01" }, today)).toBe(status);
  });
});

describe("isQuoteLocked", () => {
  it("locks only accepted quotes", () => {
    expect(isQuoteLocked({ status: "ACCEPTED" })).toBe(true);
    expect(isQuoteLocked({ status: "SENT" })).toBe(false);
    expect(isQuoteLocked({ status: "REJECTED" })).toBe(false);
  });
});
