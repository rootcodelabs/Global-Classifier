#!/bin/bash
echo "Started Shell Script to delete models"
# Ensure required environment variables are set
if [ -z "$modelId" ] || [ -z "$cookie" ]; then
  echo "One or more environment variables are missing."
  echo "Please set modelId and cookie."
  exit 1
fi

# Set the API URL to get metadata based on the modelId
api_url="http://ruuter-private:8088/classifier/datamodel/metadata?modelId=$modelId"

echo $api_url
# Send the request to the API and capture the output
api_response=$(curl -s -H "Cookie: $cookie" -X GET "$api_url")

echo $api_response

# Check if the API response is valid
if [ -z "$api_response" ]; then
  echo "API request failed to get the model metadata."
  exit 1
fi

deployment_env=$(echo $api_response | jq -r '.response.data[0].deploymentEnv')

echo "API RESPONSE"
echo $api_response
echo "DEPLOYMENT ENV"
echo $deployment_env

# Construct the payload using here document
payload=$(cat <<EOF
{
  "modelId": "$modelId",
  "cookie": "$cookie",
  "deploymentEnv": "$deployment_env"
}
EOF
)

echo $payload

# Set the forward URL
forward_url="http://file-handler:8000/datamodel/model/delete"

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