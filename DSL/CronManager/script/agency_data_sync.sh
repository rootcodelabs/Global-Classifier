#!/bin/bash

# DEFINING ENDPOINTS

SYNC_CLIENT_DATA_ENDPOINT=http://ruuter-public:8086/global-classifier/agencies/data/start-generation

# Construct payload to update training status using cat
payload=$(cat <<EOF
{}
EOF
)

echo "SENDING REQUEST TO SYNC_CLIENT_DATA_ENDPOINT"
response=$(curl -s -X POST "$SYNC_CLIENT_DATA_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$payload")

started=$(echo "$response" | sed -n 's/.*"started":[[:space:]]*\(true\|false\).*/\1/p')
reason=$(echo "$response" | sed -n 's/.*"reason":[[:space:]]*"\([^"]*\)".*/\1/p')

if [ -n "$started" ]; then
  echo "START GENERATION: started=$started reason=${reason:-none}"
else
  echo "START GENERATION RESPONSE:"
  echo "$response"
fi
