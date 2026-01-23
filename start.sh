#!/bin/bash

# 1. Start Tor in the background
echo "🍌 Starting Tor..."
tor &

# 2. Wait a few seconds for Tor to bootstrap
sleep 10

# 3. Start the Flask App using Gunicorn (Production Server)
# Render automatically provides the $PORT variable
echo "🚀 Starting Nano Banana Studio..."
exec gunicorn app:app --bind 0.0.0.0:$PORT
