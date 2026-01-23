#!/bin/bash

# 1. Start Tor with Control Port (9051) and SOCKS (9050) enabled
# We also enable Cookie Authentication so the Python script can talk to it
echo "🍌 Starting Tor with Control Port..."
tor --ControlPort 9051 --SocksPort 9050 --CookieAuthentication 1 &

# 2. Wait for Tor to boot up (crucial!)
sleep 15

# 3. Start the App
echo "🚀 Starting Nano Banana Studio..."
exec gunicorn app:app --bind 0.0.0.0:$PORT
