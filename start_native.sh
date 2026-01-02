#!/bin/bash

# Farben für schönere Ausgabe
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starte FixundFertig (Native Mode - Ohne Docker)${NC}"

# -----------------------------------------------
# 🛠 MAC OS FIX FÜR WEASYPRINT / PANGO
# -----------------------------------------------
# Zwingt Python, in den Homebrew-Ordnern nach Bibliotheken zu suchen
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 macOS erkannt: Setze Pfade für Homebrew Bibliotheken..."
    export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:/usr/local/lib:$DYLD_FALLBACK_LIBRARY_PATH"
fi
# -----------------------------------------------

# 1. PRÜFUNGEN
# -----------------------------------------------
# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 nicht gefunden! Bitte installiere Python.${NC}"
    exit 1
fi

# Check Node.js (für n8n nötig)
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ Node.js / npm nicht gefunden!${NC}"
    echo "n8n benötigt Node.js. Bitte installiere es hier: https://nodejs.org/"
    echo "Die App startet trotzdem, aber ohne Automatisierung."
    HAS_NODE=false
else
    HAS_NODE=true
fi

# 2. PYTHON APP SETUP
# -----------------------------------------------
echo -e "${BLUE}🐍 Richte Python Umgebung ein...${NC}"

cd app

# Venv erstellen falls nicht vorhanden
if [ ! -d "venv" ]; then
    echo "Erstelle virtuelle Umgebung..."
    python3 -m venv venv
fi

# Aktivieren
source venv/bin/activate

# Pakete installieren (Silent mode, außer bei Fehler)
echo "Installiere/Update Abhängigkeiten (sqlmodel, nicegui, weasyprint)..."
pip install -r requirements.txt > /dev/null

# 3. START PROZESSE
# -----------------------------------------------
# Funktion um beim Beenden (Ctrl+C) alles zu killen
trap 'kill 0' EXIT

echo -e "${GREEN}✅ Setup fertig.${NC}"

# Start n8n (im Hintergrund)
if [ "$HAS_NODE" = true ]; then
    echo -e "${BLUE}🤖 Starte n8n Automatisierung...${NC}"
    # npx startet n8n ohne globale Installation
    npx n8n start > ../n8n_log.txt 2>&1 &
    N8N_PID=$!
    echo "n8n läuft unter PID $N8N_PID (Logs in n8n_log.txt)"
else
    echo -e "${RED}⚠️  Überspringe n8n Start (Node.js fehlt)${NC}"
fi

# Start Python App
echo -e "${BLUE}💻 Starte NiceGUI App...${NC}"
echo "---------------------------------------------------"
echo -e "👉 App URL:   ${GREEN}http://localhost:8080${NC}"
if [ "$HAS_NODE" = true ]; then
    echo -e "👉 n8n URL:   ${GREEN}http://localhost:5678${NC}"
fi
echo "---------------------------------------------------"
echo "Drücke Ctrl+C um alles zu beenden."
echo ""

# App starten
python3 main.py

# Warten
wait