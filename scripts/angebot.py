"""Angebot als Entwurf in fixundfertig anlegen, aus einer JSON-Datei.

Aufruf:
    .venv/bin/python scripts/angebot.py angebot.json            # anlegen
    .venv/bin/python scripts/angebot.py angebot.json --probelauf # nur prüfen und Summen zeigen

Anmeldung: E-Mail aus FF_EMAIL, Passwort aus dem macOS-Schlüsselbund
(Dienst "fixundfertig", Konto = E-Mail). Einmalig hinterlegen mit:
    security add-generic-password -U -a "$FF_EMAIL" -s fixundfertig -w

JSON-Format (Vorgaben und Bausteine: .claude/skills/angebot/SKILL.md):
{
  "firma": "Untitled-UX",                       # optional, sonst Hauptfirma
  "kunde": {"name": "Firma GmbH", "vorname": "", "nachname": "", "email": "",
            "strasse": "", "plz": "", "ort": ""},   # wird über "name" gesucht, sonst angelegt
  "betreff": "Variante A: ...",
  "einleitung": "Hallo ...",
  "gueltig_tage": 30,                           # optional
  "positionen": [{"text": "...", "menge": 1.5, "preis": 70}],
  "raten": [{"prozent": 50, "anlass": "bei Auftrag"}]
}
Es wird nur ein Entwurf angelegt; verschickt wird nichts.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import httpx

STANDARD_URL = "https://app.untitled-ux.de"


def baue_entwurf(daten: dict, kunde_id: int, kleinunternehmer: bool, heute: date | None = None) -> dict:
    """Übersetzt die Angebots-JSON in den Body für POST /api/invoices."""
    heute = heute or date.today()
    positionen = daten.get("positionen") or []
    if not positionen:
        raise ValueError("Mindestens eine Position nötig.")
    raten = daten.get("raten") or []
    summe_raten = sum(float(r["prozent"]) for r in raten)
    if raten and abs(summe_raten - 100) > 0.01:
        raise ValueError(f"Raten ergeben {summe_raten:g} % statt 100 %.")
    return {
        "customer_id": kunde_id,
        "document_type": "QUOTE",
        "title": "Angebot",
        "subject": daten.get("betreff", ""),
        "date": heute.isoformat(),
        "valid_until": (heute + timedelta(days=int(daten.get("gueltig_tage", 30)))).isoformat(),
        "intro_text": daten.get("einleitung", ""),
        "ust_enabled": not kleinunternehmer,
        "vat_rate": 0 if kleinunternehmer else 19,
        "items": [
            {"description": p["text"], "quantity": float(p["menge"]), "unit_price": float(p["preis"])}
            for p in positionen
        ],
        "payment_plan": [{"percent": float(r["prozent"]), "label": r.get("anlass", "")} for r in raten],
    }


def netto_summe(entwurf: dict) -> float:
    return round(sum(i["quantity"] * i["unit_price"] for i in entwurf["items"]), 2)


def euro(betrag: float) -> str:
    return f"{betrag:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def passwort(email: str) -> str:
    try:
        return subprocess.run(
            ["security", "find-generic-password", "-a", email, "-s", "fixundfertig", "-w"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        sys.exit('Kein Passwort im Schlüsselbund (Dienst "fixundfertig"). Siehe Kopf dieser Datei.')


def anmelden(url: str, email: str) -> httpx.Client:
    client = httpx.Client(base_url=url, timeout=30)
    antwort = client.post("/api/auth/login", json={"email": email, "password": passwort(email)})
    if antwort.status_code != 200:
        sys.exit(f"Anmeldung fehlgeschlagen ({antwort.status_code}).")
    client.headers["X-CSRF-Token"] = client.cookies.get("ff_csrf", "")
    return client


def firma_waehlen(client: httpx.Client, name: str | None) -> dict:
    if name:
        firmen = client.get("/api/company/list").raise_for_status().json()
        treffer = [f for f in firmen if str(f.get("name", "")).strip().lower() == name.strip().lower()]
        if not treffer:
            sys.exit(f'Firma "{name}" nicht gefunden: {", ".join(f.get("name", "") for f in firmen)}')
        client.cookies.set("ff_company", str(treffer[0]["id"]))
    return client.get("/api/company").raise_for_status().json()


def kunde_finden_oder_anlegen(client: httpx.Client, kunde: dict) -> tuple[int, bool]:
    name = kunde["name"].strip().lower()
    for k in client.get("/api/customers").raise_for_status().json():
        if str(k.get("name", "")).strip().lower() == name:
            return int(k["id"]), False
    neu = client.post("/api/customers", json={**kunde, "country": kunde.get("country", "DE")})
    neu.raise_for_status()
    return int(neu.json()["id"]), True


def main() -> None:
    parser = argparse.ArgumentParser(description="Angebot als Entwurf in fixundfertig anlegen.")
    parser.add_argument("datei", help="Angebots-JSON")
    parser.add_argument("--probelauf", action="store_true", help="nur prüfen, nichts anlegen")
    parser.add_argument("--url", default=os.environ.get("FF_URL", STANDARD_URL))
    args = parser.parse_args()

    with open(args.datei, encoding="utf-8") as f:
        daten = json.load(f)

    if args.probelauf:
        entwurf = baue_entwurf(daten, kunde_id=1, kleinunternehmer=True)
        for p in entwurf["items"]:
            print(f'{p["quantity"]:>6g} × {euro(p["unit_price"]):>10}  {p["description"][:70]}')
        summe = netto_summe(entwurf)
        print(f"Netto: {euro(summe)}")
        for r in entwurf["payment_plan"]:
            print(f'  {r["percent"]:g} % {r["label"]}: {euro(summe * r["percent"] / 100)}')
        return

    email = os.environ.get("FF_EMAIL") or sys.exit("FF_EMAIL ist nicht gesetzt.")
    with anmelden(args.url, email) as client:
        firma = firma_waehlen(client, daten.get("firma"))
        kunde_id, neu = kunde_finden_oder_anlegen(client, daten["kunde"])
        entwurf = baue_entwurf(daten, kunde_id, bool(firma.get("is_small_business")))
        antwort = client.post("/api/invoices", json=entwurf)
        if antwort.status_code != 201:
            sys.exit(f"Angebot nicht angelegt ({antwort.status_code}): {antwort.text[:300]}")
        angebot = antwort.json()
    print(f'Kunde {"angelegt" if neu else "gefunden"}: {daten["kunde"]["name"]} (#{kunde_id})')
    print(f'Angebot {angebot.get("nr")} als Entwurf, {euro(angebot.get("total_brutto", 0))}: '
          f'{args.url}/quotes/{angebot["id"]}')


if __name__ == "__main__":
    main()
