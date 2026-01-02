FROM python:3.11-slim

WORKDIR /app

# System-Abhängigkeiten (falls später nötig für PDF Tools etc.)
RUN apt-get update && apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libjpeg62-turbo-dev libopenjp2-7-dev libffi-dev
RUN apt-get update && apt-get install -y     curl     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
