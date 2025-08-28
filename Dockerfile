# Use official slim Python image
FROM python:3.11-slim

# Install necessary OS deps for Playwright browsers
RUN apt-get update && apt-get install -y \
    curl ca-certificates libnss3 libatk-1.0-0 libatk-bridge2.0-0 libgtk-3-0 libgbm1 libxss1 libasound2 libcups2 \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python deps
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Copy app
COPY app.py .

# Expose port (Render will map its own $PORT env variable)
EXPOSE 8000

# Use the PORT env var if provided by the host (Render provides PORT)
CMD bash -lc "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"
