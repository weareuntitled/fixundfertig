from contextlib import contextmanager

from nicegui import ui
from data import InvoiceStatus
from styles import (
    C_BADGE_GRAY,
    C_BADGE_GREEN,
    C_BADGE_RED,
    C_BADGE_YELLOW,
    C_BTN_PRIM,
    C_BTN_SEC,
    C_CARD,
    C_CARD_HOVER,
    C_GLASS_CARD_HOVER,
    C_SECTION_TITLE,
)

def format_invoice_status(status: str) -> str:
    mapping = {
        InvoiceStatus.DRAFT: "Entwurf",
        InvoiceStatus.OPEN: "Offen",
        InvoiceStatus.SENT: "Gesendet",
        InvoiceStatus.PAID: "Bezahlt",
        InvoiceStatus.FINALIZED: "Offen",
        InvoiceStatus.CANCELLED: "Storniert",
        "Bezahlt": "Bezahlt"
    }
    return mapping.get(status, status)

def invoice_status_badge(status: str) -> str:
    if status == InvoiceStatus.DRAFT: return C_BADGE_GRAY
    if status == InvoiceStatus.OPEN: return C_BADGE_YELLOW
    if status == InvoiceStatus.SENT: return C_BADGE_YELLOW
    if status == InvoiceStatus.PAID: return C_BADGE_GREEN
    if status == InvoiceStatus.FINALIZED: return C_BADGE_YELLOW
    if status == InvoiceStatus.CANCELLED: return C_BADGE_GRAY
    if status == "Bezahlt": return C_BADGE_GREEN
    if status == "Overdue": return C_BADGE_RED
    return C_BADGE_GRAY

def kpi_card(label, value, icon, color, classes: str = ""):
    card_classes = f"{C_CARD} {C_CARD_HOVER} p-4 flex flex-row items-center justify-between {classes}".strip()
    with ui.card().classes(card_classes):
        with ui.column().classes('gap-1'):
            ui.label(label).classes('text-xs font-bold text-slate-400 uppercase tracking-wider')
            ui.label(value).classes('text-2xl font-bold text-slate-800')
        with ui.element("div").classes("rounded-full bg-white/80 shadow-inner px-3 py-2"):
            ui.icon(icon).classes(f"text-2xl {color}")

@contextmanager
def settings_card(title: str | None = None, classes: str = ""):
    with ui.card().classes(f"{C_CARD} p-6 w-full {classes}".strip()) as card:
        if title:
            ui.label(title).classes(C_SECTION_TITLE)
        yield card


@contextmanager
def settings_grid(columns: int | None = 2):
    responsive_classes = "grid grid-cols-1 gap-4 w-full"
    if columns:
        responsive_classes = f"{responsive_classes} md:grid-cols-{columns}"
    with ui.element("div").classes(responsive_classes):
        yield

@contextmanager
def settings_two_column_layout(max_width_class: str = "max-w-5xl"):
    with ui.element("div").classes(f"w-full {max_width_class} mx-auto"):
        with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 w-full"):
            yield

def sticky_header(title, on_cancel, on_save=None, on_finalize=None):
    # WICHTIG: Kein ui.header() nutzen, da wir schon im Layout sind!
    # Stattdessen ein sticky div/row.
    # z-index 40, damit es unter dem Haupt-Header (z-50) durchscrollt, falls nötig, 
    # oder einfach oben im Content klebt.
    with ui.row().classes('bg-white border-b border-slate-200 p-4 sticky top-0 z-60 flex justify-between items-center w-full shadow-sm'):
        with ui.row().classes('items-center gap-2'):
            ui.icon('description', size='sm').classes('text-slate-500')
            ui.label(title).classes('text-lg font-bold text-slate-800')
        with ui.row().classes('gap-2'):
            if on_cancel:
                ui.button('Abbrechen', on_click=on_cancel).classes(C_BTN_SEC)
            if on_save:
                ui.button('Speichern', icon='save', on_click=on_save).classes(C_BTN_SEC)
            if on_finalize:
                ui.button('Finalisieren', icon='check_circle', on_click=on_finalize).classes(C_BTN_PRIM)
