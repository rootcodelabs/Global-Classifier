#!/bin/bash

# DEFINING ENDPOINTS

GET_MODEL_METADATA_ENDPOINT=http://ruuter-private:8088/classifier/datamodel/metadata
CREATE_TRAINING_PROGRESS_SESSION_ENDPOINT=http://ruuter-private:8088/classifier/datamodel/progress/create
UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT=http://ruuter-private:8088/classifier/datamodel/progress/update
UPDATE_MODEL_METADATA_TRAINING_STATUS_ENDPOINT=http://ruuter-private:8088/classifier/datamodel/update/training/status

# Send the request to the API and capture the output
MODEL_METADATA_ENDPOINT="$GET_MODEL_METADATA_ENDPOINT?modelId=$newModelId"

echo $GET_MODEL_METADATA_ENDPOINT

echo "cookie"
echo $cookie

api_response=$(curl -s -H "Cookie: customJwtCookie=$cookie" -X GET "$MODEL_METADATA_ENDPOINT")

echo $api_response

# Check if the API response is valid
if [ -z "$api_response" ]; then
  echo "API request failed to get the model metadata."
  exit 1
fi

deploymentEnv=$(echo $api_response | grep -o '"deploymentEnv":[^,]*' | sed 's/.*"deploymentEnv"://' | tr -d '"}')
modelDetails=$api_response
export deploymentEnv
export modelDetails

# Extract model details from the JSON response
modelName=$(echo "$modelDetails" | grep -o '"modelName":[^,]*' | sed 's/.*"modelName"://' | tr -d '"}')
majorVersion=$(echo "$modelDetails" | grep -o '"majorVersion":[^,]*' | sed 's/.*"majorVersion"://' | tr -d '"}')
minorVersion=$(echo "$modelDetails" | grep -o '"minorVersion":[^,]*' | sed 's/.*"minorVersion"://' | tr -d '"}')
latest=$(echo "$modelDetails" | grep -o '"latest":[^,]*' | sed 's/.*"latest"://' | tr -d '"}')

# Construct payload to update training status using cat
payload=$(cat <<EOF
{
    "modelId": $newModelId,
    "trainingStatus": "training in-progress",
    "modelS3Location": "",
    "trainingResults": {},
    "inferenceRoutes": {}
}
EOF
)

echo "PAYLOAD FOR UPDATING TRAINING STATUS"
echo $newModelId
echo $payload

echo "SENDING REQUEST TO UPDATE_MODEL_METADATA_TRAINING_STATUS_ENDPOINT"
response=$(curl -s -X POST "$UPDATE_MODEL_METADATA_TRAINING_STATUS_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Cookie: customJwtCookie=$cookie" \
    -d "$payload")

echo $response

operation_status=$(echo "$response" | grep -o '"operationSuccessful":[^,]*' | sed 's/.*"operationSuccessful"://' | tr -d '"}')

echo "Operation Status: $operation_status"

if [ "$operation_status" = true ]; then
    echo "Model Metadata update successful"
else
    echo "Failed to update model metadata. Exiting..."
    exit 1
fi

# Construct the payload to create progress training session using cat
payload=$(cat <<EOF
{
    "modelId": $newModelId,
    "modelName": "$modelName",
    "majorVersion": $majorVersion,
    "minorVersion": $minorVersion,
    "latest": $latest
}
EOF
)

echo "Payload for creating progress session: $payload"

# Send the POST request to create the training progress session
response=$(curl -s -X POST "$CREATE_TRAINING_PROGRESS_SESSION_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Cookie: customJwtCookie=$cookie" \
    -d "$payload")

echo "Response from create training progress session"
echo $response

operation_status=$(echo "$response" | grep -o '"operationSuccessful":[^,]*' | sed 's/.*"operationSuccessful"://' | tr -d '"}')

if [ "$operation_status" = true ]; then
    progressSessionId=$(echo "$response" | grep -o '"sessionId":[^,]*' | sed 's/.*"sessionId"://' | tr -d '"}')
    echo "Session ID: $progressSessionId"
else
    echo "Failed to create training progress session. Exiting..."
    exit 1
fi

#### INITIATING REQUEST TO UPDATE TRAINING PROGRESS SESSION

# Constructing progress update payload using cat
payload=$(cat <<EOF
{
    "sessionId": $progressSessionId,
    "trainingStatus": "Training In-Progress",
    "trainingMessage": "Initiating Training Session - In Training Queue",
    "progressPercentage": 5,
    "processComplete": false
}
EOF
)

echo "UPDATE PROGRESS SESSION PAYLOAD"
echo $payload

# Send POST request to update progress session and set an initial percentage of 5
response=$(curl -s -X POST "$UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT" \
    -H "Content-Type: application/json" \
    -H "Cookie: customJwtCookie=$cookie" \
    -d "$payload")

echo "PROGRESS UPDATE RESPONSE"
echo $response

operation_status=$(echo "$response" | grep -o '"operationSuccessful":[^,]*' | sed 's/.*"operationSuccessful"://' | tr -d '"}')

if [ "$operation_status" = true ]; then
    progressSessionId=$(echo "$response" | grep -o '"sessionId":[^,]*' | sed 's/.*"sessionId"://' | tr -d '"}')
    echo "Session ID: $progressSessionId"
else
    echo "Failed to update training progress session. Exiting..."

    # Constructing progress update payload to show the error using cat
    payload=$(cat <<EOF
{
    "sessionId": $progressSessionId,
    "trainingStatus": "Training Failed",
    "trainingMessage": "Training Failed During Progress session update",
    "progressPercentage": 100,
    "processComplete": true
}
EOF
)

    echo "UPDATE PROGRESS SESSION WITH ERROR PAYLOAD"
    echo $payload

    # Send POST request to update progress session and indicate error
    response=$(curl -s -X POST "$UPDATE_TRAINING_PROGRESS_SESSION_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "Cookie: customJwtCookie=$cookie" \
        -d "$payload")

    echo "ERROR PROGRESS UPDATE RESPONSE"
    echo $response
    exit 1
fi

export progressSessionId

# Preparing the final payload for forwarding using cat
editedModelDetails=$(echo "$modelDetails" | sed 's/"/\\"/g')

payload=$(cat <<EOF
{
  "cookie": "$cookie",
  "old_model_id": "$modelId",
  "new_model_id": "$newModelId",
  "update_type": "$updateType",
  "previous_deployment_env": "$previousDeploymentEnv",
  "progress_session_id": $progressSessionId,
  "deployment_env": "$deploymentEnv",
  "model_details": "$editedModelDetails"
}
EOF
)

echo "payload - $payload"
forward_url="http://trainer-queue:8901/add_session"

# Send HTTP POST request to model_trainer
response=$(curl -s -w "\nHTTP_STATUS_CODE:%{http_code}" -X POST "$forward_url" \
  -H "Content-Type: application/json" \
  -H "Cookie: $cookie" \
  -d "$payload")

# Output the response
echo "Response from model_trainer:"
echo "$response"
