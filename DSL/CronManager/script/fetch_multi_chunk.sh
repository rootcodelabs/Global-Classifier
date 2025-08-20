#!/bin/bash

echo "Started Shell Script for Multi-Chunk Download and Aggregation"

# Check if environment variables are set
if [ -z "$datasetId" ] || [ -z "$chunkIds" ]; then
  echo "Please set the datasetId and chunkIds environment variables."
  exit 1
fi

# Logging function
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >&2
}

log "Multi-chunk download request started"
log "Dataset ID: $datasetId"
log "Chunk IDs: $chunkIds"

# Clean the parameters
DATASET_ID=$(echo "$datasetId" | tr -d '"')
CHUNK_IDS=$(echo "$chunkIds" | tr -d '"')

log "Cleaned Dataset ID: $DATASET_ID"
log "Cleaned Chunk IDs: $CHUNK_IDS"

# Validate chunk IDs format
if [[ ! "$CHUNK_IDS" =~ ^[0-9]+([[:space:]]+[0-9]+)*$ ]]; then
    log "❌ Invalid chunk IDs format. Expected space-separated numbers."
    error_response="{\"success\": false, \"dataset_id\": \"$DATASET_ID\", \"chunk_ids\": \"$CHUNK_IDS\", \"error\": \"Invalid chunk IDs format\", \"message\": \"Expected space-separated numbers like '1 2 3'\"}"
    echo "$error_response"
    exit 1
fi

# Create temp_chunks directory if it doesn't exist
mkdir -p /app/temp_chunks
log "Created/verified temp_chunks directory"

# Install required Python packages if not present
log "🔍 Installing required Python packages..."
python3 -m pip install --quiet --no-cache-dir requests pydantic || {
    log "❌ Failed to install packages"
    exit 1
}
log "✅ Required packages installed"

# Direct Python script path for downloading multiple chunks (inside container)
DOWNLOAD_SCRIPT="/app/src/s3_dataset_processor/fetch_multi_chunk.py"

log "🔍 Calling Python script to download and aggregate chunks..."

# Create temporary file for response
temp_response="/tmp/multi_chunk_response.json"

# Call the Python script
python3 "$DOWNLOAD_SCRIPT" \
  --dataset-id "$DATASET_ID" \
  --chunk-ids "$CHUNK_IDS" \
  --output-json "$temp_response"

exit_code=$?
log "🔍 Python script exit code: $exit_code"

if [ "$exit_code" -eq 0 ] && [ -f "$temp_response" ]; then
    log "✅ Multi-chunk processing successful"
    
    response_body=$(cat "$temp_response")
    
    # Check if aggregation was successful
    success_check=$(echo "$response_body" | grep -o '"success"[[:space:]]*:[[:space:]]*true' | wc -l)
    
    if [ "$success_check" -gt 0 ]; then
        log "✅ Chunks aggregated successfully"
        
        # Extract summary information for logging
        if command -v jq >/dev/null 2>&1; then
            total_items=$(echo "$response_body" | jq -r '.download_summary.total_items_aggregated // 0' 2>/dev/null || echo "0")
            successful_chunks=$(echo "$response_body" | jq -r '.download_summary.successful_downloads // 0' 2>/dev/null || echo "0")
            failed_chunks=$(echo "$response_body" | jq -r '.download_summary.failed_downloads // 0' 2>/dev/null || echo "0")
            
            log "📊 Aggregation Summary:"
            log "  - Total items aggregated: $total_items"
            log "  - Successful chunk downloads: $successful_chunks"
            log "  - Failed chunk downloads: $failed_chunks"
        else
            log "📊 Multi-chunk aggregation completed (install jq for detailed summary)"
        fi
        
        # Output the JSON response to stdout (this goes to CronManager caller)
        cat "$temp_response"
        
        # Cleanup
        rm -f "$temp_response"
        
        log "✅ Multi-chunk aggregation completed successfully"
        exit 0
    else
        log "❌ Multi-chunk aggregation failed - check response for details"
        
        # Still output the response so caller can see the error
        cat "$temp_response"
        
        # Cleanup
        rm -f "$temp_response"
        exit 1
    fi
    
else
    log "❌ Python script execution failed with exit code: $exit_code"
    
    # Create error response
    error_response="{\"success\": false, \"dataset_id\": \"$DATASET_ID\", \"chunk_ids\": \"$CHUNK_IDS\", \"error\": \"Script execution failed\", \"message\": \"Python script failed with exit code $exit_code\"}"
    echo "$error_response"
    
    if [ -f "$temp_response" ]; then
        log "Error response: $(cat $temp_response)"
        rm -f "$temp_response"
    fi
    exit 1
fi