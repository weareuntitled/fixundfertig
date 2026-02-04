from __future__ import annotations

from nicegui import app, ui

from ._shared import (
    C_BTN_PRIM,
    C_BTN_SEC,
    C_CARD,
    C_INPUT,
    C_PAGE_TITLE,
    User,
    get_current_user_id,
    get_session,
)
from services.auth import add_invited_email, get_owner_email, list_invited_emails, remove_invited_email


def _resolve_user_email(user_id: int | None) -> str:
    if not user_id:
        return ""
    with get_session() as session:
        user = session.get(User, int(user_id))
        return (user.email or "").strip().lower() if user else ""


def render_invites(session, _comp) -> None:
    user_id = get_current_user_id(session)
    if user_id is None:
        ui.notify("Nicht eingeloggt.", color="orange")
        return

    current_email = _resolve_user_email(int(user_id))
    if current_email != get_owner_email():
        ui.notify("Nur der Owner kann Einladungen verwalten.", color="orange")
        app.storage.user["page"] = "dashboard"
        ui.navigate.to("/")
        return

    ui.label("Einladungen").classes(C_PAGE_TITLE)

    with ui.card().classes(C_CARD + " p-5 w-full max-w-4xl mb-4"):
        ui.label("Neue Einladung").classes("text-sm font-semibold text-neutral-200")
        ui.label("Nur eingeladene E-Mails können sich registrieren und einloggen.").classes(
            "text-sm text-neutral-400"
        )
        email_input = ui.input("E-Mail-Adresse", placeholder="name@example.com").classes(C_INPUT)

        @ui.refreshable
        def invite_list():
            invites = list_invited_emails()
            if not invites:
                ui.label("Noch keine Einladungen.").classes("text-sm text-neutral-400")
                return
            with ui.column().classes("w-full gap-2"):
                for invite in invites:
                    with ui.row().classes(
                        "w-full items-center justify-between rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2"
                    ):
                        ui.label(invite.email).classes("text-sm text-neutral-200")

                        def _remove(email: str = invite.email) -> None:
                            if remove_invited_email(email):
                                ui.notify("Einladung entfernt.", color="grey")
                                invite_list.refresh()
                            else:
                                ui.notify("Einladung nicht gefunden.", color="orange")

                        ui.button("Entfernen", on_click=_remove).classes(C_BTN_SEC)

        def _add_invite() -> None:
            email = (email_input.value or "").strip()
            if not email:
                ui.notify("E-Mail-Adresse fehlt.", color="orange")
                return
            try:
                add_invited_email(email, invited_by_user_id=int(user_id))
            except Exception as exc:
                ui.notify(f"Einladung fehlgeschlagen: {exc}", color="orange")
                return
            ui.notify("Einladung gespeichert.", color="grey")
            email_input.set_value("")
            invite_list.refresh()

        with ui.row().classes("w-full gap-2 mt-2 flex-wrap"):
            ui.button("Einladen", on_click=_add_invite).classes(C_BTN_PRIM)

    with ui.card().classes(C_CARD + " p-5 w-full max-w-4xl"):
        ui.label("Aktive Einladungen").classes("text-sm font-semibold text-neutral-200 mb-2")
        invite_list()
