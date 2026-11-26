import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderInRouter } from "@/test/render-in-router";
import { PageHeader } from "./page-header";

describe("PageHeader", () => {
  it("is the page's h1 and names the browser tab", async () => {
    await renderInRouter(<PageHeader title="Neues Angebot" backTo="/quotes" backLabel="Angebote" />);
    expect(screen.getByRole("heading", { level: 1, name: "Neues Angebot" })).toBeTruthy();
    expect(document.title).toBe("Neues Angebot · FixundFertig");
  });

  it("takes a plain tab title when the heading carries markup", async () => {
    await renderInRouter(<PageHeader title={<span>Angebot A-1</span>} documentTitle="Angebot A-1" />);
    expect(screen.getByRole("heading", { level: 1, name: "Angebot A-1" })).toBeTruthy();
    expect(document.title).toBe("Angebot A-1 · FixundFertig");
  });

  it("gives the back link a 44 px touch target", async () => {
    await renderInRouter(<PageHeader title="X" backTo="/quotes" backLabel="Angebote" />);
    expect(screen.getByRole("link", { name: "Angebote" }).className).toContain("min-h-[44px]");
  });
});
