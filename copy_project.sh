#!/bin/bash

OUTfile="temp_code_export.txt"

# Ordner die wir komplett ignorieren (Gar nicht erst reingehen)
IGNORE_DIRS="-name venv -o -name .git -o -name __pycache__ -o -name n8n_data -o -name storage -o -name .vscode -o -name .idea"

echo "=== PROJEKT STRUKTUR ===" > "$OUTfile"
find . \( $IGNORE_DIRS \) -prune -o -print | sort >> "$OUTfile"

echo "" >> "$OUTfile"
echo "=== DATEI INHALTE ===" >> "$OUTfile"

find . \
    \( $IGNORE_DIRS \) -prune \
    -o -type f \( -name "*.py" -o -name "*.yml" -o -name "*.txt" -o -name "*.sh" -o -name "*.md" -o -name "Dockerfile" \) \
    -not -name ".env" \
    -not -name ".DS_Store" \
    -not -name "copy_project.sh" \
    -not -name "$OUTfile" \
    -exec echo "" >> "$OUTfile" \; \
    -exec echo "--- DATEI: {} ---" >> "$OUTfile" \; \
    -exec cat {} >> "$OUTfile" \;

if command -v pbcopy &> /dev/null; then
    cat "$OUTfile" | pbcopy
    echo "✅ Fertig! Code kopiert (ohne venv/git/storage)." 
else
    echo "❌ pbcopy nicht gefunden. Inhalt liegt in $OUTfile"
fi

rm "$OUTfile"
