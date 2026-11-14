FROM python:3.11-slim

WORKDIR /app

# System deps: gcc cho asyncpg, libpq-dev cho PostgreSQL client
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ source (production: không dùng volume mount)
COPY . .

EXPOSE 8000
