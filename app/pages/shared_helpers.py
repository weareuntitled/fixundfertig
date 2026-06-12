"""Pure utility functions extracted from pages/_shared.py."""
from __future__ import annotations

import os
import json
import time
import logging
import functools
import inspect
from collections.abc import Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from nicegui import ui, app
from sqlmodel import select

from data import Company, User, get_session, log_audit_action

from styles import (
    STYLE_DROPDOWN_LABEL,
    STYLE_DROPDOWN_OPTION,
    STYLE_DROPDOWN_OPTION_ACTIVE,
)

logger = logging.getLogger(__name__)

_shell_navigate_cb: Callable[[str], None] | None = None


def register_shell_navigate(fn: Callable[[str], None]) -> None:
    global _shell_navigate_cb
    _shell_navigate_cb = fn


def app_shell_nav_items(is_owner: bool) -> list[dict]:
    items: list[dict] = [
        {"id": "dashboard", "label": "Dashboard", "icon": "dashboard"},
        {"id": "invoices", "label": "Rechnungen", "icon": "receipt_long"},
        {"id": "documents", "label": "Belege", "icon": "description"},
        {"id": "ledger", "label": "Finanzen", "icon": "account_balance"},
        {"id": "exports", "label": "Export", "icon": "file_download"},
        {"id": "customers", "label": "Kunden", "icon": "groups"},
        {"id": "expenses", "label": "Ausgaben", "icon": "shopping_bag"},
    ]
    if is_owner:
        items.append({"id": "invites", "label": "Einladungen", "icon": "mail"})
    return items


def go_app_page(page: str) -> None:
    app.storage.user["page"] = page
    cb = _shell_navigate_cb
    if cb is not None:
        try:
            cb(page)
            return
        except Exception:
            logger.exception("go_app_page: shell refresh failed for %s", page)
    ui.navigate.to("/")


def ui_handler(context: str, *, notify_message: str = "Aktion fehlgeschlagen.") -> callable:
    def decorator(func: callable) -> callable:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception:
                    logger.exception("UI handler failed: %s", context, extra={"context": context})
                    ui.notify(notify_message, color="red")
            return async_wrapper

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                logger.exception("UI handler failed: %s", context, extra={"context": context})
                ui.notify(notify_message, color="red")
        return wrapper
    return decorator


def get_current_user_id(session) -> int | None:
    identifier = app.storage.user.get("auth_user")
    if not identifier:
        return None
    statement = select(User).where((User.email == identifier) | (User.username == identifier))
    user = session.exec(statement).first()
    return user.id if user else None


def list_companies(session, user_id: int) -> list[Company]:
    statement = select(Company).where(Company.user_id == user_id).order_by(Company.id)
    return list(session.exec(statement))


def get_primary_company(session, user_id: int) -> Company:
    companies = list_companies(session, user_id)
    if companies:
        return companies[0]
    unassigned = session.exec(select(Company).where(Company.user_id.is_(None))).first()
    if unassigned:
        unassigned.user_id = user_id
        session.add(unassigned)
        session.commit()
        return unassigned
    company = Company(user_id=user_id)
    session.add(company)
    session.commit()
    return company


def log_invoice_action(action: str, invoice_id: int | None = None) -> None:
    with get_session() as s:
        log_audit_action(s, action, invoice_id=invoice_id)
        s.commit()


def _parse_iso_date(value: str | None):
    from datetime import datetime
    try:
        return datetime.fromisoformat(value or "")
    except Exception:
        return datetime.min


def _open_invoice_detail(invoice_id: int) -> None:
    app.storage.user["invoice_detail_id"] = int(invoice_id)
    go_app_page("invoice_detail")


def _open_invoice_editor(draft_id: int | None) -> None:
    app.storage.user["invoice_draft_id"] = int(draft_id) if draft_id else None
    go_app_page("invoice_create")


def is_readonly_mode() -> bool:
    return bool(app.storage.user.get("readonly_mode"))


def readonly_scope() -> dict:
    scope = app.storage.user.get("readonly_scope") or {}
    return scope if isinstance(scope, dict) else {}


def _fetch_address_autocomplete(query: str, country_code: str) -> list[dict]:
    if len(query.strip()) < 3:
        return []
    base_url = os.environ.get("APP_BASE_URL", "http://localhost:8080")
    params = urlencode({"q": query, "country": country_code})
    url = f"{base_url}/api/address-autocomplete?{params}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    return payload


def use_address_autocomplete(
    street_input: ui.input,
    zip_input: ui.input,
    city_input: ui.input,
    country_input: ui.input,
    dropdown_container: ui.element,
    *,
    country_code: str = "DE",
    debounce_seconds: float = 0.35,
) -> None:
    state = {
        "query": "",
        "results": [],
        "open": False,
        "active_index": -1,
        "pending": False,
        "last_change": 0.0,
    }

    def set_dropdown_visible(visible: bool) -> None:
        dropdown_container.style(f"display: {'block' if visible else 'none'}")

    set_dropdown_visible(False)

    def apply_result(result: dict) -> None:
        street_input.value = result.get("street") or ""
        zip_input.value = result.get("zip") or ""
        city_input.value = result.get("city") or ""
        country_value = result.get("country") or country_input.value or country_code
        country_input.value = country_value
        state["open"] = False
        state["active_index"] = -1
        set_dropdown_visible(False)

    def update_dropdown() -> None:
        dropdown_container.clear()
        if not state["open"] or not state["results"]:
            set_dropdown_visible(False)
            return

        set_dropdown_visible(True)
        for idx, result in enumerate(state["results"]):
            label = result.get("label") or ""
            is_active = idx == state["active_index"]
            option_classes = STYLE_DROPDOWN_OPTION
            if is_active:
                option_classes = f"{option_classes} {STYLE_DROPDOWN_OPTION_ACTIVE}"
            with ui.element("button").props(
                f"type=button role=option aria-selected={'true' if is_active else 'false'}"
            ).classes(option_classes).on("click", lambda _, r=result: apply_result(r)):
                ui.label(label).classes(STYLE_DROPDOWN_LABEL)

    def on_input_change(_) -> None:
        state["query"] = street_input.value or ""
        state["pending"] = True
        state["last_change"] = time.monotonic()

    def on_keydown(e) -> None:
        key = (e.args or {}).get("key")
        if key == "ArrowDown":
            if state["results"]:
                state["open"] = True
                state["active_index"] = (state["active_index"] + 1) % len(state["results"])
                update_dropdown()
        elif key == "ArrowUp":
            if state["results"]:
                state["open"] = True
                state["active_index"] = (state["active_index"] - 1) % len(state["results"])
                update_dropdown()
        elif key == "Enter":
            if state["open"] and 0 <= state["active_index"] < len(state["results"]):
                apply_result(state["results"][state["active_index"]])
        elif key == "Escape":
            state["open"] = False
            state["active_index"] = -1
            set_dropdown_visible(False)

    def debounce_tick() -> None:
        if not state["pending"]:
            return
        if time.monotonic() - state["last_change"] < debounce_seconds:
            return
        state["pending"] = False
        query = state["query"].strip()
        if len(query) < 3:
            state["results"] = []
            state["open"] = False
            state["active_index"] = -1
            update_dropdown()
            return
        results = _fetch_address_autocomplete(query, country_code)
        state["results"] = results
        state["open"] = bool(results)
        state["active_index"] = 0 if results else -1
        update_dropdown()

    street_input.on("input", on_input_change)
    street_input.on("keydown", on_keydown)
    street_input.on("focus", lambda _: update_dropdown())
    ui.timer(0.1, debounce_tick)
