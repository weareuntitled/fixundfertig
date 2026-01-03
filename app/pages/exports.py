from __future__ import annotations
from ._shared import *

# Auto generated page renderer

def render_exports(session, comp: Company) -> None:
    ui.label("Exporte").classes(C_PAGE_TITLE + " mb-4")

    def run_export(action, label: str):
        ui.notify("Wird vorbereitet…")
        try:
            with get_session() as s:
                path = action(s)
            if path and os.path.exists(path):
                ui.download(path)
                ui.notify(f"{label} bereit", color="green")
            else:
                ui.notify("Export fehlgeschlagen", color="red")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="red")

    def export_card(title: str, description: str, action):
        with ui.card().classes(C_CARD + " p-5 " + C_CARD_HOVER + " w-full"):
            ui.label(title).classes("font-semibold text-slate-900")
            ui.label(description).classes("text-sm text-slate-500 mb-2")
            ui.button("Download", icon="download", on_click=action).classes(C_BTN_SEC)

    with ui.grid(columns=2).classes("w-full gap-4"):
        export_card("PDF ZIP", "Alle Rechnungs-PDFs als ZIP-Datei", lambda: run_export(export_invoices_pdf_zip, "PDF ZIP"))
        export_card("Rechnungen CSV", "Alle Rechnungen als CSV-Datei", lambda: run_export(export_invoices_csv, "Rechnungen CSV"))
        export_card("Positionen CSV", "Alle Rechnungspositionen als CSV-Datei", lambda: run_export(export_invoice_items_csv, "Positionen CSV"))
        export_card("Kunden CSV", "Alle Kunden als CSV-Datei", lambda: run_export(export_customers_csv, "Kunden CSV"))

    with ui.expansion("Erweitert").classes("w-full mt-4"):
        with ui.column().classes("w-full gap-2 p-2"):
            export_card("DB-Backup", "SQLite Datenbank sichern", lambda: run_export(export_database_backup, "DB-Backup"))
