#!/bin/bash

# Set the working directory to the location of the script
cd "$(dirname "$0")"

# Source the constants from the ini file
source ../config/config.ini

script_name=$(basename $0)
pwd

echo $(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - $script_name started

# Fetch the encrypted refresh token
response=$(curl -X POST -H "Content-Type: application/json" -d '{"platform":"OUTLOOK"}' "$CLASSIFIER_RESQL/get-token")
encrypted_refresh_token=$(echo $response | grep -oP '"token":"\K[^"]+')

echo "encrypted_refresh_token: $encrypted_refresh_token"

if [ -z "$encrypted_refresh_token" ]; then
  echo "No encrypted refresh token found"
  exit 1
fi

# Decrypt the refresh token
responseVal=$(curl -X POST -H "Content-Type: application/json" -d '{"token":"'"$encrypted_refresh_token"'"}' "http://data-mapper:3000/hbs/classifier/return_decrypted_outlook_token")
decrypted_refresh_token=$(echo "$responseVal" | grep -oP '"content":"\K[^"]+' | sed 's/\\/\\\\/g')

echo "decrypted refresh token: $decrypted_refresh_token"

# Fetch the subscription ID from the resql endpoint without authorization
subscription_id_response=$(curl -X POST -H "Content-Type: application/json" -d '{"platform":"OUTLOOK"}' "$CLASSIFIER_RESQL/get-platform-subscription-id")
subscription_id=$(echo "$subscription_id_response" | grep -oP '"subscriptionId":"\K[^"]+')

echo "subscription_id: $subscription_id"

if [ -z "$subscription_id" ]; then
  echo "Failed to retrieve subscription ID"
  exit 1
fi

# Request a new access token using the decrypted refresh token
access_token_response=$(curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$OUTLOOK_CLIENT_ID&scope=$OUTLOOK_SCOPE&refresh_token=$decrypted_refresh_token&grant_type=refresh_token&client_secret=$OUTLOOK_SECRET_KEY" \
  https://login.microsoftonline.com/common/oauth2/v2.0/token)

new_access_token=$(echo $access_token_response | grep -oP '"access_token":"\K[^"]+')

echo "new_access_token: $new_access_token"

if [ -z "$new_access_token" ]; then
  echo "Failed to get a new access token"
  exit 1
fi

# Calculate expiration time by adding 3 days to the current time
expiration_time=$(date -u -d "+3 days" +"%Y-%m-%dT%H:%M:%SZ")
echo "Calculated expiration time: $expiration_time"

# Refresh the subscription in Outlook
refresh_subscription_response=$(curl -X PATCH \
  -H "Authorization: Bearer $new_access_token" \
  -H "Content-Type: application/json" \
  -d '{"expirationDateTime": "'"$expiration_time"'"}' \
  "https://graph.microsoft.com/v1.0/subscriptions/$subscription_id")

echo "refresh_subscription_response: $refresh_subscription_response"

echo $(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - $script_name finished
