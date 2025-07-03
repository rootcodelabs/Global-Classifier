#!/bin/bash

echo "Started Shell Script for Chunk Download"

# Check if environment variables are set
if [ -z "$datasetId" ] || [ -z "$pageNum" ]; then
  echo "Please set the datasetId and pageNum environment variables."
  exit 1
fi

# Logging function
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

log "Chunk download request started"
log "Dataset ID: $datasetId"
log "Page Number: $pageNum"

# Clean the parameters
DATASET_ID=$(echo "$datasetId" | tr -d '"')
PAGE_NUM=$(echo "$pageNum" | tr -d '"')

log "Cleaned Dataset ID: $DATASET_ID"
log "Cleaned Page Number: $PAGE_NUM"

# Install required Python packages if not present
log "🔍 Installing required Python packages..."
python3 -m pip install --quiet --no-cache-dir requests pydantic || {
    log "❌ Failed to install packages"
    exit 1
}
log "✅ Required packages installed"

# Direct Python script path for downloading chunk (inside container)
DOWNLOAD_SCRIPT="/app/src/s3_dataset_processor/fetch_chunk_without_filter.py"

log "🔍 Calling Python script to download chunk..."

# Create temporary file for response
temp_response="/tmp/chunk_response.json"

# Call the Python script
python3 "$DOWNLOAD_SCRIPT" \
  --dataset-id "$DATASET_ID" \
  --page-num "$PAGE_NUM" \
  --output-json "$temp_response"

exit_code=$?
log "🔍 Python script exit code: $exit_code"

if [ "$exit_code" -eq 0 ] && [ -f "$temp_response" ]; then
    log "✅ Chunk download successful"
    
    response_body=$(cat "$temp_response")
    log "🔍 Response: $response_body"
    
    # Check if download was successful
    success_check=$(echo "$response_body" | grep -o '"success"[[:space:]]*:[[:space:]]*true' | wc -l)
    
    if [ "$success_check" -gt 0 ]; then
        log "✅ Chunk downloaded successfully"
        
        # Output the JSON response to stdout (this goes to CronManager caller)
        cat "$temp_response"
        
        # Cleanup
        rm -f "$temp_response"
        
        log "✅ Chunk download completed successfully"
        exit 0
    else
        log "❌ Chunk download failed - check response for details"
        
        # Still output the response so caller can see the error
        cat "$temp_response"
        
        # Cleanup
        rm -f "$temp_response"
        exit 1
    fi
    
else
    log "❌ Python script execution failed with exit code: $exit_code"
    
    # Create error response
    error_response="{\"success\": false, \"dataset_id\": \"$DATASET_ID\", \"page_num\": $PAGE_NUM, \"error\": \"Script execution failed\", \"message\": \"Python script failed with exit code $exit_code\"}"
    echo "$error_response"
    
    if [ -f "$temp_response" ]; then
        log "Error response: $(cat $temp_response)"
        rm -f "$temp_response"
    fi
    exit 1
fi