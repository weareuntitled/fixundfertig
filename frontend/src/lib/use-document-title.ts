import { useEffect } from "react";

export const APP_NAME = "FixundFertig";

/** Names the browser tab "{title} · FixundFertig" while the page is shown (WCAG 2.4.2). */
export function useDocumentTitle(title: string | undefined) {
  useEffect(() => {
    if (!title) return;
    document.title = `${title} · ${APP_NAME}`;
    return () => {
      document.title = APP_NAME;
    };
  }, [title]);
}
