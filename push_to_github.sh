#!/bin/bash

echo "🚀 Bereite Upload zu GitHub vor..."

# 1. SAUBERES .GITIGNORE (Damit keine DB/Passwörter hochladen!)
echo "🔒 Prüfe .gitignore..."
cat <<EOF > .gitignore
# System & Logs
.DS_Store
*.log
__pycache__/
*.pyc

# Python Umgebung
venv/
.env

# FixundFertig Daten (WICHTIG: Keine Finanzdaten hochladen!)
storage/
*.db
app/storage/

# Editor Settings
.vscode/
.idea/
EOF

# 2. GIT INITIALISIEREN
if [ ! -d ".git" ]; then
    echo "✨ Initialisiere Git..."
    git init
    git branch -M main
fi

# 3. ALLES HINZUFÜGEN
echo "📦 Verpacke Code..."
git add .

# 4. COMMIT
git commit -m "FixundFertig Ultimate Edition (State 2026)"

# 5. REMOTE VERBINDEN
echo ""
echo "🔗 Wir müssen das Ziel kennen."
echo "Bitte füge jetzt die URL deines neuen GitHub Repos ein"
echo "(z.B. https://github.com/DeinName/fixundfertig.git):"
read -p "Repo URL: " REPO_URL

if [ -z "$REPO_URL" ]; then
    echo "❌ Keine URL eingegeben. Abbruch."
    exit 1
fi

# Remote hinzufügen (oder ändern falls existent)
git remote remove origin 2>/dev/null
git remote add origin "$REPO_URL"

# 6. HOCHLADEN
echo "☁️  Lade hoch..."
git push -u origin main

echo ""
echo "✅ Fertig! Dein Projekt ist jetzt sicher auf GitHub."