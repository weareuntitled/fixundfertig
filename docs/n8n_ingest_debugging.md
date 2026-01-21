# n8n Dokumenten-Ingest: Debugging & Fehlerbehandlung

Diese Dokumentation beschreibt den aktuellen n8n-Ingest-Flow, die Validierungen
und die Debugging-Möglichkeiten in der UI.

## Überblick: Request-Flow

**Endpoint:** `POST /api/webhooks/n8n/ingest`

Der Ingest erstellt ein `Document`, speichert die Datei im Storage und hängt die
rohen Payload-Daten an `DocumentMeta`. Die Datei wird anschließend über
`GET /api/documents/{id}/file` ausgeliefert (PDFs und Bilder inline).

## Pflichtfelder & Header

**Headers (Pflicht):**
- `X-Timestamp`: Unix-Timestamp (Sekunden)
- `X-N8N-Secret`: Secret des Unternehmens
- `X-Event-Id`: eindeutige Event-ID (Duplikate werden abgelehnt, Header gewinnt vor Payload)

**Payload (Pflicht):**
- `company_id`
- `file_base64`

**Payload (optional):**
- `event_id` (nur nötig, wenn `X-Event-Id` fehlt)
- `file_name`
- `extracted` (Objekt mit Extraktionsdaten, inkl. `line_items` und `compliance_flags`)

**Hinweis zur Rückwärtskompatibilität:**  
Legacy-Clients dürfen weiterhin Felder wie `vendor`, `doc_date`, `amount_total`, usw.
auf Root-Ebene senden. Diese werden nur dann in `extracted` übernommen, wenn kein
`extracted`-Objekt vorhanden ist.

## file_base64-Format (strict)

Akzeptiert wird:
- Entweder ein vollständiger Data-URI:  
  `data:<mime>;base64,<payload>`
- Oder ein reiner Base64-Payload **ohne Prefix**

**Nicht erlaubt:**
- Werte mit `filesystem-v2`
- Präfixe, die nicht `data:<mime>;base64,` entsprechen
- Nicht-Base64-Strings

## Validierungen im Ingest

1. **Base64 Validierung**  
   Der Payload wird strikt Base64-decodiert. Fehler führen zu `HTTP 400`.

2. **Mindestgröße**  
   Dekodierte Dateien unter **32 Bytes** werden abgelehnt, um leere/korrupt
   gespeicherte Dateien zu vermeiden.

3. **Signaturprüfung (PDF/PNG/JPEG)**  
   Wenn MIME oder Dateiendung auf PDF/PNG/JPEG hindeutet, wird die Datei
   per Magic-Header geprüft:
   - PDF: `%PDF`
   - PNG: `89 50 4E 47 0D 0A 1A 0A`
   - JPEG: `FF D8`

Fehlschläge werden mit **HTTP 400** zurückgegeben und serverseitig geloggt.

4. **Extraktionsfelder (optional)**  
   Falls `extracted` gesetzt ist, werden folgende Formate geprüft:
   - `doc_date`: `YYYY-MM-DD`
   - `amount_*`: String mit zwei Dezimalstellen (`123.45`)
   - `currency`: exakt 3 Zeichen (z. B. `EUR`)

## Debugging in der UI

Im Dokumente-Tab gibt es zwei Hilfen:

1. **Debug-Button**  
   Loggt die aktuell ausgewählten Dokument-IDs in die Browser-Konsole:
   ```
   documents_debug { selected_ids: [...] }
   ```

2. **Events reset**  
   Löscht alle gespeicherten `WebhookEvent`-Einträge, damit `X-Event-Id` erneut
   gesendet werden kann (Duplikate vermeiden).

## Storage-Fehler & Log-Ausgaben

Wenn eine Datei nicht gefunden wird, erscheint im Server-Log:
```
Document file missing for document_id=... storage_path=... storage_key=... resolved_path=...
```
Damit kannst du nachvollziehen, ob die Datei im lokalen Storage oder im
Blob-Storage gesucht wurde.

## Manuelle Test-Checkliste (GUI)

1. **Dokumente öffnen**  
   Stelle sicher, dass Dokumente in der Tabelle auftauchen.

2. **Debug-Button verwenden**  
   Dokumente markieren → **Debug** klicken → Browser-Konsole prüfen.

3. **Events reset nutzen**  
   Bei Duplicate-Events **Events reset** nutzen und neu senden.

4. **PDF/Bild öffnen**  
   „Öffnen“ klicken → Datei wird inline angezeigt, wenn PDF/Bild.
