# Python Image
FROM python:3.10-slim

# Arbeitsverzeichnis im Container
WORKDIR /app

# System-Abhängigkeiten installieren (für PDF-Generierung etc.)
RUN apt-get update && apt-get install -y \
    build-essential \
    libfreetype6-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# 1. Requirements kopieren
# Wir nehmen die requirements.txt aus dem Hauptordner (die wir repariert haben)
COPY requirements.txt .

# 2. Installieren
RUN pip install --no-cache-dir -r requirements.txt

# 3. Der entscheidende Schritt:
# Wir kopieren den INHALT von "app/" in das aktuelle Verzeichnis ("/app")
# Dadurch liegt main.py direkt neben requirements.txt im Container.
COPY app/ .

# Port freigeben
EXPOSE 8000

# Startbefehl
# Da wir "flach" kopiert haben, findet er main.py direkt hier.
CMD ["python", "main.py"]
