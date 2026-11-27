import importlib.util
from datetime import date
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("angebot", Path(__file__).parent.parent / "scripts" / "angebot.py")
angebot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(angebot)

from app.schemas.invoice import InvoiceDraft  # noqa: E402

DATEN = {
    "kunde": {"name": "Muster GmbH"},
    "betreff": "Variante A",
    "einleitung": "Hallo,\n\nzweiter Absatz.",
    "positionen": [{"text": "E-Mail einrichten", "menge": 1.75, "preis": 70}, {"text": "Formular", "menge": 3, "preis": 70}],
    "raten": [{"prozent": 50, "anlass": "bei Auftrag"}, {"prozent": 50, "anlass": "nach Fertigstellung"}],
}


def test_entwurf_passt_zum_api_schema_und_rechnet_richtig():
    entwurf = angebot.baue_entwurf(DATEN, kunde_id=7, kleinunternehmer=True, heute=date(2026, 11, 27))
    InvoiceDraft(**entwurf)  # wirft bei falschen Feldern
    assert entwurf["document_type"] == "QUOTE"
    assert entwurf["valid_until"] == "2026-12-27"
    assert entwurf["ust_enabled"] is False and entwurf["vat_rate"] == 0
    assert angebot.netto_summe(entwurf) == 332.50


def test_regelbesteuerung_setzt_19_prozent():
    entwurf = angebot.baue_entwurf(DATEN, kunde_id=7, kleinunternehmer=False)
    assert entwurf["ust_enabled"] is True and entwurf["vat_rate"] == 19


def test_raten_muessen_100_prozent_ergeben():
    with pytest.raises(ValueError, match="80 %"):
        angebot.baue_entwurf({**DATEN, "raten": [{"prozent": 80}]}, kunde_id=7, kleinunternehmer=True)


def test_ohne_positionen_kein_angebot():
    with pytest.raises(ValueError):
        angebot.baue_entwurf({**DATEN, "positionen": []}, kunde_id=7, kleinunternehmer=True)


def test_euro_format():
    assert angebot.euro(2135) == "2.135,00 €"
