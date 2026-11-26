import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NotificationProvider, useNotification } from "./use-notifications";

function Trigger() {
  const { notify } = useNotification();
  return (
    <>
      <button type="button" onClick={() => notify("success", "Angebot gespeichert")}>ok</button>
      <button type="button" onClick={() => notify("error", "E-Mail konnte nicht gesendet werden")}>fehler</button>
    </>
  );
}

function setup() {
  render(
    <NotificationProvider>
      <Trigger />
    </NotificationProvider>,
  );
}

describe("Toasts", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("announces success politely and lets it go after a while", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "ok" }));
    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveTextContent("Angebot gespeichert");
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.queryByText("Angebot gespeichert")).toBeNull();
  });

  it("announces errors as alert and keeps them until closed", () => {
    setup();
    fireEvent.click(screen.getByRole("button", { name: "fehler" }));
    expect(screen.getByRole("alert")).toHaveTextContent("E-Mail konnte nicht gesendet werden");
    act(() => vi.advanceTimersByTime(60_000));
    expect(screen.getByRole("alert")).toHaveTextContent("E-Mail konnte nicht gesendet werden");
    fireEvent.click(screen.getByRole("button", { name: "Meldung schließen" }));
    expect(screen.queryByText("E-Mail konnte nicht gesendet werden")).toBeNull();
  });
});
