#!/bin/bash

HOST_CFG="/host/config.yaml"
HOST_DB="/host/streams.db"

# Create host folder if missing
mkdir -p /host

# If host config missing → initialize
if [ ! -f "$HOST_CFG" ]; then
    echo "No host config found → copying default"
    cp /defaults/config.yaml "$HOST_CFG"
fi

# If host DB missing → initialize
if [ ! -f "$HOST_DB" ]; then
    echo "No host DB found → copying default"
    cp /defaults/streams.db "$HOST_DB"
fi

# SYNC: mount host files into /app (this is the magic)
ln -sf "$HOST_CFG" /app/config.yaml
ln -sf "$HOST_DB" /app/streams.db

echo "Using config → $HOST_CFG"
echo "Using DB     → $HOST_DB"

exec "$@"
