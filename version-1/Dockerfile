FROM python:3.11-slim


WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Create data directory for persistent DB/config
RUN mkdir -p /data
VOLUME ["/data"]

# Expose Flask port
EXPOSE 8000

# Start both monitor and webgui
CMD ["sh", "-c", "python monitor.py & python webgui.py"]
