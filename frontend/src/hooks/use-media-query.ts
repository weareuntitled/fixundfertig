import { useEffect, useState } from "react";

/**
 * @schema useMediaQuery
 * @purpose Passt die Oberfläche an die Fensterbreite an: am Handy wandern die Kopfaktionen
 *   in das „Mehr"-Menü, am Desktop stehen sie nebeneinander.
 * @input {string} query - Eine CSS-Medienabfrage, z. B. „(min-width: 768px)“
 * @input {boolean} fallback - Wert, wenn der Browser die Abfrage nicht kennt (z. B. im Test)
 * @output true, wenn die Abfrage gerade zutrifft
 */
export function useMediaQuery(query: string, fallback = false): boolean {
  const [matches, setMatches] = useState(() => matchesNow(query, fallback));

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const list = window.matchMedia(query);
    const update = () => setMatches(list.matches);
    update();
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, [query]);

  return matches;
}

function matchesNow(query: string, fallback: boolean): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return fallback;
  return window.matchMedia(query).matches;
}

/** Ab dem Desktop-Breakpoint (Tailwind `md`) ist Platz für mehrere Aktionen nebeneinander. */
export const WIDE_SCREEN = "(min-width: 768px)";
