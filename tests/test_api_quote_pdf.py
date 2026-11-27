"""Das Angebots-PDF aus der gemeinsamen Vorlage, beobachtet über die API (#486)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from pdf_text import pdf_strings
from test_api_invoice_artist_identity import artist_api  # noqa: F401  (fixture)


def _quote(payload: dict, **overrides) -> dict:
    return payload | {"document_type": "QUOTE", "date": "2026-10-23", "valid_until": "2026-11-22"} | overrides


def _create(client, body: dict) -> dict:
    response = client.post("/api/invoices", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _download(client, invoice_id: int):
    response = client.get(f"/api/invoices/{invoice_id}/download")
    assert response.status_code == 200, response.text
    return response


def test_quote_pdf_names_itself_angebot_with_number_and_dates(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload))

    strings = pdf_strings(_download(client, quote["id"]).content)

    assert "ANGEBOT AN" in strings
    number_index = strings.index(f"Nr. {quote['nr']}")
    assert strings[number_index - 1] == "ANGEBOT"
    assert "RECHNUNG" not in strings
    assert "RECHNUNG AN" not in strings
    for label, value in (("Angebotsdatum:", "23.10.2026"), ("Gültig bis:", "22.11.2026")):
        assert strings[strings.index(label) + 1] == value
    assert "Rechnungsdatum:" not in strings
    assert "Leistungsdatum:" not in strings


def test_quote_pdf_asks_for_no_payment(artist_api):
    client, company, payload, _ = artist_api
    company.bank_name = "N26"
    quote = _create(client, _quote(payload))

    strings = pdf_strings(_download(client, quote["id"]).content)
    text = " ".join(strings)

    for absent in ("Zahlbar bis", "ZAHLUNGSINFORMATIONEN", "Kontoinhaber", "IBAN", "Verwendungszweck",
                   "DE89 3704 0044 0532 0130 00"):
        assert absent not in text
    assert "GESAMTBETRAG" in strings
    assert "300,00 €" in strings


def test_quote_download_is_named_angebot_nr(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload))

    response = _download(client, quote["id"])

    assert response.headers["content-disposition"] == f'attachment; filename="angebot_{quote["nr"]}.pdf"'


def test_quote_preview_create_and_download_show_the_same_text(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload))
    draft_preview = client.post("/api/invoices/preview-pdf", json=_quote(payload))
    assert draft_preview.status_code == 200, draft_preview.text

    preview = pdf_strings(client.get(f"/api/invoices/{quote['id']}/preview-pdf").content)
    download = pdf_strings(_download(client, quote["id"]).content)

    assert preview == download
    # The draft has no number yet; everything else matches the stored quote.
    assert pdf_strings(draft_preview.content) == [s for s in download if s != f"Nr. {quote['nr']}"]


def test_editing_or_regenerating_a_quote_keeps_it_an_angebot(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload))

    edited = client.put(f"/api/invoices/{quote['id']}", json={"valid_until": "2026-12-01"})
    assert edited.status_code == 200, edited.text
    after_edit = pdf_strings(_download(client, quote["id"]).content)
    assert "ANGEBOT" in after_edit
    assert after_edit[after_edit.index("Gültig bis:") + 1] == "01.12.2026"
    assert "Zahlbar bis" not in " ".join(after_edit)

    regenerated = client.post(f"/api/invoices/{quote['id']}/regenerate-pdf")
    assert regenerated.status_code == 200, regenerated.text
    after_regenerate = pdf_strings(_download(client, quote["id"]).content)
    assert after_regenerate == after_edit


def test_quote_pdf_follows_position_changes(artist_api):
    client, _, payload, _ = artist_api
    quote = _create(client, _quote(payload))
    item_id = quote["items"][0]["id"]

    added = client.post(f"/api/invoices/{quote['id']}/items",
                        json={"description": "Anfahrt", "quantity": 1, "unit_price": 40})
    assert added.status_code == 201, added.text
    assert "Anfahrt" in pdf_strings(_download(client, quote["id"]).content)

    changed = client.put(f"/api/invoices/{quote['id']}/items/{item_id}",
                         json={"description": "Live-Set", "quantity": 1, "unit_price": 200})
    assert changed.status_code == 200, changed.text
    strings = pdf_strings(_download(client, quote["id"]).content)
    assert "Live-Set" in strings
    assert "DJ-Set Daniel S. (Daniel Schmidt)" not in " ".join(strings)

    removed = client.delete(f"/api/invoices/{quote['id']}/items/{item_id}")
    assert removed.status_code == 200, removed.text
    strings = pdf_strings(client.get(f"/api/invoices/{quote['id']}/preview-pdf").content)
    assert "Live-Set" not in strings
    assert "ANGEBOT" in strings


def test_invoice_pdf_keeps_its_invoice_wording(artist_api):
    client, company, payload, _ = artist_api
    company.bank_name = "N26"
    invoice = _create(client, payload | {"date": "2026-10-23"})

    response = _download(client, invoice["id"])
    strings = pdf_strings(response.content)

    assert "RECHNUNG AN" in strings and "RECHNUNG" in strings and "ANGEBOT" not in strings
    assert "Zahlbar bis" in strings and "ZAHLUNGSINFORMATIONEN" in strings
    assert "Gültig bis:" not in strings
    assert f'filename="rechnung_{invoice["nr"]}.pdf"' in response.headers["content-disposition"]


def test_intro_keeps_paragraphs(artist_api):
    """Absätze der Einleitung bleiben im PDF als eigene Zeilen erhalten."""
    client, _, payload, _ = artist_api
    intro = "Hallo Herr Muster,\n\nerster Absatz.\n\nZahlungsbedingungen: 50 % bei Auftrag."
    quote = _create(client, _quote(payload, intro_text=intro))

    strings = pdf_strings(_download(client, quote["id"]).content)

    assert "Hallo Herr Muster," in strings
    assert "erster Absatz." in strings
    assert "Zahlungsbedingungen: 50 % bei Auftrag." in strings
