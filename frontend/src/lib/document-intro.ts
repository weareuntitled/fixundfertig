/**
 * Standard-Einleitungstexte der Dokumente.
 *
 * Spiegel von `app/services/invoice_pdf_draw.py` (`QUOTE_INTRO`, `INVOICE_INTRO`).
 * Das Backend ist die Quelle der Wahrheit; der Test
 * `tests/test_quote_intro_text.py` vergleicht beide Texte, damit sie nicht auseinanderlaufen.
 */
export const QUOTE_INTRO = "Vielen Dank für Ihre Anfrage. Hiermit biete ich folgende Leistungen an.";
export const INVOICE_INTRO = "Vielen Dank für den Auftrag. Hiermit stelle ich folgende Leistungen in Rechnung.";

/** Der Standardtext, den das PDF ohne eigenen Einleitungstext druckt. */
export function defaultIntroText(documentType: "QUOTE" | "INVOICE"): string {
  return documentType === "QUOTE" ? QUOTE_INTRO : INVOICE_INTRO;
}
