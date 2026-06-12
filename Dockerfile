# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libfreetype6-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Copy React build into static directory
COPY --from=frontend-build /frontend/dist/ ./app/static/frontend/

# /app so `from app.api import ...` resolves to /app/app/api/
# /app/app so bare imports like `from env import ...` resolve to /app/app/env.py
ENV PYTHONPATH=/app:/app/app

EXPOSE 8000

CMD ["python", "-m", "app.main"]
