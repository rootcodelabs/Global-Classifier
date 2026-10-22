#!/bin/bash
source /app/scripts/load_constants.sh

# DEFINING ENDPOINTS

# Ruuter reads the CentOps URL, API key and secret from constants.ini itself
POLL_CENTOPS_ENDPOINT="${GLOBAL_CLASSIFIER_RUUTER_PUBLIC}/agencies/data/poll-centops"

echo "SENDING REQUEST TO POLL_CENTOPS_ENDPOINT"
response=$(curl -s -w "\n%{http_code}" -X POST "$POLL_CENTOPS_ENDPOINT" \
    -H "Content-Type: application/json" \
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
