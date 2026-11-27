#!/bin/sh
URL="${GATEWAY_INTERNAL_BASE_URL}:${GATEWAY_PORT}${GATEWAY_TEST_ENDPOINT}"
STATUS=$(curl -sk -w "%{http_code}" -o /dev/null "$URL" 2>/dev/null)

if [ -n "$STATUS" ] && [ "$STATUS" -gt 0 ] 2>/dev/null; then
  echo "API Gateway healthcheck OK: HTTP $STATUS"
  exit 0
else
  echo "API Gateway healthcheck failed: no response"
  exit 1
fi
