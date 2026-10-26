#!/bin/bash
source /app/scripts/load_constants.sh

# DEFINING ENDPOINTS

# Ruuter reads the CentOps URL, API key and secret from constants.ini itself
POLL_CENTOPS_ENDPOINT="${GLOBAL_CLASSIFIER_RUUTER_PUBLIC}/agencies/data/poll-centops"

echo "SENDING REQUEST TO POLL_CENTOPS_ENDPOINT"
response=$(curl -s -w "\n%{http_code}" -X GET "$POLL_CENTOPS_ENDPOINT")

http_code=$(echo "$response" | tail -n 1)
body=$(echo "$response" | sed '$d')

# The reply holds only counts or an error message, never URLs or credentials
if [ "$http_code" = "200" ]; then
  echo "CENTOPS POLL SUMMARY: $body"
else
  # A CentOps outage comes back as an empty 500, not a 502, so every failure is logged the same way
  echo "CENTOPS POLL FAILED - the next hourly poll will try again. HTTP $http_code: $body"
  exit 1
fi
