import { useEffect, useState } from "react";

/**
 * Returns `value` after it has remained unchanged for `delay` ms.
 * Used to throttle expensive operations (e.g. PDF-preview rendering).
 */
export function useDebounce<T>(value: T, delay: number = 800): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
