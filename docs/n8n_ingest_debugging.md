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

## Payload erstellen (ausführliche Anleitung)

Die **kanonische Payload** enthält nur die Felder auf Root-Ebene, die wirklich
gebraucht werden. Extrahierte Metadaten liegen **immer** unter `extracted`.

### 1) Minimale Payload (nur Pflichtfelder)

```json
{
  "company_id": 123,
  "file_base64": "JVBERi0xLjQKJ...."
}
```

Wenn `X-Event-Id` als Header fehlt, muss zusätzlich `event_id` im Body gesetzt
werden.

### 2) Kanonische Payload mit `extracted`

```json
{
  "company_id": 123,
  "event_id": "evt-2024-0001",
  "file_name": "rechnung_2024-01.pdf",
  "file_base64": "data:application/pdf;base64,JVBERi0xLjQKJ....",
  "extracted": {
    "vendor": "ACME GmbH",
    "doc_date": "2024-01-31",
    "doc_number": "INV-001",
    "amount_total": "123.45",
    "amount_net": "100.00",
    "amount_tax": "23.45",
    "currency": "EUR",
    "summary": "Bürobedarf Januar",
    "keywords": ["büro", "bedarf", "januar"],
    "line_items": [
      {"description": "Papier A4", "quantity": 2, "price": "10.00"}
    ],
    "compliance_flags": [
      {"code": "VAT_MISMATCH", "severity": "warning"}
    ]
  }
}
```

### 3) Legacy-Payload (nur für alte Clients)

Legacy-Clients dürfen weiterhin Root-Felder wie `vendor` oder `doc_date` senden.
Diese werden **nur dann** verwendet, wenn `extracted` fehlt.

```json
{
  "company_id": 123,
  "event_id": "evt-legacy-0001",
  "file_base64": "JVBERi0xLjQKJ....",
  "vendor": "Alt GmbH",
  "doc_date": "2024-02-01",
  "amount_total": "50.00",
  "currency": "EUR"
}
```

### 4) Gemischte Payload (nicht empfohlen)

Wenn `extracted` vorhanden ist, werden gleichnamige Root-Felder ignoriert.

```json
{
  "company_id": 123,
  "event_id": "evt-mixed-0001",
  "file_base64": "JVBERi0xLjQKJ....",
  "vendor": "Ignoriert",
  "extracted": {
    "vendor": "Verwendet",
    "doc_date": "2024-03-05",
    "amount_total": "10.00",
    "currency": "CHF"
  }
}
```

### 5) Header (Pflicht)

Beispiel-Header für HMAC-Signatur (empfohlen):

```
X-Timestamp: <unix-timestamp>
X-Signature: <hex-signatur>
```

Alternative (Legacy): `X-N8N-Secret` + `X-Event-Id`.

### 6) Validierungsregeln für `extracted`

- `doc_date`: `YYYY-MM-DD` (z. B. `2024-01-31`)
- `amount_*`: String mit genau **2 Dezimalstellen** (`"123.45"`)
- `currency`: exakt **3 Zeichen** (z. B. `EUR`)
- Leere Strings vermeiden: Feld besser **weglassen** als `""` senden.

### 7) Tipps zum Base64-String

- Bei PDFs/Bildern möglichst Data-URI verwenden:
  `data:application/pdf;base64,<payload>`
- Keine Whitespaces im Base64-String.
- Datei muss > 32 Bytes sein (Mindestgröße).

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

## Outbound Webhook bei manuellem Upload (FixundFertig → n8n)

Wenn ein Dokument **manuell** hochgeladen wird, sendet die App die Datei per
**Outbound Webhook** an die in den Settings konfigurierte n8n-URL (nur wenn n8n
aktiviert ist). Das Dokument erscheint erst in der Liste, nachdem n8n den
Ingest zurück an die App gesendet hat. Der Status wird in den Settings angezeigt
und kann per Button getestet werden.

### Gesendete Payload (Beispiel)

Die App sendet JSON mit HMAC-Signatur. Header:

```
X-API-KEY: <n8n secret>
X-Signature: <sha256 hmac>
Content-Type: application/json
```

Body-Format (vereinfacht):

```json
{
  "event": "document_upload",
  "company_id": "123",
  "ts": 1710000000,
  "data": {
    "file_name": "rechnung.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 123456,
    "file_base64": "data:application/pdf;base64,JVBERi0xLjQKJ...."
  }
}
```

Das Format basiert auf dem `post_to_n8n`-Client (HMAC über den JSON-Body).

### Empfang in n8n (Webhook Trigger)

1. **Webhook-Trigger** in n8n anlegen (Production URL) und diese URL in den
   App-Settings als „n8n Webhook URL“ eintragen.
2. **Secret** aus der App übernehmen (Header `X-API-KEY`).
3. **HTTP-Methode auf POST stellen**, da die App JSON im Body sendet.
4. Optional: Signatur im n8n-Workflow prüfen (HMAC SHA-256 auf den rohen Body).

### Weiterleitung in den bestehenden Ingest (Mail-Scraping-Flow)

Wenn du den **gleichen Ingest** verwenden willst wie beim Mail-Scraping:

1. `data.file_base64` aus dem Webhook übernehmen.
2. Optional: Metadaten ergänzen (z. B. `file_name`, `vendor`, `doc_date`).
3. An den bestehenden Ingest-Endpunkt senden:  
   `POST /api/webhooks/n8n/ingest` mit `company_id`, `event_id`, `file_base64` und
   optional `extracted` (Metadaten).

Damit laufen **manuelle Uploads** über denselben Ingest-Pfad wie Mail-Scraping,
inkl. Validierung und Speicherung im Dokumenten-Storage.

## Manuelle Test-Checkliste (GUI)

1. **Dokumente öffnen**  
   Stelle sicher, dass Dokumente in der Tabelle auftauchen.

2. **Debug-Button verwenden**  
   Dokumente markieren → **Debug** klicken → Browser-Konsole prüfen.

3. **Events reset nutzen**  
   Bei Duplicate-Events **Events reset** nutzen und neu senden.

4. **PDF/Bild öffnen**  
   „Öffnen“ klicken → Datei wird inline angezeigt, wenn PDF/Bild.
