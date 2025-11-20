FROM python:3.11-slim

WORKDIR /app

# Install Python reqs
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install supervisor
RUN apt-get update && apt-get install -y supervisor && rm -rf /var/lib/apt/lists/*

# Copy app
COPY monitor.py .
COPY webgui.py .

# Copy default config/db to /defaults (never overwritten)
COPY config.yaml /defaults/config.yaml
COPY streams.db /defaults/streams.db

# Supervisord config
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 7000 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/usr/bin/supervisord"]
