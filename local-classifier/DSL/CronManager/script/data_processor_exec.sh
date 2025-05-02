#!/bin/bash

echo "Started Shell Script to process"
# Ensure required environment variables are set
if [ -z "$dgId" ] || [ -z "$newDgId" ] || [ -z "$cookie" ] || [ -z "$updateType" ] || [ -z "$savedFilePath" ] || [ -z "$patchPayload" ] || [ -z "$sessionId" ]; then
  echo "One or more environment variables are missing."
  echo "Please set dgId, newDgId, cookie, updateType, savedFilePath, patchPayload, and sessionId."
  exit 1
fi

# Construct the payload using here document
payload=$(cat <<EOF
{
  "dgId": "$dgId",
  "newDgId": "$newDgId",
  "updateType": "$updateType",
  "savedFilePath": "$savedFilePath",
  "patchPayload": "$patchPayload",
  "cookie": "$cookie",
  "sessionId": "$sessionId"
}
EOF
)

# Set the forward URL
forward_url="http://dataset-processor:8001/init-dataset-process"

# Send the request
response=$(curl -s -w "\nHTTP_STATUS_CODE:%{http_code}" -X POST "$forward_url" \
  -H "Content-Type: application/json" \
  -H "Cookie: $cookie" \
  -d "$payload")

# Extract the HTTP status code from the response
http_status=$(echo "$response" | grep "HTTP_STATUS_CODE" | awk -F: '{print $2}' | tr -d '[:space:]')

# Extract the body from the response
http_body=$(echo "$response" | grep -v "HTTP_STATUS_CODE")

# Check if the request was successful
if [ "$http_status" -ge 200 ] && [ "$http_status" -lt 300 ]; then
  echo "Request successful."
  echo "Response: $http_body"
else
  echo "Request failed with status code $http_status."
  echo "Response: $http_body"
  exit