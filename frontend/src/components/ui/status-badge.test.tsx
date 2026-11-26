import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./status-badge";

const TOKENS = readFileSync(resolve(__dirname, "../../styles/tokens.css"), "utf8");

/** Resolves a design token like --color-status-open down to its hex value. */
function token(name: string): string {
  const match = TOKENS.match(new RegExp(`${name}:\\s*([^;]+);`));
  if (!match) throw new Error(`token ${name} missing`);
  const value = match[1].trim();
  const ref = value.match(/^var\((--[\w-]+)\)$/);
  return ref ? token(ref[1]) : value;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function badgeColors(status: string) {
  const { container } = render(<StatusBadge status={status} />);
  const cls = container.firstElementChild!.className;
  const text = cls.match(/text-\[var\((--[\w-]+)\)\]/)![1];
  const bg = cls.match(/bg-\[var\((--[\w-]+)\)\]/)![1];
  return { text: token(text), bg: token(bg) };
}

const STATUSES = ["DRAFT", "OPEN", "SENT", "PAID", "FINALIZED", "CANCELLED", "ACCEPTED", "REJECTED", "EXPIRED"];

describe("StatusBadge", () => {
  it.each(STATUSES)("%s text reaches 4.5:1 on its background", (status) => {
    const { text, bg } = badgeColors(status);
    expect(contrast(text, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it("shows Abgelaufen in its own colour, not the one of Offen", () => {
    expect(badgeColors("EXPIRED")).not.toEqual(badgeColors("OPEN"));
    expect(badgeColors("EXPIRED")).not.toEqual(badgeColors("SENT"));
  });

  it("muted and danger text reach 4.5:1 on white and on the page background", () => {
    for (const name of ["--color-text-muted", "--color-text-tertiary", "--color-text-secondary", "--color-text-danger", "--color-text-link", "--color-brand-text"]) {
      expect(contrast(token(name), "#ffffff"), name).toBeGreaterThanOrEqual(4.5);
      expect(contrast(token(name), token("--color-background")), name).toBeGreaterThanOrEqual(4.5);
    }
  });
});
