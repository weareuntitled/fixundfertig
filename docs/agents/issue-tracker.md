# Issue tracker: GitHub

Issues und Spezifikationen liegen in GitHub Issues unter
`weareuntitled/fixundfertig`. Nutze die gh-CLI.

## Konventionen

- Prüfe vor Schreiboperationen mit `gh api repos/weareuntitled/fixundfertig --jq .permissions`, ob der aktive Account Schreibrechte hat. Auf diesem Mac ist dafür der Account `weareuntitled` eingerichtet (`gh auth switch --user weareuntitled`).
- Veröffentliche Spezifikationen und Tickets als GitHub Issues.
- Lies vor der Bearbeitung das Issue einschließlich Kommentaren und Labels.
- Verknüpfe zusammengehörige Issues über Sub-Issues.
  Falls diese nicht verfügbar sind, nutze `Part of #NUMMER`
  im Kind-Issue und eine Aufgabenliste im Eltern-Issue.
- Nutze native Issue-Abhängigkeiten für Blockierungen.
  Falls diese nicht verfügbar sind, nutze `Blocked by: #NUMMER`
  im Issue-Text. Eine Aufgabe ist erst frei, wenn alle Blocker geschlossen sind.
- Nutze die Label-Zuordnung aus `docs/agents/triage-labels.md`.

## Vorhandene lokale Unterlagen

Unter `.scratch/kuenstlername-auf-rechnung/` liegen bereits eine
Spezifikation und Tickets. Prüfe bei Arbeiten an diesem Thema diese
Unterlagen und vorhandene GitHub Issues, um Duplikate zu vermeiden.
Eine Veröffentlichung dieser Bestandsunterlagen ist ein eigener Auftrag.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Wayfinding

Eine Map ist ein Issue mit `wayfinder:map`; Entscheidungstickets sind
verknüpfte Kind-Issues mit `wayfinder:research`, `wayfinder:prototype`,
`wayfinder:grilling` oder `wayfinder:task`.
Lege die benötigten Wayfinder-Labels bei der ersten Nutzung an.

Wähle das erste offene, nicht zugewiesene Kind-Issue ohne offene Blocker
in der Reihenfolge der Map. Weise es zur Übernahme dir selbst zu.
Dokumentiere das Ergebnis im Ticket, schließe es und ergänze die
Entscheidungszusammenfassung der Map mit einem Link.
