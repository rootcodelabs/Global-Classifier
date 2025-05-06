#!/bin/bash

# Set the working directory to the location of the script
cd "$(dirname "$0")"

# Source the constants from the ini file
source ../config/config.ini

script_name=$(basename $0)
pwd

echo $(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - $script_name started

# Function to Base64 encode
base64_encode() {
  echo -n "$1" | base64
}

# Fetch the encrypted refresh token
response=$(curl -X POST -H "Content-Type: application/json" -d '{"platform":"OUTLOOK"}' "$CLASSIFIER_RESQL/get-token")
encrypted_refresh_token=$(echo $response | grep -oP '"token":"\K[^"]+')

echo "encrypted_refresh_token: $encrypted_refresh_token"

if [ -z "$encrypted_refresh_token" ]; then
  echo "No encrypted refresh token found"
  exit 1
fi

responseVal=$(curl -X POST -H "Content-Type: application/json" -d '{"token":"'"$encrypted_refresh_token"'"}' "http://data-mapper:3000/hbs/classifier/return_decrypted_outlook_token")
decrypted_refresh_token=$(echo "$responseVal" | grep -oP '"content":"\K[^"]+' | sed 's/\\/\\\\/g')


echo "decrypted refresh token: $decrypted_refresh_token"

# Request a new access token using the decrypted refresh token
access_token_response=$(curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=$OUTLOOK_CLIENT_ID&scope=$OUTLOOK_SCOPE&refresh_token=$decrypted_refresh_token&grant_type=refresh_token&client_secret=$OUTLOOK_SECRET_KEY" \
  https://login.microsoftonline.com/common/oauth2/v2.0/token)

new_refresh_token=$(echo $access_token_response | grep -oP '"refresh_token":"\K[^"]+')
echo "new_refresh_token: $new_refresh_token"

if [ -z "$new_refresh_token" ]; then
  echo "Failed to get a new refresh token"
  exit 1
fi

responseEncrypt=$(curl -X POST -H "Content-Type: application/json" -d '{"token":"'"$new_refresh_token"'"}' "http://data-mapper:3000/hbs/classifier/return_encrypted_outlook_token")
encrypted_new_refresh_token=$(echo "$responseEncrypt" | grep -oP '"cipher":"\K[^"]+')

# Function to save the new encrypted refresh token
save_refresh_token() {
  encrypted_new_refresh_token="$1"
  curl -s -X POST -H "Content-Type: application/json" -d '{"platform":"OUTLOOK", "token":"'"$encrypted_new_refresh_token"'"}' "$CLASSIFIER_RESQL/save-outlook-token"
}

# Call the function to save the encrypted new refresh token
save_refresh_token "$encrypted_new_refresh_token"
echo "Encrypted New refresh token: $encrypted_new_refresh_token"

echo $(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - $script_name finished
