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
