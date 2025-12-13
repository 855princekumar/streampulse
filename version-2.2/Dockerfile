FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        supervisor \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY monitor.py .
COPY webgui.py .
COPY mqtt_service.py .
COPY entrypoint.sh .
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Runtime folders
RUN mkdir -p /var/log/supervisor && \
    mkdir -p /host && \
    chmod +x /app/entrypoint.sh

# Default exposed ports
EXPOSE 7000 8000

ENTRYPOINT ["/app/entrypoint.sh"]
