# Use the Playwright official image for the matching browser binaries
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

WORKDIR /app

# Copy requirements and install (playwright is already present in base image)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY app.py .

EXPOSE 8000

# Use PORT env var Render provides (default 8000)
CMD ["bash", "-lc", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
