from __future__ import annotations

from typing import Any

from nicegui import ui
from sqlmodel import select

from data import Customer
from styles import STYLE_SECTION_TITLE
from ui_components import ff_btn_primary, ff_btn_secondary, ff_card, ff_input, settings_card, settings_grid, settings_two_column_layout
from ._shared import customer_address_card, customer_contact_card, get_session, insert_customer


def create_new_customer_dialog(comp, *, on_saved=None) -> ui.dialog:
    """Erstellt den Neukunden-Dialog und gibt das dialog-Objekt zurück."""
    dialog = ui.dialog()

    with dialog:
        with ff_card(pad="p-4", classes="w-full max-w-[92vw] max-h-[85vh] overflow-y-auto"):
            ui.label("Neuer Kunde").classes(f"{STYLE_SECTION_TITLE} mb-2")
            with settings_two_column_layout(max_width_class="max-w-4xl"):
                contact_fields = customer_contact_card()
                address_fields = customer_address_card(country_value=getattr(comp, "country", None) or "DE")
                with settings_card("Rechnungsempfänger"):
                    same_recipient_checkbox = ui.checkbox("Rechnungsempfänger = Kontaktadresse", value=True).classes("mb-2")
                    with settings_grid():
                        recipient_name = ff_input("Rechnungsempfänger", value="")
                        recipient_street = ff_input("Rechnungsstraße", value="")
                        recipient_plz = ff_input("Rechnungs-PLZ", value="")
                        recipient_city = ff_input("Rechnungs-Ort", value="")

            name_input = contact_fields["name"]
            first = contact_fields["first"]
            last = contact_fields["last"]
            email = contact_fields["email"]
            short_code = contact_fields["short_code"]
            street = address_fields["street"]
            plz = address_fields["plz"]
            city = address_fields["city"]
            country = address_fields["country"]

            def _contact_display_name() -> str:
                name_value = (name_input.value or "").strip()
                if name_value:
                    return name_value
                return f"{first.value or ''} {last.value or ''}".strip()

            def _sync_recipient_with_contact() -> None:
                recipient_name.value = _contact_display_name()
                recipient_street.value = street.value or ""
                recipient_plz.value = plz.value or ""
                recipient_city.value = city.value or ""

            def _maybe_sync_recipient() -> None:
                if same_recipient_checkbox.value:
                    _sync_recipient_with_contact()

            same_recipient_checkbox.on("update:model-value", lambda _: _maybe_sync_recipient())
            _maybe_sync_recipient()

            def _reset_form(prefill_name: str = "") -> None:
                name_input.value = prefill_name
                first.value = ""
                last.value = ""
                email.value = ""
                short_code.value = ""
                street.value = ""
                plz.value = ""
                city.value = ""
                country.value = getattr(comp, "country", None) or "DE"
                _maybe_sync_recipient()

            def _save() -> None:
                display_name = (name_input.value or "").strip()
                if not display_name and not ((first.value or "").strip() or (last.value or "").strip()):
                    ui.notify("Bitte mindestens einen Namen für den Kunden angeben.", color="red")
                    return

                new_id = None
                with get_session() as s:
                    c = insert_customer(
                        s, comp,
                        name=name_input.value or "", vorname=first.value or "",
                        nachname=last.value or "", email=email.value or "",
                        short_code=short_code.value or "", strasse=street.value or "",
                        plz=plz.value or "", ort=city.value or "",
                        country=country.value or "",
                        recipient_name=recipient_name.value or _contact_display_name(),
                        recipient_street=recipient_street.value or "",
                        recipient_postal_code=recipient_plz.value or "",
                        recipient_city=recipient_city.value or "",
                    )
                    new_id = int(c.id) if c.id is not None else None

                if on_saved:
                    on_saved(new_id, comp)
                ui.notify("Kunde gespeichert.", type="positive")
                dialog.close()

            with ui.row().classes("w-full justify-end gap-2 mt-4"):
                ff_btn_secondary("Abbrechen", on_click=dialog.close)
                ff_btn_primary("Speichern", on_click=_save)

    dialog._reset_form = _reset_form  # type: ignore[attr-defined]
    return dialog
