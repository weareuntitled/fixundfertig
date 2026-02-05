from __future__ import annotations

from nicegui import app, ui

from ._shared import (
    C_PAGE_TITLE,
    User,
    get_current_user_id,
    get_session,
)
from styles import STYLE_TEXT_MUTED
from ui_components import ff_btn_ghost, ff_btn_primary, ff_card, ff_input
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

    with ff_card(pad="p-5", classes="w-full max-w-4xl mb-4"):
        ui.label("Neue Einladung").classes("text-sm font-semibold text-slate-900")
        ui.label("Nur eingeladene E-Mails können sich registrieren und einloggen.").classes(STYLE_TEXT_MUTED)
        email_input = ff_input("E-Mail-Adresse", value="", props='placeholder="name@example.com"')

        @ui.refreshable
        def invite_list():
            invites = list_invited_emails()
            if not invites:
                ui.label("Noch keine Einladungen.").classes(STYLE_TEXT_MUTED)
                return
            with ui.column().classes("w-full divide-y divide-slate-200"):
                for invite in invites:
                    with ui.row().classes("w-full items-center justify-between px-3 py-3 hover:bg-slate-50 transition-colors"):
                        ui.label(invite.email).classes("text-sm text-slate-900")

                        def _remove(email: str = invite.email) -> None:
                            if remove_invited_email(email):
                                ui.notify("Einladung entfernt.", color="grey")
                                invite_list.refresh()
                            else:
                                ui.notify("Einladung nicht gefunden.", color="orange")

                        ff_btn_ghost("Entfernen", on_click=_remove)

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
            ff_btn_primary("Einladen", on_click=_add_invite)

    with ff_card(pad="p-5", classes="w-full max-w-4xl"):
        ui.label("Aktive Einladungen").classes("text-sm font-semibold text-slate-900 mb-2")
        invite_list()
