from __future__ import annotations

from contextlib import contextmanager

from nicegui import app, ui

from data import InvoiceStatus
from styles import (
    C_NUMERIC,
    STYLE_BADGE_GRAY,
    STYLE_BADGE_GREEN,
    STYLE_BADGE_RED,
    STYLE_BADGE_YELLOW,
    STYLE_BTN_DANGER,
    STYLE_BTN_GHOST,
    STYLE_BTN_MUTED,
    STYLE_BTN_PRIMARY,
    STYLE_BTN_SECONDARY,
    STYLE_CARD,
    STYLE_CARD_HOVER,
    STYLE_EMPTY,
    STYLE_EMPTY_BODY,
    STYLE_EMPTY_TITLE,
    STYLE_EYEBROW,
    STYLE_EYEBROW_ASIDE,
    STYLE_EYEBROW_LABEL,
    STYLE_EYEBROW_RULE,
    STYLE_HERO,
    STYLE_HERO_EYEBROW,
    STYLE_HERO_META,
    STYLE_HERO_VALUE,
    STYLE_ICON_TOOLBAR,
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
def ff_card(*, pad: str = "p-3 sm:p-4", classes: str = "", hover: bool = False):
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


def ff_upload(*, on_upload=None, label: str = "Datei wählen", auto_upload: bool = False, classes: str = "", props: str = ""):
    """Upload wrapper with unified surface styling."""
    return (
        ui.upload(on_upload=on_upload, auto_upload=auto_upload, label=label)
        .props(props.strip())
        .classes(f"ff-upload w-full {classes}".strip())
    )




def _readonly_disabled(write_action: bool) -> str:
    return " disable" if write_action and bool(app.storage.user.get("readonly_mode")) else ""

def ff_btn_primary(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "", write_action: bool = True) -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"unelevated no-caps{_readonly_disabled(write_action)} {props}".strip())
        .classes(f"{STYLE_BTN_PRIMARY} {classes}".strip())
    )


def ff_btn_secondary(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "", write_action: bool = False) -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"flat no-caps{_readonly_disabled(write_action)} {props}".strip())
        .classes(f"{STYLE_BTN_SECONDARY} {classes}".strip())
    )


def ff_btn_muted(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "", write_action: bool = True) -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"flat no-caps{_readonly_disabled(write_action)} {props}".strip())
        .classes(f"{STYLE_BTN_MUTED} {classes}".strip())
    )


def ff_btn_danger(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "", write_action: bool = True) -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"unelevated no-caps{_readonly_disabled(write_action)} {props}".strip())
        .classes(f"{STYLE_BTN_DANGER} {classes}".strip())
    )


def ff_btn_ghost(text: str, *, on_click=None, icon: str | None = None, classes: str = "", props: str = "", write_action: bool = True) -> ui.button:
    return (
        ui.button(text, icon=icon, on_click=on_click)
        .props(f"flat no-caps{_readonly_disabled(write_action)} {props}".strip())
        .classes(f"{STYLE_BTN_GHOST} {classes}".strip())
    )


def ff_icon_button(
    *,
    icon: str,
    on_click=None,
    classes: str = "",
    props: str = "",
    write_action: bool = False,
    round_button: bool = True,
) -> ui.button:
    shape = " round" if round_button else ""
    p = f"flat dense{shape}{_readonly_disabled(write_action)} {props}".strip()
    merged = f"{STYLE_ICON_TOOLBAR} {classes}".strip()
    return ui.button(icon=icon, on_click=on_click).props(p).classes(merged)

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
        trend_color_class = "text-slate-500"

    with ff_card(pad="p-3", classes=f"ff-kpi-card relative overflow-hidden flex flex-col gap-2.5 {classes}".strip()):
        # Indigo accent strip at top (Stripe-style)
        ui.element("div").classes(
            "absolute top-0 left-0 right-0 h-px "
            "bg-gradient-to-r from-indigo-500 to-violet-500 rounded-t-lg"
        )
        # Icon badge + label
        with ui.row().classes("items-center gap-3 pt-1"):
            with ui.element("div").classes(
                "w-7 h-7 rounded-md bg-indigo-50 flex items-center justify-center shrink-0"
            ):
                ui.icon(icon).classes("text-sm text-indigo-600")
            ui.label(label).classes("text-xs font-semibold text-slate-500 uppercase tracking-wider")
        # Value
        ui.label(value).classes(f"text-xl font-semibold text-slate-900 {C_NUMERIC}")
        # Trend
        if trend_text:
            with ui.row().classes("items-center gap-1"):
                if trend_icon:
                    ui.icon(trend_icon).classes(f"text-xs {trend_color_class}")
                ui.label(trend_text).classes(f"text-xs {trend_color_class}")

@contextmanager
def ff_hero(eyebrow: str, value: str, meta: str | None = None, *, classes: str = ""):
    """Top-of-page hero: large editorial-serif number with an ink-wash background.
    Use exactly ONE per page (usually above KPI grids or table lists)."""
    with ui.element("div").classes(f"{STYLE_HERO} {classes}".strip()) as hero:
        ui.label(eyebrow).classes(STYLE_HERO_EYEBROW)
        ui.label(value).classes(STYLE_HERO_VALUE)
        if meta:
            ui.label(meta).classes(STYLE_HERO_META)
        yield hero


@contextmanager
def ff_empty_state(title: str, body: str, *, icon: str = "inbox", classes: str = ""):
    """Editorial empty state. Mono caption, single-line description, single CTA slot."""
    with ui.element("div").classes(f"{STYLE_EMPTY} {classes}".strip()) as panel:
        with ui.element("div").classes("ff-empty-glyph"):
            ui.icon(icon)
        ui.label(title).classes(STYLE_EMPTY_TITLE)
        ui.label(body).classes(STYLE_EMPTY_BODY)
        yield panel


def ff_eyebrow(label: str, aside: str | None = None) -> None:
    """Small uppercase eyebrow + thin rule. Replaces a generic section title."""
    with ui.element("div").classes(STYLE_EYEBROW):
        ui.label(label).classes(STYLE_EYEBROW_LABEL)
        if aside:
            ui.label(aside).classes(STYLE_EYEBROW_ASIDE)
        ui.element("div").classes(STYLE_EYEBROW_RULE)


@contextmanager
def settings_card(title: str | None = None, classes: str = ""):
    with ff_card(pad="p-3 sm:p-4", classes=f"w-full {classes}".strip()) as card:
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
    with ui.row().classes(
        "bg-white/90 backdrop-blur-sm border-b border-slate-200/80 px-4 py-3 sticky top-0 z-60 "
        "shadow-[0_1px_8px_rgba(0,0,0,0.05)] "
        "flex flex-wrap justify-between items-center gap-2 w-full"
    ):
        with ui.row().classes("items-center gap-2 min-w-0"):
            ui.icon("description", size="sm").classes("text-indigo-500")
            ui.label(title).classes(f"{STYLE_SECTION_TITLE} truncate")
        with ui.row().classes("gap-2 w-full sm:w-auto sm:ml-auto justify-start sm:justify-end flex-wrap"):
            if on_cancel:
                ff_btn_secondary("Abbrechen", on_click=on_cancel)
            if on_save:
                ff_btn_secondary("Speichern", icon="save", on_click=on_save)
            if on_finalize:
                ff_btn_primary("Finalisieren", icon="check_circle", on_click=on_finalize)
