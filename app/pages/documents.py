from __future__ import annotations

import os
from datetime import datetime

from ._shared import *


def render_documents(session, comp: Company) -> None:
    ui.label("Dokumente").classes(C_PAGE_TITLE)
    ui.label("Importierte Dokumente aus Automationen.").classes("text-sm text-slate-500 mb-4")

    def _format_date(value: datetime | None) -> str:
        if not value:
            return "-"
        try:
            return value.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "-"

    def _load_documents() -> list[dict]:
        rows = session.exec(
            select(Document)
            .where(Document.company_id == comp.id)
            .order_by(Document.id.desc())
        ).all()
        items: list[dict] = []
        for doc in rows:
            items.append(
                {
                    "id": int(doc.id),
                    "title": (doc.title or "").strip(),
                    "description": (doc.description or "").strip(),
                    "vendor": (doc.vendor or "").strip(),
                    "keywords": (doc.keywords or "").strip(),
                    "source": (doc.source or "").strip(),
                    "file_path": (doc.file_path or "").strip(),
                    "file_name": (doc.file_name or "").strip(),
                    "created_at": doc.created_at,
                }
            )
        return items

    items = _load_documents()

    if not items:
        with ui.card().classes(C_CARD + " p-4"):
            ui.label("Keine Dokumente vorhanden.").classes("text-sm text-slate-500")
        return

    with ui.card().classes(C_CARD + " p-0 overflow-hidden"):
        with ui.row().classes(C_TABLE_HEADER):
            ui.label("Datum").classes("w-36 font-bold text-xs text-slate-500")
            ui.label("Titel").classes("w-56 font-bold text-xs text-slate-500")
            ui.label("Lieferant").classes("w-40 font-bold text-xs text-slate-500")
            ui.label("Keywords").classes("w-56 font-bold text-xs text-slate-500")
            ui.label("Quelle").classes("w-20 font-bold text-xs text-slate-500")
            ui.label("Datei").classes("w-20 font-bold text-xs text-slate-500")

        for doc in items:
            with ui.row().classes(C_TABLE_ROW):
                ui.label(_format_date(doc["created_at"])).classes("w-36 text-xs font-mono text-slate-600")
                ui.label(doc["title"] or "-").classes("w-56 text-sm")
                ui.label(doc["vendor"] or "-").classes("w-40 text-sm text-slate-600")
                ui.label(doc["keywords"] or "-").classes("w-56 text-xs text-slate-500")
                ui.label(doc["source"] or "-").classes("w-20 text-xs text-slate-500")

                def _download(path=doc["file_path"], label=doc["file_name"]):
                    if not path or not os.path.exists(path):
                        ui.notify("Datei nicht gefunden.", color="red")
                        return
                    ui.download(path, filename=label or None)

                ui.button("Download", on_click=_download).props("flat dense").classes(
                    "w-20 text-xs text-blue-600 hover:text-blue-700"
                )
