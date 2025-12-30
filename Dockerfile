FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p logs models

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=wsgi.py

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/api/running || exit 1

# Default command (override by docker-compose)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--worker-class", "gevent", "wsgi:app"]