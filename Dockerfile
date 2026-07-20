# MerakiMind AIOps Platform — Backend Dockerfile
FROM python:3.11-slim

# Install system dependencies (build-essential, curl, fonts for PDF Unicode)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    fontconfig \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY config.py pipeline.py server.py /app/
COPY api/ /app/api/
COPY agents/ /app/agents/
COPY models/ /app/models/
COPY MERAKI_API_DOCUMENTATION.md MERAKI_API_DOCUMENTATION.docx /app/

# Expose backend port
EXPOSE 8765

# Healthcheck
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8765/api/health || exit 1

# Start Python HTTP Server
CMD ["python", "server.py"]
