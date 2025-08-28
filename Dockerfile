# Use Playwright's official Python image (includes browsers & deps)
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app sources
COPY app.py .

# Expose port (Render will set PORT env var)
EXPOSE 8000

# Start uvicorn using Render's PORT environment variable
CMD ["bash", "-lc", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
