import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge, STATUS_LABELS } from "./status-badge";

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
  const badge = container.firstElementChild!;
  const cls = badge.className;
  const text = cls.match(/text-\[var\((--[\w-]+)\)\]/)![1];
  const bg = cls.match(/bg-\[var\((--[\w-]+)\)\]/)![1];
  const dot = badge.querySelector("span > span")!.className.match(/bg-\[var\((--[\w-]+)\)\]/)![1];
  return { text: token(text), bg: token(bg), dot: token(dot) };
}

const STATUSES = ["DRAFT", "OPEN", "SENT", "PAID", "FINALIZED", "CANCELLED", "ACCEPTED", "REJECTED", "EXPIRED"];

describe("StatusBadge", () => {
  it.each(STATUSES)("%s text reaches 4.5:1 on its background", (status) => {
    const { text, bg } = badgeColors(status);
    expect(contrast(text, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(STATUSES)("%s dot reaches 3:1 on its background", (status) => {
    const { dot, bg } = badgeColors(status);
    expect(contrast(dot, bg)).toBeGreaterThanOrEqual(3);
  });

  it("shows Abgelaufen in its own colour, not the one of Gestellt", () => {
    expect(badgeColors("EXPIRED")).not.toEqual(badgeColors("OPEN"));
    expect(badgeColors("EXPIRED")).not.toEqual(badgeColors("SENT"));
  });

  it("muted and danger text reach 4.5:1 on white and on the page background", () => {
    for (const name of ["--color-text-muted", "--color-text-tertiary", "--color-text-secondary", "--color-text-danger", "--color-text-link", "--color-text-success", "--color-text-warning", "--color-brand-text"]) {
      expect(contrast(token(name), "#ffffff"), name).toBeGreaterThanOrEqual(4.5);
      expect(contrast(token(name), token("--color-background")), name).toBeGreaterThanOrEqual(4.5);
    }
  });
});

/**
 * Eine Rechnung gilt als gestellt, sobald sie weder Entwurf noch storniert ist.
 * Für diesen Zustand gibt es genau ein Wort in der Oberfläche.
 */
describe("StatusBadge wording", () => {
  it("calls an issued invoice 'Gestellt'", () => {
    render(<StatusBadge status="OPEN" />);
    expect(screen.getByText("Gestellt")).toBeInTheDocument();
    expect(screen.queryByText("Offen")).toBeNull();
  });

  it("calls a finalized invoice 'Gestellt' too", () => {
    render(<StatusBadge status="FINALIZED" />);
    expect(screen.getByText("Gestellt")).toBeInTheDocument();
    expect(screen.queryByText("Finalisiert")).toBeNull();
  });

  it("uses the same word in the labels of the status lists", () => {
    expect(STATUS_LABELS.OPEN).toBe("Gestellt");
    expect(STATUS_LABELS.FINALIZED).toBe("Gestellt");
    expect(STATUS_LABELS.DRAFT).toBe("Entwurf");
    expect(STATUS_LABELS.CANCELLED).toBe("Storniert");
  });
});
