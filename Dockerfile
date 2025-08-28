# Use the Playwright official Python image (includes browser binaries)
FROM mcr.microsoft.com/playwright/python:v1.54.0-jammy

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your FastAPI application
COPY app.py .

# Expose port 8000
EXPOSE 8000

# Install Playwright browsers (necessary)
RUN playwright install

# Start the FastAPI app with uvicorn using the PORT env var Render provides
CMD ["bash", "-lc", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
