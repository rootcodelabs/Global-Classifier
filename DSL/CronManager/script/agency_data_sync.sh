#!/bin/bash

# DEFINING ENDPOINTS

SYNC_CLIENT_DATA_ENDPOINT=http://ruuter-public:8086/global-classifier/agencies/data/sync

# Construct payload to update training status using cat
payload=$(cat <<EOF
{}
EOF
)

echo "SENDING REQUEST TO SYNC_CLIENT_DATA_ENDPOINT"
response=$(curl -s -X POST "$SYNC_CLIENT_DATA_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$payload")

sync_summary=$(echo "$response" | sed -n 's/.*"syncSummary":\({[^}]*}\).*/{"syncSummary":\1}/p')

if [ -n "$sync_summary" ]; then
  echo "SYNC SUMMARY: $sync_summary"
else
  echo "DATA IMPORT SUMMARY:"
  echo "$response"
fi
