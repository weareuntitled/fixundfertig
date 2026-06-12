import { describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useDebounce } from "./use-debounce";

describe("useDebounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebounce("hello", 500));
    expect(result.current).toBe("hello");
  });

  it("does not update before the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 500), {
      initialProps: { value: "first" },
    });
    rerender({ value: "second" });
    act(() => {
      vi.advanceTimersByTime(499);
    });
    expect(result.current).toBe("first");
  });

  it("updates once the delay elapses", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 500), {
      initialProps: { value: "first" },
    });
    rerender({ value: "second" });
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current).toBe("second");
  });

  it("resets the timer when the value changes again", () => {
    const { result, rerender } = renderHook(({ value }) => useDebounce(value, 500), {
      initialProps: { value: "a" },
    });
    rerender({ value: "b" });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    rerender({ value: "c" });
    act(() => {
      vi.advanceTimersByTime(300);
    });
    // Only 600ms have passed since the LAST change, not the first — so still old value
    expect(result.current).toBe("a");
    act(() => {
      vi.advanceTimersByTime(200);
    });
    // 500ms since last change — now it should be the latest
    expect(result.current).toBe("c");
  });
});
