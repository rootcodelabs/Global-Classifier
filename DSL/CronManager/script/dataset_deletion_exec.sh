#!/bin/bash
echo "Started Shell Script to delete"
# Ensure required environment variables are set
if [ -z "$dgId" ] || [ -z "$cookie" ]; then
  echo "One or more environment variables are missing."
  echo "Please set dgId, newDgId, cookie, updateType, savedFilePath, and patchPayload."
  exit 1
fi

# Construct the payload using here document
payload=$(cat <<EOF
{
  "dgId": "$dgId",
  "cookie": "$cookie"
}
EOF
)

# Set the forward URL
forward_url="http://file-handler:8000/datasetgroup/data/delete"

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
  exit 1
fi