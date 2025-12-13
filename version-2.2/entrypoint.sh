#!/bin/bash
set -e

echo "🔧 StreamPulse EntryPoint starting..."

# Ensure supervisor log directory exists
mkdir -p /var/log/supervisor

# Ensure host mount exists
mkdir -p /host

# Copy default config if missing
if [ ! -f /host/config.yaml ]; then
    echo "📄 No config.yaml found in /host → copying default."
    cp /app/config.yaml /host/config.yaml 2>/dev/null || true
fi

# Copy DB if missing
if [ ! -f /host/streams.db ]; then
    echo "🗄  No DB found in /host → copying default."
    cp /app/streams.db /host/streams.db 2>/dev/null || true
fi

# Link config + DB into app folder
ln -sf /host/config.yaml /app/config.yaml
ln -sf /host/streams.db /app/streams.db

echo "🚀 Launching Supervisor..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
