/**
 * @schema useDialogFocus
 * @purpose The keyboard contract of every modal dialog: on open the focus moves into the dialog
 * (an element with autoFocus wins, else the first control), Tab and Shift+Tab stay inside,
 * focus that lands behind the dialog is pulled back, Escape calls onEscape, and on close
 * the focus returns to the element that opened it.
 * @output A ref for the dialog element.
 */
import { useEffect, useRef } from "react";

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "iframe",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function focusables(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => {
    const check = (el as HTMLElement & { checkVisibility?: () => boolean }).checkVisibility;
    return check ? check.call(el) : true;
  });
}

interface Options {
  /** Called on Escape. Leave it out while a running step must not be interrupted. */
  onEscape?: () => void;
  suspended?: boolean;
}

export function useDialogFocus<T extends HTMLElement = HTMLElement>(open: boolean, { onEscape, suspended = false }: Options = {}) {
  const ref = useRef<T>(null);
  const onEscapeRef = useRef(onEscape);
  onEscapeRef.current = onEscape;
  const suspendedRef = useRef(suspended);
  suspendedRef.current = suspended;
  // Captured while rendering the opening frame: by the time effects run, autoFocus has already moved focus.
  const triggerRef = useRef<HTMLElement | null>(null);
  const wasOpen = useRef(false);
  if (open && !wasOpen.current && typeof document !== "undefined") {
    triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }
  wasOpen.current = open;

  useEffect(() => {
    if (!open || suspended) return;
    const trigger = triggerRef.current;
    const container = ref.current;
    if (!container) return;

    const focusFirst = () => {
      const target = focusables(container)[0] ?? container;
      if (target === container && !container.hasAttribute("tabindex")) container.setAttribute("tabindex", "-1");
      target.focus();
    };
    // autoFocus (set by React during commit) and a focused field inside win.
    if (!container.contains(document.activeElement)) focusFirst();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (onEscapeRef.current) {
          event.stopPropagation();
          onEscapeRef.current();
        }
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables(container);
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !container.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !container.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };
    const onFocusIn = (event: FocusEvent) => {
      if (event.target instanceof Node && !container.contains(event.target)) focusFirst();
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("focusin", onFocusIn);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("focusin", onFocusIn);
      if (!suspendedRef.current && trigger && trigger.isConnected) trigger.focus();
    };
  }, [open, suspended]);

  return ref;
}
