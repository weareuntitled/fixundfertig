# Deployment (Hostinger + Docker)

## Voraussetzungen
- Docker + Docker Compose auf dem Server installiert.
- Zwei Subdomains (z. B. `app.example.com` und `n8n.example.com`) zeigen per DNS auf den Server.

## Setup
1. `.env.example` nach `.env` kopieren und Domains/Secret setzen.
2. Production-Stack starten:
   ```bash
   APP_REVISION=$(git rev-parse HEAD) docker compose -f docker-compose.prod.yml up -d --build
   ```
3. Caddy holt automatisch TLS-Zertifikate für beide Subdomains.

## Hinweise
- App-Daten (SQLite + Uploads) liegen im Volume `app_storage`.
- n8n Daten liegen im Volume `n8n_data`.
- Für eine sichere Session-Konfiguration `STORAGE_SECRET` unbedingt ändern.

## Sicherer Deploy
- GitHub Actions deployt nur nach erfolgreichen Backend- und Frontend-Checks.
- Der Deploy-Key in `SSH_PRIVATE_KEY` muss zum lokalen SSH-Alias `fixundfertig-prod` passen; der Workflow bevorzugt dieses Secret vor `SERVER_SSH_KEY`.
- Der Server-Deploy bricht bei lokalen Änderungen außerhalb von `backups/` ab; er setzt den Arbeitsbaum nicht zurück.
- Backup-Archive unter `backups/*.tar.gz` bleiben auf dem Server und werden nicht versioniert.
- Der App-Container meldet Readiness und Revision über `/healthz`; das gebaute Frontend enthält dieselbe Revision in `meta[name="app-revision"]`.
- Der Deploy wartet auf healthy und prüft die Container-Revision gegen den Server-Checkout, bevor er Images aufräumt.
- Lokale Serveränderungen vor einem manuellen Update zuerst sichern und prüfen. Wiederherstellung aus einem Stash erfolgt bewusst mit `git stash apply`, nicht `pop`.

## Deployment verifizieren

Prüfe Server-Checkout, Containerzustand, Backend-Readiness und die Revision des ausgelieferten Frontends mit:

```bash
bash scripts/check-deployment.sh fixundfertig-prod https://app.untitled-ux.de EXPECTED_COMMIT
```

`EXPECTED_COMMIT` ist optional. Ohne Angabe gilt der Commit des Server-Checkouts als erwartet.

## Direkter SSH-Zugang vom Mac
Der Alias `fixundfertig-prod` verbindet als `root` mit dem Hostinger-Server über den dedizierten Schlüssel `~/.ssh/fixundfertig_hostinger_20261021`. Der Host-Key ist in `~/.ssh/fixundfertig_hostinger_known_hosts` gepinnt. Nach Einrichtung des SSH-Config-Eintrags genügt:

```bash
ssh fixundfertig-prod
```
