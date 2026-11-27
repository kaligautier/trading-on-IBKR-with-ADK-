#!/bin/bash

# Start the API Gateway in the background
cd /app/api_gateway
sh bin/run.sh root/conf.yaml &

# Wait for the API Gateway to become healthy before starting the tickler
echo "Waiting for API Gateway to become healthy..."
while ! /usr/local/bin/healthcheck.sh > /dev/null 2>&1; do
  echo "API Gateway not ready yet, waiting..."
  sleep 2
done

echo "API Gateway is healthy, starting tickler..."
/app/tickler.sh &

# Start the auto-login server
echo "Starting auto-login server..."
source /app/set_chromium.sh
echo "Using Chromium at: $CHROMIUM_PATH"
cd /app/auto_login
node server.js &

# Wait for all background processes to keep container alive
wait