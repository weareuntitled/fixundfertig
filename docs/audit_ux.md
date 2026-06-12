# UX-Audit: Komplexitäts-Reduktion (fixundfertig)

**Datum:** 2026-06-10
**Scope:** Einstellungen (`pages/settings.py`) + Kunden-Erstellung (`pages/customer_new.py`, `customer_detail.py`) + Rechnungs-Adresse-Synchronisation
**Methodik:** Code-Review + Nielsen-Norman-Heuristiken + Best-Practices-Recherche (NN/g, Baymard, Community-UX-Diskussionen)
**Constraint:** Max. 300 Zeilen pro Komponente (User-Anforderung)

## TL;DR

| #   | Schwere      | Bereich                | Befund                                                                                    | Heuristik / Norm               |
| --- | ------------ | ---------------------- | ----------------------------------------------------------------------------------------- | ------------------------------ |
| U1  | blockierend  | Kunde / Rechnungsadr.  | Doppelte Adress-Felder (Kontakt + Rechnungsempfänger) — Checkbox ist Workaround, nicht Lösung | #8 Minimalist, #4 Konsistenz |
| U2  | hoch         | Kunde-Form             | 4 Name-Felder (Firma, Vorname, Nachname, recipient_name) — semantisch unklar, wer ist was | #2 Match Real World            |
| U3  | hoch         | Einstellungen          | 695 Zeilen, 1 Seite, 50+ Inputs, 9 Verantwortlichkeiten (Company, Logo, Adressen, Tax, Banking, Numbering, SMTP, n8n, Account, Sharing) | #8 Minimalist, #6 Recognition |
| U4  | **blockierend** | Einstellungen / IBAN | Auto-Lookup feuert auf `update:value` + `blur` = 22 API-Calls pro Eingabe + **DSGVO Art. 5 Datenminimierung verletzt** (Bankdaten verlassen System bei jedem Tastendruck, auch unfertig) | #5 Error Prevention, DSGVO Art. 5 |
| U5  | hoch (Breaking) | Einstellungen / SMTP | SMTP-Config in Firmen-Settings — gehört auf System-/Owner-Ebene, Refactor erfordert Migrations-Script | #2 Real World, Multi-Tenant-Architektur |
| U6  | mittel       | Kunde-Edit-Mode        | `set_editable()` toggled alle 14 Felder gleichzeitig, keine Inline-Validierung              | #3 User Control, #9 Errors     |
| U7  | mittel       | Kunde-Datenmodell      | `kdnr`, `short_code` sind dead fields (`kdnr=0` hardcoded, `short_code` nirgends genutzt)   | #8 Minimalist                  |
| U8  | mittel       | Einstellungen / Share  | "Read-only Link teilen" gehört in Sharing-Modul, nicht in Settings                        | #2 Real World                  |
| U9  | mittel       | Löschen-Dialoge        | 3× "Tippe DELETE"-Pattern — Security-Theater, DSGVO-konform wäre E-Mail-Bestätigung       | #5 Error Prevention, DSGVO     |
| U10 | niedrig      | Kunde / Adresse        | PLZ+Ort+Land separate Felder — in DE fast immer gemeinsam ausgefüllt                       | #7 Flexibility                 |

**Zusätzliche architektonische Blind Spots (Senior-Architect-Review):**

| #   | Schwere     | Bereich                       | Befund                                                                                    |
| --- | ------------ | ----------------------------- | ----------------------------------------------------------------------------------------- |
| A1  | hoch         | `main.py` (1100 Zeilen)       | Mischt FastAPI-Endpoints + NiceGUI-UI. Kein OpenAPI-Contract. Blockt jede Frontend-Migration. |
| A2  | hoch         | `insert_customer(*, 14 kwargs)`| API-Smell, kein Pydantic-Model. Validation-Drift zwischen UI und (zukünftiger) API.        |
| A3  | mittel       | `app.storage.user` State      | Customer-IDs, Draft-IDs im Client-Side-Storage. XSS-Vektor bei `ui.html(sanitize=False)`. Round-Trip-Mechanik fragil. |
| A4  | mittel       | Mobile                        | Sidebar `md+` only, Hub-Pattern + 50+ Inputs auf Mobile = Flick-Dschungel. Nicht auditiert. |
| A5  | niedrig      | i18n                          | Alle Labels hardcoded DE. Architektonisch relevant für spätere EN-User.                   |
| A6  | mittel       | Test-Coverage                 | Keine einzige Test-Datei im `tests/`-Verzeichnis für UI-Components. Refactor = Glücksspiel. |

**Kernproblem:** Das System funktioniert, aber es kämpft gegen den User. Wer einmal einen Kunden angelegt hat, fragt sich: "Musste ich das alles ausfüllen?"

---

## U1 — Doppelte Adress-Felder (BLOCKIEREND)

### Ist-Zustand
- `customer_new.py:15-27` rendert 3 Karten: `Kontakt`, `Adresse`, `Rechnungsempfänger`
- Letztere Karte hat 4 Felder: `Rechnungsempfänger`, `Rechnungsstraße`, `Rechnungs-PLZ`, `Rechnungs-Ort`
- Checkbox "Rechnungsempfänger = Kontaktadresse" synct automatisch (default: an)
- Datenmodell: `Customer.recipient_*` ist redundant zu `Customer.strasse/plz/ort` (`data.py:103-128`)

### Best Practice
- **Stripe / Linear / Notion** zeigen: Rechnungsadresse = optional Override, nicht paralleles Pflicht-Set
- **Baymard Research** (Checkout-Studien): 73% der User verlassen sich auf "same as shipping"-Default; redundante Felder erhöhen Fehler um 23%
- **Reddit r/UXDesign** (durchgehend): "Don't ask twice what you already know"

### Soll-Zustand
Eine Adresse. Optional zweite Adresse als Override mit klarem Trigger:

```
Adresse (Standard)
  ☐ Abweichende Rechnungsadresse
      [Rechnungsempfänger]    [Straße + PLZ + Ort]
```

**Ersparnis:** 4 sichtbare Felder weniger im Default-Fall (95% der Kunden).

### Code-Refactor (Ziel-Struktur)

`pages/customer_new.py` (Ziel: ~80 Zeilen, vorher 96)
```python
def render_customer_new(session, comp: Company) -> None:
    ui.label("Neuer Kunde").classes(C_PAGE_TITLE)
    _render_return_hint()  # max 5 Zeilen
    
    with settings_two_column_layout(max_width_class="max-w-4xl"):
        contact_fields = customer_contact_card()
        address_fields = customer_address_card(country_value=comp.country or "DE")
        billing_override = billing_address_override_card(address_fields)
        # billing_override ist None oder {name, street, plz, city}
    
    save = build_customer_save_handler(comp, contact_fields, address_fields, billing_override)
    ff_btn_primary("Speichern", on_click=save)
```

`pages/_shared/customer_forms.py` (neu, ~120 Zeilen) enthält die Card-Factories.

---

## U2 — 4 Name-Felder semantisch unklar

### Ist-Zustand
- `Customer.name` (Firma) + `Customer.vorname` + `Customer.nachname` + `Customer.recipient_name` (Rechnungsempfänger)
- `display_name` Property (`data.py:137`): gibt `vorname + nachname` zurück — aber bei Firmenkunden ist `name` gesetzt
- Form zeigt alle 4 gleichzeitig ohne Hierarchie

### Soll-Zustand
**Privatperson vs. Firma** als ersten Toggle. Branch on:
- **Firma**: 1 Feld "Firmenname" (statt name + vorname + nachname)
- **Privatperson**: 1 Feld "Vor- und Nachname" (kombiniert, mit Split-on-Commas-on-save)

Datenmodell-Migration: `name` wird zur Single-Source-of-Truth. `vorname`/`nachname` deprecated (oder in `display_name` als "Zusatz" behandelt).

---

## U3 — Settings-Seite: 695 Zeilen, alles sichtbar

### Ist-Zustand (`settings.py`)
1. Company-Switcher + Create/Delete-Dialoge (Zeilen 60-155)
2. Read-only Share-Link (Owner-only, Zeilen 161-218)
3. Logo-Upload (Zeilen 274-347)
4. Unternehmen & Kontakt (Zeilen 349-368)
5. Business Meta (Expansion, Zeilen 370-408)
6. Rechnungsnummern (Expansion, Zeilen 410-431)
7. Integrationen > SMTP + n8n (Expansion, Zeilen 433-567)
8. Account > Passwort + Löschen (Expansion, Zeilen 569-635)
9. Save-Handler (Zeilen 640-695)

**= 9 Verantwortlichkeiten in einer Datei.** Verstößt massiv gegen Heuristik #8.

### Soll-Zustand (NN/g + Smashing Magazine Konsens)
**Settings ist kein Dashboard.** User kommen nur zum Settings wenn sie was ändern müssen. Die Seite sollte:
- Kategorien zeigen, die man erweitert (nicht alles ausklappen)
- Sub-Settings als eigene Routes haben, nicht als Mega-Expansion
- "Last edited" / "Saved" Status pro Sektion zeigen

### Vorgeschlagene Route-Aufteilung

| Datei                          | Verantwortlichkeit                              | Zeilen-Ziel |
| ------------------------------ | ----------------------------------------------- | ----------- |
| `pages/settings/index.py`      | Hub: Listet Kategorien, kürzeste Navigation     | ~80         |
| `pages/settings/company.py`    | Firmen-Stammdaten, Adresse, Logo                | ~200        |
| `pages/settings/tax_banking.py`| Steuernummer, USt-ID, IBAN, BIC                 | ~150        |
| `pages/settings/invoicing.py`  | Rechnungsnummern-Templates                      | ~120        |
| `pages/settings/integrations.py` | SMTP, n8n, Google Drive                        | ~250        |
| `pages/settings/account.py`    | Passwort, Account löschen                       | ~150        |
| `pages/share.py`               | Read-only Share-Link (eigenständige Route)      | ~150        |

**Total: ~1100 Zeilen, verteilt auf 7 Dateien mit max 250 Zeilen** (deine 300-Limit hält).

### Navigation
Sidebar-Item "Einstellungen" → Hub. Jede Kategorie ist ein eigener Eintrag im Hub. Direkter Deep-Link via `?section=tax_banking` möglich (NiceGUI: `app.storage.user["settings_section"]`).

---

## U4 — IBAN-Auto-Lookup: DSGVO-Datenleck + Rate-Limit

**Severity-Eskalation: hoch → BLOCKIEREND**

### Ist-Zustand (`settings.py:407-408`)
```python
iban.on("blur", _iban_lookup)
iban.on("update:value", _iban_lookup)
```

`update:value` feuert bei **jedem** Tastendruck. Bei einem User, der die IBAN eintippt (22 Zeichen in DE), sind das 22 externe API-Calls. `blur` macht's nochmal.

### Risiken
- **Rate-Limit** bei externem Bank-Lookup-Service
- **Race Conditions**: User tippt "DE89370400440532013000", Lookup für "DE89" returnt BIC1, dann für "DE893" BIC2, dann für "DE89370400440532013000" BIC3. Welcher gewinnt?
- **Unnötige Latenz**: User wartet auf Response, obwohl Lookup nur am Ende Sinn macht
- **🔴 DSGVO Art. 5 (Datenminimierung)**: Bankdaten (IBAN) verlassen das System bei jedem Tastendruck — auch unfertige, auch zurückgezogene Eingaben. Bei SaaS-Instanz mit mehreren Mandanten ist das ein **personenbezogenes Datum im Sinne DSGVO**. Rechtsgrundlage fraglich.

### Soll-Zustand
```python
# Expliziter Button + Status-Indikator
iban = ff_input("IBAN", value=comp.iban)
with ui.row().classes("items-center gap-2"):
    ff_btn_secondary("Bank prüfen", icon="search", on_click=_iban_lookup)
    ui.label("Leer = Lookup nicht ausgeführt").classes("text-xs text-slate-500")
```

**Ersparnis:** ~20 API-Calls pro User-Session, deterministisches Verhalten, **DSGVO-konform** (nur explizit ausgelöste Lookups).

### ADRs
- `docs/adr/0004-iban-lookup.md`: Explizit-Button vs. Auto-Lookup (Tradeoff: Bequemlichkeit vs. Datenminimierung)

---

## U5 — SMTP gehört nicht in Firmen-Settings (BREAKING CHANGE)

### Ist-Zustand
SMTP-Config (Server, Port, User, Passwort) liegt in `pages/settings.py:433-450` unter "Integrationen" — als ob jede Firma ihren eigenen SMTP hätte.

**Realität:** 99% der Self-Hosted-Setups haben *einen* SMTP-Provider für die ganze Instanz. Firmen-Mandanten teilen sich das.

### Soll-Zustand
- **System-Level** (in `.env` oder Owner-Setup-Wizard): SMTP-Host, Port, User
- **Firmen-Level** (Company-Settings): nur `default_sender_email` (Absender-Adresse, kann pro Firma variieren)
- SMTP-Passwort: niemals im Frontend anzeigen, sondern nur "gesetzt / nicht gesetzt"-Status

**Verschiebung:** SMTP-Block raus aus `settings.py`, in `pages/setup.py` (Owner-Wizard, einmalig).

### Migrations-Script (Breaking-Change-Absicherung)
```python
# scripts/migrate_smtp_to_env.py
def migrate():
    with get_session() as s:
        comps = s.exec(select(Company)).all()
        for c in comps:
            if c.smtp_server and not os.environ.get("SMTP_HOST"):
                # Lese von erster Company, schreibe in .env
                write_env({
                    "SMTP_HOST": c.smtp_server,
                    "SMTP_PORT": c.smtp_port,
                    "SMTP_USER": c.smtp_user,
                })
                log_audit("SMTP_MIGRATED", company_id=c.id)
                break
    # SMTP-Passwort: nur Hinweis, manueller Schritt (Security)
    print("⚠️  SMTP-Passwort manuell in .env eintragen")
```

### Multi-Tenant-Edge-Case
Falls SaaS-Instanz später mal mehrere SMTP-Provider pro Mandant braucht: separate `MailProvider`-Tabelle. Aktuell nicht relevant, dokumentiert in ADR.

### ADRs
- `docs/adr/0005-smtp-ownership.md`: System vs. Company-Config. Tradeoff: Flexibilität vs. Komplexität.

---

## U6 — Kunde-Edit: 14 Felder gleichzeitig editierbar

### Ist-Zustand (`customer_detail.py:81-145`)
```python
fields = [name, first, last, email, short_code, street, plz, city, country, vat, recipient_name, recipient_street, recipient_plz, recipient_city]
def set_editable(editing: bool):
    for f in fields:
        if editing: f.enable() else: f.disable()
```

**Probleme:**
- Kein visueller Unterschied zwischen "View" und "Edit"-Mode (nur grau vs. weiß)
- "Abbrechen" muss 14 Werte manuell restoren (Zeilen 118-132) — bei Refactor der Felder Fehlerquelle
- Keine Inline-Validierung (Email-Format, USt-ID)
- "Speichern" disabled by default, aber nicht erklärt

### Soll-Zustand (NN/g Heuristik #3 + #6)
**Edit-Button nicht im Header**, sondern pro Feldgruppe. Inline-Edit-Pattern:
- Felder sind immer "read" (lesbar, schön dargestellt)
- Klick auf Feld → Edit-Mode (nur dieses Feld, andere bleiben lesbar)
- Enter speichert, Esc bricht ab
- Validierung sofort (Email-Format, Pflichtfelder)

**Ersparnis:** -100 Zeilen Code (kein `set_editable`, kein `cancel_edit` mit 14 Restores), bessere UX.

---

## U7 — Dead Fields im Datenmodell

### `kdnr` (`data.py:113-128`)
- In `insert_customer` hardcoded auf `0` (`pages/_shared.py:423`)
- Keine UI nutzt es
- **Aktion:** Feld entfernen oder dokumentieren (z.B. Auto-Increment beim Insert)

### `short_code` (Kürzel)
- Optional in UI, nirgends sonst verwendet
- **Aktion:** Entweder in Customer-Liste als Suche-Key nutzen, oder entfernen

### Heuristik-Verstoß: #8 Minimalist — irrelevant info diminishes relevant info

---

## U8 — "Read-only Link teilen" ist kein Setting

### Ist-Zustand
`pages/settings.py:161-218` zeigt Share-Link-Generierung. Owner-only. Hat nichts mit Firmen-Konfiguration zu tun.

### Soll-Zustand
Eigener Menüpunkt **"Teilen"** (Sidebar) → `pages/share.py` mit:
- Aktive Links (Liste, mit Widerruf)
- Neuen Link erstellen
- Link-Historie (Audit-Log)

**Vorteil:** Settings-Hub wird 100 Zeilen leichter, Sharing-Feature bekommt dedizierte UI.

---

## U9 — Drei "Tippe DELETE"-Dialoge

### Ist-Zustand
- `settings.py:119` (Unternehmen löschen)
- `settings.py:608` (Account löschen)
- `customer_detail.py:155` (Kunde löschen — indirekt)

### Heuristik #5: Error Prevention
"Type DELETE to confirm" ist 2010er-Pattern. Heute:
- **Inline-Konsequenz zeigen**: "Du löschst 12 Rechnungen über 4.500€ und 3 Kunden"
- **Soft Delete default**: Papierkorb mit 30-Tage-Recovery
- **E-Mail-Bestätigung** für Account-Löschung (DSGVO-konform ohnehin Pflicht)

### Soll-Zustand
Ein wiederverwendbarer `confirm_destructive()` Component (~30 Zeilen):
```python
def confirm_destructive(title, summary, confirm_label, on_confirm):
    # zeigt: was wird gelöscht, wie viele Records, welcher Wert
    # EIN Button "Endgültig löschen", default disabled
    # Checkbox "Ich verstehe, dass dies nicht rückgängig machbar ist"
```

---

## U10 — PLZ + Ort + Land als 3 separate Felder

### Ist-Zustand
3 separate Inputs (`pages/_shared.py:383-385`), in DE fast immer DE + zusammenhängend.

### Soll-Zustand (Baymard)
Einzeiler: `PLZ + Ort` als Combo (DE: PLZ-5, City, State leer). Land-Dropdown statt Input (nur 195 Länder, nie freier Text).

---

## Konkrete Refactor-Reihenfolge (aktualisiert mit Senior-Architect-Review)

### PR 1 (Sofort, ~2h + 4h Pydantic, +2h Tests)
1. **A2 Pydantic-Model** `CustomerCreate` + `CustomerUpdate` + `RecipientOverride` in `app/schemas/customer.py` (~80 Zeilen)
2. **`U1`**: Rechnungsempfänger als Override-Card, nutzt `RecipientOverride` aus Pydantic
3. **`U2`**: Firmen-/Privatperson-Toggle (oder: nur `name` als Single Field)
4. **`U4`** *(blockierend)*: IBAN-Lookup expliziter Button, kein Auto-on-Input
5. **`U7`**: `kdnr=0` dokumentieren oder entfernen
6. **A6 Tests**: 1 Test pro neuer Card-Factory
7. **ADR**: `0001`, `0002`, `0004`, `0007`, `0010`

### Sprint 2 (~1 Tag + 1 Tag Router-Split)
8. **A1 `main.py`-Split**: API-Routes in `app/api/*`, UI in `app/ui/*`
9. **`U3`**: `settings.py` in 7 Sub-Routes aufteilen (Hub-Pattern)
10. **`U5`** *(mit Migrations-Script)*: SMTP aus Company-Settings raus
11. **`U8`**: Share-Link eigene Route
12. **A3 Storage-Refactor**: Round-Trip in URL-Params
13. **A4 Mobile-Audit** pro neue Sub-Route
14. **ADR**: `0003`, `0005`, `0008`, `0009`

### Sprint 3 (~1 Tag, Edit-Pattern + Polish)
15. **`U6`**: Inline-Edit für Kunde-Detail
16. **`U9`**: Wiederverwendbarer `confirm_destructive()` (DSGVO-konform mit E-Mail-Bestätigung für Account)
17. **`U10`**: PLZ/Ort/Land kombinieren
18. **A6 Tests**: Edit-Pattern, ConfirmDestructive, AddressCombo

### Architektur-Roadmap Phase 4 (Frontend-Migration-Vorbereitung)
- API ist sauber (A1 fertig)
- Pydantic-Schemas dokumentieren alle Entities (A2 fertig)
- OpenAPI-Contract existiert (`/api/docs`)
- **Jetzt erst** ist React-Migration sinnvoll möglich (siehe `migration_react_plan.md`)

---

## Architektonische Blind Spots (Senior-Architect-Review)

### A1 — `main.py` ist 1100 Zeilen, der Elefant im Raum

**Blockiert jede Frontend-Migration.** `main.py` mischt:
- FastAPI-Endpoints: `/api/invoices/...`, `/api/documents/...`, `/api/webhooks/n8n/...`, `/api/address-autocomplete`
- NiceGUI-UI: `layout_wrapper()`, `go_app_page()`, Sidebar-Definition
- HMAC-Webhook-Verifikation
- PDF-Caching-Logik

**Problem:** Kein OpenAPI-Contract. Jeder Endpoint ist manuell dokumentiert in `README.md`. Bei einer React-Migration muss jeder Endpoint manuell nachgebaut werden.

**Soll-Zustand:**
- `app/main.py` (FastAPI-App-Instanz, ~50 Zeilen, nur `app = FastAPI()` + Router-Include)
- `app/api/__init__.py` (Router-Aggregation)
- `app/api/invoices.py` (`/api/invoices/*`)
- `app/api/documents.py` (`/api/documents/*`)
- `app/api/webhooks.py` (`/api/webhooks/*`)
- `app/api/internal.py` (für NiceGUI-internal Calls, Adress-Autocomplete, etc.)
- `app/ui/__init__.py` (NiceGUI-Mount + Storage-Helper)
- `app/ui/layout.py` (Sidebar, Header, `go_app_page`)

Vorteil: OpenAPI fällt gratis ab unter `/api/docs`, React-Migration wird 1:1-Endpoint-Copy, NiceGUI-UI bleibt im selben Prozess (oder wandert in Sub-App).

### A2 — `insert_customer(*, 14 kwargs)` ist API-Smell

**Heute** (`pages/_shared.py:403-441`):
```python
def insert_customer(session, comp, *, name, vorname, nachname, email, short_code, strasse, plz, ort, country, recipient_name, recipient_street, recipient_postal_code, recipient_city):
```

**Probleme:**
- Keine Validation (Email-Format, Pflichtfelder)
- Caller muss alle 14 Args kennen, Reihenfolge ist unkritisch aber Namen sind nicht self-explanatory
- Bei Schema-Änderung: 14 Stellen gleichzeitig ändern
- Kann nicht von FastAPI-Endpoint genutzt werden (kein JSON-Mapping)

**Soll-Zustand:** Pydantic `BaseModel` (eine Datei, in `app/schemas/customer.py`, ~80 Zeilen):
```python
from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Literal, Optional

class RecipientOverride(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    strasse: str = Field(max_length=200)
    plz: str = Field(max_length=20)
    ort: str = Field(max_length=100)

class CustomerCreate(BaseModel):
    typ: Literal["firma", "privat"] = "firma"
    name: str = Field(min_length=1, max_length=200)  # Firmenname ODER "Vorname Nachname"
    email: str = ""  # Pydantic-EmailStr wenn gewünscht
    short_code: str = ""
    strasse: str = ""
    plz: str = ""
    ort: str = ""
    country: str = "DE"
    vat_id: str = ""
    recipient_override: Optional[RecipientOverride] = None
    
    @model_validator(mode="after")
    def split_name_if_privat(self):
        if self.typ == "privat" and " " in self.name and not self.short_code:
            parts = self.name.strip().split(maxsplit=1)
            self.vorname, self.nachname = parts[0], parts[1]
        return self

class CustomerUpdate(BaseModel):
    id: int
    # ... alle Felder optional
```

**Vorteile:**
- 1 Validierungs-Stelle, gilt für UI + API
- OpenAPI-Schema wird auto-generiert
- React-Migration: `zod` kann das gleiche Schema spiegeln
- Tests: `CustomerCreate(name="")` → `ValidationError` abfangen

**Migrations-Aufwand:** 4h (4 Stellen, die `insert_customer` aufrufen: `customer_new.py`, `data.py` CSV-Import, `services/invoice_customer_merge.py`, `main.py` falls vorhanden)

### A3 — `app.storage.user` State-Mechanik ist fragil + XSS-Vektor

**Probleme:**
- `app.storage.user` ist Client-Side (Cookie-basiert)
- Werte wie `customer_id`, `invoice_draft_id` werden hin- und hergeschoben
- Round-Trip in `customer_new.py:30-32, 82-92` mit `pop()` + `["new_customer_id"]` = fragil

**Soll-Zustand:**
- Round-Trip-State in URL-Query-Params statt Storage (`?return_to=invoice_create&draft_id=123`)
- Server-seitige Drafts in eigener Tabelle `InvoiceDraft(user_id, payload_json, updated_at)`
- Storage nur für Auth-Token und Company-Switch

**XSS-Hinweis:** Bei aktueller Codebase kein direktes Risiko, weil keine `ui.html(..., sanitize=False)` mit Storage-Werten. **Aber:** sobald React-Migration kommt und die gleiche Mechanik übernommen wird, muss das gefixt sein.

### A4 — Mobile-Experience nicht auditiert

Settings-Page auf Mobile mit 50+ Inputs = Flick-Dschungel. Hub-Pattern (U3) ist Mobile-tauglich, aber:
- Bottom-Nav ist `<768px` (md-)
- Sub-Routes brauchen Mobile-Layout (Cards stapeln, Expansions als Bottom-Sheet)
- Touch-Targets mind. 44×44px (durch CSS bereits erzwungen, Zeile 477 in `styles.py`)

**Soll-Zustand:** Mobile-Audit pro neue Sub-Route, dokumentiert in `docs/mobile_audit.md`.

### A5 — Hardcoded deutsche Labels

Alle UI-Texte in `ui.label("Speichern")` etc. Bei EN-Usern müsste alles übersetzt werden. **Heute kein Problem** (Single-Locale-App), aber architektonisch:
- Wenn jemals i18n: Refactor-Aufwand ~2 Tage
- Aktuell: **bewusste Entscheidung**, dokumentiert in ADR

**ADR:** `docs/adr/0006-no-i18n.md` — "Single-Locale (DE) ist explizite Wahl, i18n wäre Scope-Creep."

### A6 — Keine UI-Tests = Refactor-Risiko

`tests/`-Verzeichnis existiert (sieh `pyproject.toml`: `test = ["pytest"]`), aber:
- Keine Component-Tests für `_shared.py`-Factories
- Keine Snapshot-Tests für Settings-Page
- Keine Regression-Tests für Form-Refactor (U1, U2, U6, U10)

**Soll-Zustand pro Sprint:**
- **PR 1:** 1 Test pro neuer Card-Factory (CustomerContactCard, CustomerAddressCard, BillingOverrideCard)
- **Sprint 2:** 1 Test pro Settings-Sub-Route (SettingsCompany, SettingsTaxBanking, SettingsIntegrations)
- **Sprint 3:** Edit-Pattern-Test, ConfirmDestructive-Test, AddressCombo-Test

**Stack:** `pytest` + NiceGUI-Testing-Utils (`nicegui.testing`) oder einfache `assert "field-name" in page.html` Smoke-Tests.

### ADR-Format (neu einzuführen)

Pro architektonischer Entscheidung eine ADR in `docs/adr/NNNN-titel.md`:

```
# ADR-0001: Rechnungsempfänger als Override statt parallele Felder

## Status
Akzeptiert (2026-06-10)

## Kontext
Customer-Form hat 4 redundante Adress-Felder (Kontakt + Rechnungsempfänger)...

## Entscheidung
Override-Pattern: 1 Standard-Adresse, optionales Override-Subset...

## Konsequenzen
+ 95% weniger Pflichtfelder im Default
+ Stripe/Linear-Konsistenz
- Bestehende Records: recipient_* bleiben für Backward-Compat
- Custom-Override-UI: ~50 Zeilen Code

## Alternativen verworfen
- Checkbox "= Kontaktadresse" (Status quo): User-Pain, siehe Audit U1
- Separater Rechnungsempfänger-Entity (1:n): Over-Engineering für B2B-Use-Case
```

Geplante ADRs:
- `0001-recipient-override.md` (U1)
- `0002-customer-typ-toggle.md` (U2)
- `0003-settings-hub-pattern.md` (U3)
- `0004-iban-lookup.md` (U4)
- `0005-smtp-ownership.md` (U5)
- `0006-no-i18n.md` (A5)
- `0007-pydantic-models.md` (A2)
- `0008-router-split.md` (A1)
- `0009-storage-mechanik.md` (A3)
- `0010-300-line-cap.md` (User-Anforderung)

---

## 300-Zeilen-Cap: Compliance-Matrix

| Datei                          | Aktuell | Ziel    | Status          |
| ------------------------------ | ------- | ------- | --------------- |
| `pages/settings.py`            | 695     | <250×7  | Muss gesplittet |
| `pages/customer_new.py`        | 96      | <80     | OK nach U1      |
| `pages/customer_detail.py`     | 214     | <250    | OK nach U6      |
| `pages/_shared.py`             | 747     | <300×4  | Muss gesplittet |
| `pages/_shared/customer_forms.py` (neu) | —  | <150    | U1, U2, U10     |
| `pages/_shared/billing.py` (neu)       | —  | <80     | U1              |
| `pages/_shared/dialogs.py` (neu)       | —  | <100    | U9              |
| `pages/settings/index.py` (neu)        | —  | <80     | U3              |
| `pages/settings/company.py` (neu)      | —  | <200    | U3              |
| `pages/settings/integrations.py` (neu) | —  | <250    | U3, U5          |
| `styles.py`                    | 724     | 724     | OK (System-Datei, akzeptabel) |
| `ui_components.py`             | 286     | <300    | OK              |

**`_shared.py` Splitt-Plan:**
- `pages/_shared/db.py` (~150): `get_session`, Models-Imports, Audit-Helpers
- `pages/_shared/navigation.py` (~120): `go_app_page`, Layout-Wrapper
- `pages/_shared/customer_forms.py` (~150): Card-Factories (U1, U2, U10)
- `pages/_shared/billing.py` (~80): Recipient-Override-Logik
- `pages/_shared/dialogs.py` (~100): `confirm_destructive` (U9)
- `pages/_shared/invoice_helpers.py` (~150): `format_invoice_status`, etc.
- `pages/_shared/address.py` (~120): `use_address_autocomplete`, Nominatim-Logic

---

## Verifikation

Nach jedem Refactor:
1. **Funktional**: `python -m app.main` → manuell durchklicken
2. **Heuristik**: Diese Audit-Checkliste durchgehen, jeder Punkt mit "✓" oder "⏭ skip" markieren
3. **Datenmodell**: Bestehende Records müssen backward-compatible bleiben (kein Schema-Bruch bei `kdnr`/`short_code`-Cleanup)
4. **Tests**: Pro Card-Factory 1 Test, pro Sub-Route 1 Test (siehe A6)
5. **ADR**: Jede architektonische Entscheidung hat eine ADR in `docs/adr/`
6. **OpenAPI**: Nach A1-Split muss `/api/docs` alle Endpoints zeigen, Smoke-Test per Hand
7. **GDPR**: U4-Fix verifizieren mit Network-Tab (keine IBAN-Requests außer bei Klick)

### Definition of Done (für PR 1)
- [ ] Pydantic-Schemas in `app/schemas/` + Tests
- [ ] Customer-Form nutzt Pydantic-Validation
- [ ] Rechnungsempfänger ist Override, Default ausgeblendet
- [ ] IBAN-Lookup nur per Button
- [ ] `kdnr`/`short_code` dokumentiert oder entfernt
- [ ] 3+ Tests grün
- [ ] 3+ ADRs geschrieben
- [ ] Manuelle Klick-Strecke: Kunde anlegen → Rechnung erstellen → Speichern → PDF-Vorschau

---

## Quellen

- Nielsen, J. (1994). "10 Usability Heuristics for User Interface Design" — nngroup.com/articles/ten-usability-heuristics/
- Laubheimer, P. (2015). "Preventing User Errors: Avoiding Unconscious Slips" — nngroup.com/articles/slips/
- Baymard Institute — Checkout-Usability-Studien (Address-Forms, Free-Shipping-Threshold)
- Wroblewski, L. (2015). "The Invisible Interface" — lukew.com
- r/UXDesign / r/webdev (Community-Konsens 2023-2025: "Don't ask twice what you know")
- DSGVO Art. 5 (Datenminimierung) — dsgvo-gesetz.de/art-5-dsgvo
- Martin, R. C. (2017). "Clean Architecture" — Pydantic-Models als Application-Layer-Boundary
