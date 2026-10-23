# Entwicklung und Prüfungen

## Aktive UI-Einstiege

Die aktuelle Einstellungsseite liegt in `frontend/src/routes/_app.settings.tsx`.
Die älteren `settings.*`-Unterrouten werden vom Elternlayout nicht über ein
`Outlet` gerendert. Ändere Einstellungen auf der aktiven Seite und prüfe sie
mit dem vorhandenen Browser-Test. Der historische Migrationsplan steht in
`docs/react_handoff.md`.

## Python-Umgebung

Lege eine lokale Umgebung mit `uv venv --python 3.11` an. Installiere darin
die bestehenden Abhängigkeiten und Prüfwerkzeuge:

```bash
uv pip install -r requirements.txt pytest ruff mypy pypdf
```

Führe Python-Kommandos mit dem Interpreter dieser Umgebung aus. CI nutzt
Python 3.11 und führt folgende Prüfungen aus:

```bash
python -m ruff check --select E9,F63,F7,F82 app tests scripts
python -m mypy --follow-imports=skip --ignore-missing-imports app/renderer.py app/services/invoice_pdf.py app/services/invoice_pdf_draw.py app/services/invoice_pdf_layout.py
python -m pytest -q
```

Ruff prüft zunächst Syntaxfehler, undefinierte Namen und fehlerhafte
Kontrollausdrücke. Die Typprüfung ist bewusst auf den PDF-Ausgabepfad
begrenzt; ein grüner Lauf bedeutet keine vollständige Backend-Typprüfung.

## Frontend

Führe im Verzeichnis `frontend/` aus:

```bash
npm ci
npm test
npm run build
npm run test:deploy-build
npx playwright install chromium
npm run test:e2e
```

Playwright startet einen eigenen Vite-Server mit der Basis `/` und strikt
belegtem Port. `PLAYWRIGHT_FRONTEND_PORT` wählt bei Bedarf einen anderen Port.
Der Produktionsbuild verwendet weiter `/static/frontend/`; der Build-Check
prüft diesen Pfad und die Revisionsmetadaten.

Die Standard-Browser-Suite isoliert API-Aufrufe und benötigt keine echten
Zugangsdaten. Die drei echten Auth-Tests benötigen `PLAYWRIGHT_FULL_E2E=1`
und einen Test-Owner; sie bleiben standardmäßig übersprungen. Wähle einen
vorbereiteten Python-Interpreter mit `PLAYWRIGHT_PYTHON`. Verwende für echte
Backend-Tests eine isolierte Testdatenbank, niemals Produktionsdaten.
