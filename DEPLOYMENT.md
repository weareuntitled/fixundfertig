# Deployment (Hostinger + Docker)

## Voraussetzungen
- Docker + Docker Compose auf dem Server installiert.
- Zwei Subdomains (z. B. `app.example.com` und `n8n.example.com`) zeigen per DNS auf den Server.

## Setup
1. `.env.example` nach `.env` kopieren und Domains/Secret setzen.
2. Production-Stack starten:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```
3. Caddy holt automatisch TLS-Zertifikate für beide Subdomains.

## Hinweise
- App-Daten (SQLite + Uploads) liegen im Volume `app_storage`.
- n8n Daten liegen im Volume `n8n_data`.
- Für eine sichere Session-Konfiguration `STORAGE_SECRET` unbedingt ändern.

## Sicherer Deploy
- GitHub Actions deployt nur nach erfolgreichen Backend- und Frontend-Checks.
- Der Server-Deploy bricht bei lokalen Änderungen außerhalb von `backups/` ab; er setzt den Arbeitsbaum nicht zurück.
- Backup-Archive unter `backups/*.tar.gz` bleiben auf dem Server und werden nicht versioniert.
- Der App-Container meldet Readiness über `/healthz`; der Deploy wartet auf healthy, bevor er Images aufräumt.
- Lokale Serveränderungen vor einem manuellen Update zuerst sichern und prüfen. Wiederherstellung aus einem Stash erfolgt bewusst mit `git stash apply`, nicht `pop`.

## Direkter SSH-Zugang vom Mac
Der Alias `fixundfertig-prod` verbindet als `root` mit dem Hostinger-Server über den dedizierten Schlüssel `~/.ssh/fixundfertig_hostinger_20261021`. Der Host-Key ist in `~/.ssh/fixundfertig_hostinger_known_hosts` gepinnt. Nach Einrichtung des SSH-Config-Eintrags genügt:

```bash
ssh fixundfertig-prod
```
