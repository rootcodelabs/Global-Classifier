#!/bin/bash

echo "Started Shell Script for Dataset Generation Callback Processing"

# Check if environment variables are set
if [ -z "$filePath" ] || [ -z "$results" ] || [ -z "$taskId" ]; then
  echo "Please set the filePath, results, and taskId environment variables."
  exit 1
fi

# Logging function
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}
PROGRESS_UPDATE_URL="http://ruuter-public:8086/global-classifier/datasets/progress/update"
# Debug: Check Python environment
log "[INFO] Python version: $(python3 --version)"
log "[INFO] Python path: $(which python3)"

# Install required packages
log "[INFO] Installing required Python packages..."
python3 -m pip install --quiet --no-cache-dir requests pydantic pandas || {
    log "[ERROR] Failed to install packages"
    exit 1
}
log "[INFO] Required packages installed"

log "[INFO] Dataset generation callback processing started"
log "[INFO] File path: $filePath"
log "[INFO] Encoded results length: ${#results} characters"

dataset_id=$(echo "$filePath" | grep -o '/[^/]*\.csv$' | sed 's|/\([^/]*\)\.csv$|\1|' || echo "unknown")
log "[INFO] Extracted dataset ID: $dataset_id"

# Direct Python script path for processing generation callback (inside container)
CALLBACK_SCRIPT="/app/src/s3_dataset_processor/dataset_generation_callback_processor.py"

log "[INFO] Calling direct Python script to process generation callback..."

# Create temporary file for response
temp_response="/tmp/callback_response.json"

# Update progress session with initial status
progress_update_payload=$(cat <<EOF
{
  "sessionId": "$taskId",
  "generationStatus": "New Dataset Uploading to s3",
  "generationMessage": "Preparing to Upload New Dataset to S3",
  "progressPercentage": 85,
  "processComplete": false
}
EOF
)

progress_update_response=$(curl -s -X POST "$PROGRESS_UPDATE_URL" \
  -H "Content-Type: application/json" \
  -d "$progress_update_payload")
echo "Progress session update response: $progress_update_response"

python3 "$CALLBACK_SCRIPT" \
  --file-path "$filePath" \
  --encoded-results "$results" \
  --output-json "$temp_response" \
  --session-id "$taskId" \
  > /tmp/callback_stdout.log 2> /tmp/callback_stderr.log
exit_code=$?

log "[INFO] Python STDOUT:"
cat /tmp/callback_stdout.log

log "[INFO] Python STDERR:"
cat /tmp/callback_stderr.log

log "[INFO] Python script exit code: $exit_code"

if [ -f "$temp_response" ]; then
    log "[INFO] Contents of output JSON:"
    cat "$temp_response"
else
    log "[WARNING] No output JSON file was generated."
fi

# Check if script execution was successful
if [ "$exit_code" -eq 0 ] && [ -f "$temp_response" ]; then
    log "[INFO] Python script execution successful"
    
    response_body=$(cat "$temp_response")
    log "[INFO] Response: $response_body"

    # Parse the response to get status information
    if command -v jq >/dev/null 2>&1; then
        status=$(echo "$response_body" | jq -r '.status // "unknown"')
        message=$(echo "$response_body" | jq -r '.message // "unknown"')

        log "[INFO] Callback Processing Status:"
        log "  - Status: $status"
        log "  - Message: $message"
        log "  - Dataset ID: $dataset_id"
        
    else
        # Fallback parsing without jq
        log "[WARNING] jq not available, using grep/sed for parsing"

        status=$(echo "$response_body" | grep -o '"status":"[^"]*"' | sed 's/.*"status":"\([^"]*\)".*/\1/' || echo "unknown")
        message=$(echo "$response_body" | grep -o '"message":"[^"]*"' | sed 's/.*"message":"\([^"]*\)".*/\1/' || echo "unknown")

        log "[INFO] Callback Processing Status:"
        log "  - Status: $status"
        log "  - Message: $message"
        log "  - Dataset ID: $dataset_id"
    fi
    
    # Check if callback processing was completed
    if [ "$status" = "completed" ]; then
        log "[INFO] Dataset generation callback processed successfully"
        log "[INFO] Callback payload has been sent to status update endpoint"
        log "[INFO]   - agencies: [{agencyId: X, syncStatus: Synced_with_CKB/Sync_with_CKB_Failed}, ...]"
        log "[INFO]   - datasetId: $dataset_id"
        log "[INFO]   - generationStatus: Generation_Success/Generation_Failed"

    else
        log "[WARNING] Unexpected status received: $status"
        log "[WARNING] Message: $message"
    fi
    
    # Cleanup temp file
    rm -f "$temp_response"
    
else
    log "[ERROR] Python script execution failed with exit code: $exit_code"
    if [ -f "$temp_response" ]; then
        log "[ERROR] Error response: $(cat $temp_response)"
        rm -f "$temp_response"
    fi
    exit 1
fi

log "[INFO] Dataset generation callback processing completed successfully"
log "[INFO] Summary: Dataset ID: $dataset_id, Request Status: $status"

exit 0