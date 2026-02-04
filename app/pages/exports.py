from __future__ import annotations
import os
import tempfile

from ._shared import *

# Auto generated page renderer

def render_exports(session, comp: Company) -> None:
    ui.label("Exporte").classes(C_PAGE_TITLE + " mb-4")

    def run_export(action, label: str):
        ui.notify("Wird vorbereitet…")
        try:
            with get_session() as s:
                result = action(s, comp.id)
            if isinstance(result, (bytes, bytearray)):
                suffix = ".zip" if bytes(result[:4]) == b"PK\x03\x04" else ".csv"
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="export_")
                temp_path = temp_file.name
                temp_file.write(result)
                temp_file.close()
                ui.download(temp_path)
                ui.notify(f"{label} bereit", color="grey")
                return
            if result and os.path.exists(result):
                ui.download(result)
                ui.notify(f"{label} bereit", color="grey")
                return
            ui.notify("Export fehlgeschlagen", color="orange")
        except Exception as e:
            ui.notify(f"Fehler: {e}", color="orange")

    def export_card(title: str, description: str, action):
        with ui.card().classes(C_CARD + " p-5 " + C_CARD_HOVER + " w-full"):
            ui.label(title).classes("font-semibold text-neutral-100")
            ui.label(description).classes("text-sm text-neutral-400 mb-2")
            ui.button("Download", icon="download", on_click=action).classes(C_BTN_SEC)

    with ui.grid(columns=2).classes("w-full gap-4"):
        export_card("Dokumente ZIP", "Alle Dokumente als ZIP-Datei", lambda: run_export(export_documents_zip, "Dokumente ZIP"))
        export_card("Rechnungen CSV", "Alle Rechnungen als CSV-Datei", lambda: run_export(export_invoices_csv, "Rechnungen CSV"))
        export_card("Positionen CSV", "Alle Rechnungspositionen als CSV-Datei", lambda: run_export(export_invoice_items_csv, "Positionen CSV"))
        export_card("Kunden CSV", "Alle Kunden als CSV-Datei", lambda: run_export(export_customers_csv, "Kunden CSV"))
        export_card("DB-Backup", "SQLite Datenbank sichern", lambda: run_export(export_database_backup, "DB-Backup"))
