#!/bin/sh
# This script contains the tickler logic to keep the API Gateway session alive.
# It continuously sends POST requests to the tickle endpoint at a specified interval.

echo "[tickler] Tickler service started."

# The 'while true' loop ensures the script runs indefinitely,
# continuously sending requests to the tickle endpoint.
while true; do
  NOW=$(date) # Get the current timestamp
  # Log the action, including the current time and the target URL.
  echo "[tickler] $NOW: Sending tickle to ${TICKLE_BASE_URL}${TICKLE_ENDPOINT}"

  # Send a POST request using curl.
  # -s: Silent mode
  # -k: Allow insecure server connections (if needed)
  # -X POST: Specify POST request method
  # -H "Content-Type: application/json": Set the Content-Type header
  # -d "{}": Send an empty JSON object as data
  # -w " HTTP status: %{http_code}\n": Output the HTTP status code after the request
  curl -sk -X POST "${TICKLE_BASE_URL}${TICKLE_ENDPOINT}" -H "Content-Type: application/json" -d "{}" -w " HTTP status: %{http_code}\n"

  # Pause execution for the duration specified by TICKLE_INTERVAL.
  sleep "${TICKLE_INTERVAL}"
done
