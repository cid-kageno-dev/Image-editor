# Use a lightweight Python base image
FROM python:3.9-slim

# 1. Install System Dependencies (Tor and functionality for it)
RUN apt-get update && apt-get install -y \
    tor \
    procps \
    && rm -rf /var/lib/apt/lists/*

# 2. Set working directory
WORKDIR /app

# 3. Copy files
COPY . /app

# 4. Install Python Dependencies
# We install Gunicorn for production server
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 5. Make the start script executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# 6. Command to run when container starts
CMD ["./start.sh"]
