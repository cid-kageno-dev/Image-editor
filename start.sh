#!/bin/bash

# 1. Start Tor with Control Port (9051) enabled
# We use --CookieAuthentication 1 so our Python script can authenticate safely
echo "🍌 Starting Tor..."
tor --ControlPort 9051 --SocksPort 9050 --CookieAuthentication 1 &

# 2. Wait for Tor to bootstrap
# Tor needs time to build circuits. We wait 15s to avoid initial connection errors.
sleep 15

# 3. Start Gunicorn (Max Capacity Mode for Free Tier)
# --workers 1      : Keeps RAM usage low (~150MB base) to avoid OOM crashes.
# --threads 8      : Allows 8 concurrent requests (ideal for I/O heavy apps like this).
# --worker-class=gthread : Optimized threading for waiting on external APIs.
# --timeout 300    : 5-minute timeout because Tor/Image Gen can be slow.

echo "🔥 Starting Nano Banana (Max Requests)..."
exec gunicorn --workers 1 --threads 8 --worker-class=gthread --timeout 300 app:app --bind 0.0.0.0:$PORT
