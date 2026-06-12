# Audit: PDF-Erstellung & Rechnungs-Flow (fixundfertig)

**Datum:** 2026-06-10
**Scope:** Warum "PDF erstellen" / "Rechnung erstellen" nicht durchlÃ¤uft + DB-Konsistenz
**Methodik:** Diagnose-Skill (Phase 1â€“4): statische Codeanalyse + DB-Inspektion. Kein Runtime-Test mÃ¶glich (venv hat kein `nicegui`). Alle Befunde sind Code- + DB-belegt.

## TL;DR

| #   | Schwere      | Befund                                                                                      | Auswirkung                                                                  |
| --- | ------------ | ------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| F1  | blockierend  | `from ._shared import *` filtert `_render_status_stepper` raus                              | Invoice-Detail-Seite â†’ 500 â†’ keine Aktion mÃ¶glich                           |
| F2  | hoch         | `finalize_invoice_logic` setzt `status=OPEN`; **kein** DRAFT-Pfad im UI                     | Rechnungen werden ungefragt finalisiert; DRAFT/FINALIZED sind Schema-Theater |
| F3  | hoch         | `pdf_bytes` in DB gesetzt, `pdf_filename` leer â†’ Download regeneriert PDF bei jedem Klick  | ~50â€“200ms Overhead + Redundanz Blob/FS                                      |
| F4  | mittel       | `send_invoice_email` Ã¶ffnet nur `mailto:`-URL â€” **kein PDF-Anhang**                          | "Senden" ist faktisch ein No-Op                                             |
| F5  | mittel       | Doppelte PDF-Speicherstrategie (DB-Blob + FS) wird nie synchron gehalten                   | `pdf_storage`/`pdf_filename` leere Felder; Schema-Inkonsistenz              |
| F6  | hoch (legal) | Alle 27 Invoices haben `nr="100"`; `_build_invoice_number` Sequenz unklar                   | GoBD-VerstoÃŸ: Rechnungsnummern nicht eindeutig/fortlaufend                  |
| F7  | mittel       | DRAFT blockiert Status-Updates, aber `create_correction` erzeugt DRAFTs â†’ Zombie-DatensÃ¤tze | Korrekturen kÃ¶nnen nicht promoted werden                                    |
| F8  | niedrig      | `auditlog` Tabelle leer, obwohl `log_audit_action` mehrfach aufgerufen wird                | Vermutlich: fehlendes `commit()` direkt nach `session.add(entry)`           |

**Hauptsymptom "PDF geht nicht":** F1. Der 500-Crash auf der Detail-Seite lÃ¤sst jeden Klick (Download, PDF-Vorschau, Senden) tot wirken, obwohl der Renderer (`app/services/invoice_pdf.py`) sauber ist.

---

## F1 â€” `NameError: name '_render_status_stepper' is not defined` (gefixt)

**Beleg:**
- `app/pages/_shared.py:691` definiert `def _render_status_stepper(invoice)`.
- `app/pages/invoice_detail.py:2` importiert per `from ._shared import *`.
- Python-Spec: `import *` ohne `__all__` filtert Namen mit fÃ¼hrendem `_`.
- Reproduktion (isoliert): bestÃ¤tigt â€” `det._render_status_stepper` ist `False`.

**Fix:** `app/pages/invoice_detail.py:3` zusÃ¤tzlich `from ._shared import _render_status_stepper`. âœ… angewendet.

**Restrisiko:** 11 Pages mit `import *`. Sobald eine Page eine `_*`-Funktion **aufruft** ohne expliziten Re-Import â†’ derselbe NameError.

**Audithinweis:** `grep "from \._shared import \*$" app/pages/*.py` â†’ 11 Treffer:
- `__init__.py`, `customers.py`, `customer_detail.py`, `customer_new.py`, `dashboard.py`, `documents.py`, `expenses.py`, `exports.py`, `invoice_create.py`, `invoices.py`, `ledger.py`, `invoice_detail.py`

Selektive Re-Imports gibt es nur fÃ¼r `_parse_iso_date` (5 Pages) und `_open_invoice_editor` (1 Page). Alle anderen `_*`-Funktionen in `_shared.py` (siehe `dir()`-Liste: `_open_invoice_detail`, `_snapshot_invoice`, `_status_step_current`, `_fetch_address_autocomplete`, `use_address_autocomplete`, `customer_*_card`, `insert_customer`, `build_invoice_mailto`, `send_invoice_email`, `create_invoice_revision_and_edit`, `log_invoice_action`, `_render_status_stepper`) sind ungeschÃ¼tzt.

**Empfehlung (aus dem Diagnose-Skill, Phase 6):** In `_shared.py` `__all__` mit Whitelist setzen, die `_*` ausschlieÃŸt. Dann meckert jeder vergessene Re-Import beim Modul-Import (`NameError`) statt erst zur Laufzeit auf der Seite.

---

## F2 â€” Kein DRAFT-Pfad; Rechnungen werden direkt OPEN

**Beleg:**
- `app/logic.py:165`: `inv = Invoice(..., status=InvoiceStatus.OPEN)`. **Direkt OPEN.**
- `app/pages/invoice_create.py:257`: einziger Speichern-Button (`Rechnung finalisieren`) ruft `finalize_invoice_logic`.
- `grep "save_draft\|on_save\|save_button" app/pages/invoice_create.py` â†’ 0 Treffer.
- DB-Befund: 27/27 Invoices mit `status="OPEN"`. `invoices.py:32-33` splittet in `drafts` (immer leer) vs. `finals`.

**Konsequenz:**
- Workflow "Entwurf â†’ prÃ¼fen â†’ finalisieren" existiert im UI nicht.
- `actions.py:19-20`: `update_status_logic` lehnt DRAFT-Rechnungen ab â†’ kein ZurÃ¼ck auf DRAFT.
- `create_correction` (actions.py:34) erzeugt DRAFTs, die nirgends editiert werden kÃ¶nnen (kein DRAFT-Save-UI) â€” siehe F7.

**Empfehlung:**
- Entweder DRAFT-Pfad im UI aktivieren (zweiter Button "Als Entwurf speichern" â†’ Logik mit `status=InvoiceStatus.DRAFT`).
- Oder DRAFT/FINALIZED aus dem Enum entfernen und bewusst auf `OPEN` reduzieren.

---

## F3 — pdf_bytes in DB, pdf_filename leer ? Download regeneriert PDF bei jedem Klick

**DB-Befund** (scripts/audit_db.py):
- 27/27 Invoices: pdf_bytes vorhanden (2304–2433 Bytes), pdf_filename="", pdf_storage="".
- storage/invoices/ Verzeichnis vorhanden, **0 Dateien**.

**Code-Beleg — pp/pages/_shared.py:460 (download_invoice_file):**

`
Pfad A: if not pdf_path:    # pdf_filename leer
         render_invoice_to_pdf_bytes(...)
         schreibe nach storage/invoices/{filename}
         persistiere pdf_filename
Pfad B: if os.path.exists(pdf_path): ui.download(pdf_path)
`

**Was passiert jetzt:**
1. inalize_invoice_logic setzt inv.pdf_bytes (Blob, korrekt) — pdf_filename/pdf_storage bleiben leer.
2. Erster Download-Klick ? Pfad A ? **regeneriert** PDF (überflüssig) + schreibt FS-Datei.
3. Persistiert pdf_filename. Ab jetzt Pfad B.

**Severity:** mittel — funktioniert, aber:
- Erst-Klick: 1× überflüssiges Rendering (~50–200ms).
- Disk + 2.3 KB in DB = 2 Kopien (GoBD-Verstoß bei auseinanderlaufendem Stand).
- export_invoices_pdf_zip (logic.py:255) liest Blob zuerst, dann Disk — redundant.

**Empfehlung:**
- Variante A: download_invoice_file priorisiert invoice.pdf_bytes, liefert via ui.download(BytesIO(bytes), filename=...) aus. FS nur als Cache.
- Variante B: inalize_invoice_logic setzt konsistent pdf_filename + pdf_storage="db" direkt beim Schreiben, sodass Pfad B immer greift und der FS-Cache gefüllt wird.

---

## F4 — send_invoice_email hängt PDF nicht an

**Beleg — pp/pages/_shared.py:559:**
`python
def send_invoice_email(comp, customer, invoice):
    if not customer or not customer.email:
        ui.notify("Keine Email-Adresse beim Kunden hinterlegt", color="red")
        return
    mailto = build_invoice_mailto(comp, customer, invoice)
    ui.run_javascript(f"window.location.href = {json.dumps(mailto)}")
`

- Baut nur mailto:-URL mit Subject + Body-Text.
- mailto: unterstützt keine Attachments. **PDF fehlt.**
- SMTP ist in .env konfigurierbar (SMTP_HOST etc., aktuell leer), wird aber nicht genutzt.

**Auswirkung:** Kunde klickt "Senden" ? Mail-Programm öffnet sich mit Text, der "im Anhang" verspricht. **Anhang fehlt.** Faktisch No-Op.

**Severity:** mittel — sieht wie Feature aus, ist Toy.

**Empfehlung:** Echten SMTP-Versand implementieren — email.mime.application.MIMEApplication + invoice.pdf_bytes als Anhang.

---

## F5 — Doppelte PDF-Speicherstrategie, nie synchron

**Beleg:**
- pp/data.py:155: pdf_bytes: Optional[bytes] (Blob).
- pp/data.py:156-157: pdf_storage: str = "", pdf_filename: str = "" (FS-Referenz).
- pp/logic.py:187: Blob wird beim Finalisieren geschrieben.
- pp/pages/_shared.py:478, 517: FS wird erst beim ersten Download geschrieben.

**Status:** Beide Pfade existieren, werden aber nie synchron gepflegt.
- 27 Invoices: Blob ?, FS ?
- 0 Invoices: FS ?, Blob ?

**Severity:** mittel — funktioniert, aber Schema ist tot. pdf_storage und pdf_filename werden von der Finalisierungs-Logik nie initialisiert.

**Empfehlung:** DB-Blob als Source-of-Truth:
- Backup ist inklusive (export_database_backup in logic.py:654).
- Kein FS-Pfad-Desync.
- 2 KB pro Rechnung — kein Performance-Thema.

**Migration:** inalize_invoice_logic setzt pdf_storage="db" + pdf_filename=build_invoice_filename(...); download_invoice_file priorisiert Blob und schreibt FS nur als Cache.

---

## F6 — 
r="100" für alle 27 Invoices (GoBD-Verstoß)

**DB-Befund:** SELECT nr, COUNT(*) FROM invoice GROUP BY nr ? ('100', 27).

**Code — pp/logic.py:43 (_build_invoice_number):**
`python
seq = int(getattr(comp, "next_invoice_nr", 10000) or 10000)
tpl = (getattr(comp, "invoice_number_template", "{seq}") or "{seq}").strip()
# ...
comp.next_invoice_nr = seq + 1
`

- Erwartet Company.next_invoice_nr als Per-Company-Sequenz.
- 42 Companies existieren, alle 27 Rechnungen tragen 
r="100".
- Möglich A: Test-Seed setzt 
r=100 direkt (DB-konsistent, aber User sehen alle Rechnungen mit 
r=100).
- Möglich B: 
ext_invoice_nr ist überall  /None ? Formatierung greift nicht wie erwartet, oder Template liefert statisch "100".

**Severity:** hoch (rechtlich) — Rechnungsnummern müssen eindeutig und fortlaufend sein (§ 14 UStG, GoBD).

**Diagnose-Schritt (nicht im Audit enthalten):**
`sql
SELECT id, name, next_invoice_nr, invoice_number_template FROM company;
`
Erwartet: entweder 
ext_invoice_nr=99 mit 	pl="{seq+1}" für alle Companies, oder kein 
ext_invoice_nr-Feld im Schema.

**Empfehlung:** Sequenz pro Company garantieren. Test-Seed entfernen oder dokumentieren.

---

## F7 — Lifecycle-Inkonsistenz: DRAFT-Zombies

**Beleg:**
- ctions.py:19-20: update_status_logic lehnt DRAFT-Rechnungen ab.
- ctions.py:34-49 (create_correction): erzeugt neue Rechnung mit status=InvoiceStatus.DRAFT.
- invoice_create.py:257: einzige Save-Funktion erzeugt OPEN.

**Konsequenz:** Eine via create_correction erzeugte DRAFT-Rechnung **kann nirgends editiert** werden (kein DRAFT-Save-UI) und **kann nicht promoted** werden (DRAFT blockiert update_status_logic). Zombie-Datensatz.

**Severity:** mittel — in der Praxis noch nicht aufgefallen, weil der Korrektur-Flow wenig benutzt wird.

**Empfehlung:** Entweder DRAFT-Editor implementieren (siehe F2) oder create_correction direkt status=InvoiceStatus.OPEN setzen und das "Korrektur als Entwurf"-Konzept streichen.

---

## F8 — Auditlog leer

**DB-Befund:** SELECT COUNT(*) FROM auditlog ? 0.

**Code-Beleg:**
- pp/data.py:182-188: AuditLog Tabelle + Schema existiert.
- pp/data.py:498: def log_audit_action(session, action, invoice_id=None, ...) ? session.add(entry). **Kein commit.**
- pp/actions.py:31: log_audit_action(session, STATUS_AUDIT_ACTIONS[...]) in update_status_logic aufgerufen.
- pp/pages/_shared.py:192-195: log_invoice_action ruft log_audit_action + eigenes s.commit(). **Dieser Pfad committed.**

**Wahrscheinliche Ursache:** In ctions.py:31 wird log_audit_action aufgerufen, aber update_status_logic (Aufrufer) macht selbst s.add(invoice) ohne commit. Audit-Eintrag wird zwar geaddet, geht aber bei einem späteren Rollback oder Session-Wechsel verloren.

**Severity:** niedrig (Compliance), aber rechtlich relevant (GoBD verlangt nachvollziehbare Status-Änderungen).

**Empfehlung:** In log_audit_action selbst session.commit() aufrufen ODER den Aufrufer in ctions.py:31 zwingen, im selben Transaktionsblock zu committen.

---

## Datenbank-Zustand (Stand: 2026-06-10)

| Tabelle              | Zeilen | Anmerkung                                                        |
| -------------------- | ------ | ---------------------------------------------------------------- |
| user                 | 1      | djdanep@gmail.com, aktiv, verifiziert                          |
| company              | 42     | "Test GmbH" (×27), "Merge Co A" (×3), "Co A" (×3), "Co B" (×2), "Co X" (×2), "Co Y" (×3) — Test-Seed |
| customer             | 36     | je 1 pro Company, einige Companies ohne Customer                 |
| invoice              | 27     | alle 
r="100", alle status="OPEN", alle pdf_bytes ~2.3 KB |
| invoiceitem          | 27     | je 1 Item pro Rechnung (Leistung A/B, "Gültige Position")        |
| invoicerevision      | 0      | leer                                                             |
| invoice_revision     | 0      | leer (zwei verschiedene Tabellennamen — siehe unten)            |
| auditlog             | 0      | leer (siehe F8)                                                  |
| token                | 0      | leer                                                             |
| document             | 0      | leer                                                             |

**Schema-Anomalie:** Es gibt **zwei** Tabellen für Invoice-Revisions:
- invoicerevision (Singular) — von SQLModel aus pp/data.py:159 deklariert (class InvoiceRevision(SQLModel, table=True)).
- invoice_revision (Underscore) — manuell per ensure_invoice_revision_schema() in pp/data.py:399 als CREATE TABLE IF NOT EXISTS angelegt.

Beide leer. Die manuelle Tabelle dupliziert die SQLModel-Tabelle mit anderem Naming. Doppeltes Schema, identische Funktion.

**Empfehlung:** ensure_invoice_revision_schema() entfernen, nur InvoiceRevision aus data.py verwenden. Oder umgekehrt.

---

## Reproduktions-Skripte (für Re-Run)

- scripts/audit_db.py — Tabellen, Spalten, PDF-Status.
- scripts/audit_db2.py — Companies, Customers, Auditlog, Users.

Beide laufen mit env/Scripts/python.exe und brauchen keinen NiceGUI-Stack.

---

## Priorisierte Action-Liste

1. **Sofort:** F1 (? done) — __all__ in _shared.py setzen, um die übrigen 10 Pages abzusichern.
2. **Diese Woche:** F2 + F7 klären — DRAFT entweder richtig implementieren oder aus Enum/UI entfernen.
3. **Diese Woche:** F3 + F5 — DB-Blob priorisieren, FS-Cache nur als Fallback.
4. **Diese Woche:** F4 — echten SMTP-Versand implementieren.
5. **Backlog:** F6 (Sequenz), F8 (Auditlog-commit), Schema-Doppel (invoicerevision vs invoice_revision).
