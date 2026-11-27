---
name: angebot
description: Angebot für einen Kunden schreiben und als Entwurf in fixundfertig anlegen. Verwenden, wenn Daniel ein Angebot, einen Kostenvoranschlag oder Preise für einen Kunden will, auch wenn nur Leistungen und Kunde genannt werden.
---

# Angebot schreiben

Ein Angebot entsteht als JSON-Datei und landet mit einem Befehl als Entwurf in fixundfertig. Die Weboberfläche ist nur zum Prüfen und Versenden da.

## Schritte

1. Positionen, Stunden und Zahlungsbedingungen nach den **Vorgaben** unten aufstellen und Daniel als Tabelle zeigen (Pos., Leistung, Menge, Netto, Summe, Raten). Fertig, wenn Daniel die Summe bestätigt.
2. JSON nach dem Format im Kopf von `scripts/angebot.py` schreiben, in `.scratch/angebote/<kunde>-<variante>.json` (Vorlage: [`beispiel.json`](beispiel.json)).
3. `.venv/bin/python scripts/angebot.py <datei> --probelauf` zeigt Summen und Raten ohne Anmeldung. Fertig, wenn sie der bestätigten Tabelle entsprechen.
4. Ohne `--probelauf` anlegen. Braucht `FF_EMAIL` und das Passwort im Schlüsselbund (Befehl im Skriptkopf). Fehlt es, Daniel den Befehl geben; das Passwort tippt er selbst.
5. Daniel die Angebotsnummer und den Link nennen. Versenden macht Daniel über „Angebot senden“.

## Vorgaben

- **Absender:** Firma „Untitled-UX“ (`"firma": "Untitled-UX"`).
- **Stundensatz:** 70 € netto. Positionen in Stunden (`"menge": 1.5`, `"preis": 70`), Beschreibung endet auf „(Stunden)“.
- **Zahlungsplan:** immer 50 % bei Auftrag, 50 % nach Fertigstellung (bei Websites „nach Freischaltung“).
- **Zahlungsziel:** kleine Aufträge 14 Tage ohne Abzug. Größere Aufträge (ab etwa 1.000 €) 30 Tage, 3 % Skonto bei Zahlung innerhalb von 14 Tagen.
- **Zahlungsbedingungen und Hinweise gehören in die Einleitung**; ein eigenes Feld dafür gibt es nicht.
- **Puffer:** bei alter oder fremder Technik eine eigene Position „Test und Puffer“ (etwa 1 h).
- **Varianten** (z. B. alte Seite fit machen vs. neue Seite): je ein eigenes Angebot. Gemeinsame Leistungen stehen in beiden gleich, ohne Abzug.

## Sprache

Kunden sind meist keine Technikleute. Jede Position nennt den Nutzen in Alltagssprache.

- „Bereit für Werbung“ statt „Landingpages“; „besser gefunden werden bei Google“ statt „SEO“; „sichere Verbindung (Schloss im Browser)“ statt „SSL“.
- Nur versprechen, was die Technik hergibt („soweit die alte Technik es zulässt“). Bei netcup-Webhosting keine Aussagen wie „ohne Cookies“.

## Bausteine (Stunden als Richtwert)

| Baustein | Std. |
|---|---|
| E-Mail und Domain einrichten (Postfach, Zustellung ohne Spam, Schloss im Browser, Anleitung Handy/PC) | 1,5–1,75 |
| Kontaktformular mit Spamschutz | 2 (neu) / 3 (alte Technik) |
| Sicherheits-Update alte Website | 2 |
| Eigenes Design | 6 |
| Neue Website, alle Seiten mit Texten und Bildern | 12 |
| Bereit für Werbung: eine Werbeseite plus Vorlagen für weitere | 6 |
| Besser gefunden werden bei Google (Weiterleitungen, Titel, Beschreibungen) | 2 |
| Übergabe: Freischaltung, Einweisung, Zugangsdaten | 1 |
