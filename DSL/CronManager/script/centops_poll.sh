#!/bin/bash

# DEFINING ENDPOINTS

POLL_CENTOPS_ENDPOINT=http://ruuter-public:8086/global-classifier/agencies/data/poll-centops

# CENTOPS_URL, CENTOPS_API_KEY and CENTOPS_API_SECRET are set on the container at deployment.
# Never log them or the AUTH value built from them.
if [ -z "$CENTOPS_URL" ] || [ -z "$CENTOPS_API_KEY" ] || [ -z "$CENTOPS_API_SECRET" ]; then
  echo "CENTOPS POLL SKIPPED: CENTOPS_URL, CENTOPS_API_KEY and CENTOPS_API_SECRET must be set"
  exit 1
fi

AUTH=$(printf '%s:%s' "$CENTOPS_API_KEY" "$CENTOPS_API_SECRET" | base64 -w0)

echo "SENDING REQUEST TO POLL_CENTOPS_ENDPOINT"
response=$(curl -s -w "\n%{http_code}" -X POST "$POLL_CENTOPS_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "X-Centops-Url: $CENTOPS_URL" \
    -H "X-Centops-Authorization: $AUTH" \
    -d '{}')

http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | sed '$d')

# The reply holds only counts or an error message, never URLs or credentials
if [ "$http_code" = "200" ]; then
  echo "CENTOPS POLL SUMMARY: $body"
elif [ "$http_code" = "502" ]; then
  echo "CENTOPS POLL FAILED - CentOps error, retrying at the next hourly poll. HTTP $http_code: $body"
  exit 1
else
  echo "CENTOPS POLL FAILED - HTTP $http_code: $body"
  exit 1
fi
