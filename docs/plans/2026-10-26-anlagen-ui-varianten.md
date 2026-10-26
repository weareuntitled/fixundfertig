# Plan: Anlagen in der Rechnung – Varianten

Stand: 2026-10-26. Betrifft die Rechnungs-Detailseite
(`frontend/src/routes/_app.invoices.$id.tsx`) und den Versand-Dialog
(`frontend/src/components/invoice/send-invoice-sheet.tsx`).

## Ziel

Beim Versenden einer Rechnung will ich Anlagen (PDF, JPG, PNG) hochladen und
mit einem Haken entscheiden, ob sie mit der E-Mail rausgehen. Die
Rechnungs-PDF bleibt unverändert. Die Anlagen sind eigene Dateien.

Das Wichtigste: Der Knopf muss dort sein, wo ich schon hinschaue, nämlich bei
den Aktionen oben rechts („Zahlungslink“, „An Kunde senden“), und der Haken
muss im Versand-Dialog sichtbar sein, auch wenn noch keine Anlage da ist.

## Ist-Stand (lokal, Branch `feat/anlagen-upload`)

```
┌────────────────────────────────────────────────────────────────────┐
│ ← Rechnungen                                                       │
│ Rechnung #10000      [PDF herunterladen] [Vorschau]                │
│                      [PDF neu erzeugen]  [Zahlungslink]            │
│                      [Bearbeiten] [Löschen]                        │
│                      [📎 Anlage hochladen (1)] [An Kunde senden]   │  <- A
├────────────────────────────────────────────────────────────────────┤
│ Statusverfolgung                                                   │
├──────────────────────────────────────────────┬─────────────────────┤
│ Rechnungsempfänger                           │ Zusammenfassung     │
│ Positionen                                   │ Status ändern       │
│                                              │ ┌─Anlagen (1)─────┐ │  <- B
│                                              │ │ beleg.pdf  ⬇ ✕  │ │
│                                              │ │ [Anlage hochl.] │ │
│                                              │ └─────────────────┘ │
│                                              │ Interne Notizen     │
└──────────────────────────────────────────────┴─────────────────────┘
```

Versand-Dialog:

```
┌─────────────────────────────────────────┐
│ Rechnung senden                         │
│ An Beispiel Kunde · kunde@example.com   │
│                                         │
│ PERSÖNLICHE NACHRICHT (OPTIONAL)        │
│ ┌─────────────────────────────────────┐ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
│ ┌─────────────────────────────────────┐ │
│ │ [x] 📎 Belege mitschicken (1)       │ │  <- C
│ └─────────────────────────────────────┘ │
│ Weitere Anlage hinzufügen: [Anlage +]   │  <- D
│                                         │
│                  [Abbrechen] [Senden]   │
└─────────────────────────────────────────┘
```

A = Knopf in der Kopfzeile, B = Karte in der rechten Spalte,
C = Haken im Dialog, D = Upload im Dialog.

## Offene Frage

Welche Meldung kommt im Browser bei „An Kunde senden“? Im lokalen Stand öffnet
sich nur der Dialog. Vermutlich ist es die Rückfrage von „PDF neu erzeugen“
oder die Live-Version ohne diesen Code.

## Varianten

### Variante 1 – Alles im Dialog (minimal)

Kein Knopf auf der Seite. Hochladen und Haken nur im Dialog „An Kunde senden“.

```
Kopfzeile:   [... Löschen] [An Kunde senden]

Dialog:      Nachricht ...
             ┌─────────────────────────────────────┐
             │ Anlagen                             │
             │  [x] beleg.pdf               ✕      │
             │  [x] foto.jpg                ✕      │
             │  [ + Datei hinzufügen ]             │
             └─────────────────────────────────────┘
                              [Abbrechen] [Senden]
```

- Vorteil: ein Ort, kein Suchen, wenig Code.
- Nachteil: Anlagen sind nur beim Versand sichtbar, nicht auf der Rechnung.

### Variante 2 – Knopf in der Kopfzeile plus Haken im Dialog (empfohlen)

Genau dort, wo du ihn haben willst: neben „Zahlungslink“ und „An Kunde
senden“. Der Dialog zeigt die Anlagen als Liste mit je einem Haken.

```
Kopfzeile:   [PDF herunterladen] [Vorschau] [PDF neu erzeugen]
             [Zahlungslink] [Bearbeiten] [Löschen]
             [📎 Anlage hochladen (2)]   [An Kunde senden]

Dialog:      ┌─────────────────────────────────────┐
             │ Mit der E-Mail senden               │
             │  [x] beleg.pdf          120 KB      │
             │  [ ] foto.jpg           2,1 MB      │
             │  [ + Weitere Anlage ]               │
             └─────────────────────────────────────┘
```

- Vorteil: Knopf dort, wo du ihn erwartest. Pro Anlage entscheidest du einzeln.
- Nachteil: Pro-Anlage-Haken braucht ein Feld mehr in der Datenbank
  (`send_with_email`) und eine Änderung am Versand-Endpoint.

### Variante 3 – Eigene Karte unter den Aktionen

Die Karte „Anlagen“ wandert nach oben, direkt unter die Statusverfolgung,
über die ganze Breite. Der Knopf sitzt rechts in der Kartenzeile.

```
┌──────────────────────────────────────────────────────────────┐
│ 📎 Anlagen (2)                         [Anlage hochladen]    │
│ ──────────────────────────────────────────────────────────── │
│ beleg.pdf   120 KB   [x] mitsenden   ⬇  ✕                    │
│ foto.jpg    2,1 MB   [ ] mitsenden   ⬇  ✕                    │
└──────────────────────────────────────────────────────────────┘
```

- Vorteil: Anlagen immer sichtbar, Haken direkt an der Datei.
- Nachteil: schiebt Positionen und Summen nach unten.

## Vergleich

| | 1 Dialog | 2 Kopfzeile + Dialog | 3 Karte oben |
|---|---|---|---|
| Knopf bei den Aktionen | nein | **ja** | nein |
| Haken pro Datei | nein | ja (Feld nötig) | ja (Feld nötig) |
| Aufwand | klein | mittel | mittel |
| Anlagen auf der Rechnung sichtbar | nein | ja (Zähler) | ja |

## Empfehlung

Variante 2. Sie entspricht dem Wunsch („Knopf bei Zahlungslink und Versand“)
und der Haken sitzt dort, wo entschieden wird. Die rechte Karte (B) bleibt
als Verwaltung: ansehen, herunterladen, entfernen.

## Umsetzung für Variante 2

1. `InvoiceAttachment` bekommt `send_with_email: bool = True`.
2. `POST /api/invoices/{id}/send` nimmt `attachment_ids` statt
   `include_attachments` und versendet nur die gewählten.
3. Dialog zeigt pro Anlage Name, Größe und Haken; Standard: alle angehakt.
4. Tests: Auswahl einzelner Anlagen, leere Auswahl, fremde ID wird abgelehnt.
5. Deploy prüfen: `bash scripts/check-deployment.sh fixundfertig-prod
   https://app.untitled-ux.de <commit>`.

## Nicht Teil dieses Plans

- Anlagen in die Rechnungs-PDF einbetten (bewusst nicht: PDF bleibt sauber).
- Mehr als PDF, JPG, PNG.
