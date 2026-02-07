from __future__ import annotations

from contextlib import contextmanager

from nicegui import ui

from data import InvoiceStatus
from styles import (
    C_NUMERIC,
    STYLE_BADGE_GRAY,
    STYLE_BADGE_GREEN,
    STYLE_BADGE_RED,
    STYLE_BADGE_YELLOW,
    STYLE_BTN_MUTED,
    STYLE_BTN_PRIMARY,
    STYLE_BTN_SECONDARY,
    STYLE_CARD,
    STYLE_CARD_HOVER,
    STYLE_INPUT,
    STYLE_PAGE_TITLE,
    STYLE_SECTION_TITLE,
    STYLE_TEXT_MUTED,
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
    if status == InvoiceStatus.DRAFT:
        return STYLE_BADGE_GRAY
    if status == InvoiceStatus.OPEN:
        return STYLE_BADGE_YELLOW
    if status == InvoiceStatus.SENT:
        return STYLE_BADGE_YELLOW
    if status == InvoiceStatus.PAID:
        return STYLE_BADGE_GREEN
    if status == InvoiceStatus.FINALIZED:
        return STYLE_BADGE_YELLOW
    if status == InvoiceStatus.CANCELLED:
        return STYLE_BADGE_GRAY
    if status == "Bezahlt":
        return STYLE_BADGE_GREEN
    if status == "Overdue":
        return STYLE_BADGE_RED
    return STYLE_BADGE_GRAY


@contextmanager
def ff_card(*, pad: str = "p-4 sm:p-6", classes: str = "", hover: bool = False):
    """Card wrapper: flat (no Quasar shadow) + single padding source."""
    hover_classes = STYLE_CARD_HOVER if hover else ""
    with ui.card().props("flat").classes(f"{STYLE_CARD} {hover_classes} {pad} {classes}".strip()) as card:
        yield card


def ff_input(label: str, *, value: str | None = None, classes: str = "", props: str = "") -> ui.input:
    """Input wrapper: outlined+dense, consistent sizing."""
    return (
        ui.input(label, value=value)
        .props(f"outlined dense {props}".strip())
        .classes(f"{STYLE_INPUT} {classes}".strip())
    )


def ff_textarea(label: str, *, value: str | None = None, classes: str = "", props: str = "") -> ui.textarea:
    return (
        ui.textarea(label, value=value)
        .props(f"outlined dense {props}".strip())
        .classes(f"{STYLE_INPUT} {classes}".strip())
    )


def ff_select(label: str, options, *, value=None, classes: str = "", props: str = "") -> ui.select:
    return (
        ui.select(options, label=label, value=value)
        .props(f"outlined dense {props}".strip())
        .classes(f"{STYLE_INPUT} {classes}".strip())
    )


def ff_btn_primary(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "") -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"unelevated no-caps {props}".strip())
        .classes(f"{STYLE_BTN_PRIMARY} {classes}".strip())
    )


def ff_btn_secondary(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "") -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"flat no-caps {props}".strip())
        .classes(f"{STYLE_BTN_SECONDARY} {classes}".strip())
    )


def ff_btn_muted(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "") -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"flat no-caps {props}".strip())
        .classes(f"{STYLE_BTN_MUTED} {classes}".strip())
    )


def ff_btn_danger(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "") -> ui.button:
    return ff_btn_muted(text, on_click=on_click, icon=icon, classes=classes, props=props)


def ff_btn_ghost(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "") -> ui.button:
    return ff_btn_muted(text, on_click=on_click, icon=icon, classes=classes, props=props)

def kpi_card(
    label,
    value,
    icon,
    color,
    classes: str = "",
    trend_text: str | None = None,
    trend_direction: str | None = None,
    trend_color: str | None = None,
):
    icon_map = {"up": "arrow_upward", "down": "arrow_downward", "flat": "arrow_forward"}
    direction = (trend_direction or "").lower()
    trend_icon = icon_map.get(direction)
    if trend_color:
        trend_color_class = trend_color
    elif direction == "up":
        trend_color_class = "text-emerald-600"
    elif direction == "down":
        trend_color_class = "text-rose-600"
    else:
        trend_color_class = "text-slate-600"

    with ff_card(pad="p-5", classes=f"relative overflow-hidden flex flex-col justify-between h-[220px] {classes}".strip()):
        ui.icon(icon).classes("absolute right-4 bottom-4 text-6xl text-slate-200")
        with ui.column().classes("gap-2 z-10"):
            with ui.row().classes("items-center gap-2"):
                ui.icon(icon).classes("text-base text-amber-600")
                ui.label(label).classes("text-xs font-bold text-slate-600 uppercase tracking-wider")
            ui.element("div").classes("h-px w-10 bg-slate-200")
            ui.label(value).classes(f"text-[40px] font-bold text-slate-900 {C_NUMERIC}")
            if trend_text:
                with ui.row().classes("items-center gap-1"):
                    if trend_icon:
                        ui.icon(trend_icon).classes(f"text-xs {trend_color_class}")
                    ui.label(trend_text).classes(f"text-xs {trend_color_class}")

@contextmanager
def settings_card(title: str | None = None, classes: str = ""):
    with ff_card(pad="p-4 sm:p-6", classes=f"w-full {classes}".strip()) as card:
        if title:
            ui.label(title).classes(STYLE_SECTION_TITLE)
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
    with ui.row().classes(
        "bg-white/80 backdrop-blur border-b border-slate-200 p-3 sm:p-4 sticky top-0 z-60 "
        "flex flex-wrap justify-between items-start sm:items-center gap-2 w-full"
    ):
        with ui.row().classes("items-center gap-2 min-w-0"):
            ui.icon("description", size="sm").classes("text-slate-500")
            ui.label(title).classes("text-lg font-bold text-slate-900 truncate")
        with ui.row().classes("gap-2 w-full sm:w-auto sm:ml-auto justify-start sm:justify-end flex-wrap"):
            if on_cancel:
                ff_btn_secondary("Abbrechen", on_click=on_cancel)
            if on_save:
                ff_btn_secondary("Speichern", icon="save", on_click=on_save)
            if on_finalize:
                ff_btn_primary("Finalisieren", icon="check_circle", on_click=on_finalize)
