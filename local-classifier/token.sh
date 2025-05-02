#!/bin/bash

# Define the path where the SQL file will be generated
SQL_FILE="DSL/Liquibase/data/update_refresh_token.sql"

# Read the OUTLOOK_REFRESH_KEY value from the INI file
OUTLOOK_REFRESH_KEY=$(awk -F '=' '/OUTLOOK_REFRESH_KEY/ {print $2}' constants.ini | xargs)

# Function to Base64 encode
base64_encode() {
  echo -n "$1" | base64
}

# Encrypt the refresh token
encrypted_refresh_token=$(base64_encode "$OUTLOOK_REFRESH_KEY")

# Generate a SQL script with the encrypted value
cat << EOF > "$SQL_FILE"
-- Update the refresh token in the database
UPDATE integration_status
SET token = '$encrypted_refresh_token'
WHERE platform='OUTLOOK';
EOF

echo "SQL file created at $SQL_FILE with encrypted token."
