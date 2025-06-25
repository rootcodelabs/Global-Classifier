#!/bin/bash

echo "Started Shell Script for Dataset Generation Callback Processing"

# Check if environment variables are set
if [ -z "$filePath" ] || [ -z "$results" ]; then
  echo "Please set the filePath and results environment variables."
  exit 1
fi

# Logging function
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Dataset generation callback processing started"
log "File path: $filePath"
log "Encoded results length: ${#results} characters"

# Extract dataset ID from file path for logging
dataset_id=$(echo "$filePath" | grep -o '/[^/]*\.json$' | sed 's|/\([^/]*\)\.json$|\1|' || echo "unknown")
log "Extracted dataset ID: $dataset_id"

# API endpoint for processing generation callback
API_URL="http://s3-dataset-processor:8001/process-generation-callback"

log "🔍 Calling S3 Dataset Processor API to process generation callback..."

# Call the API to process generation callback (background processing)
response=$(curl -s -o /tmp/callback_response_body.txt -w "%{http_code}" -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -d "{\"file_path\":\"$filePath\", \"results\":\"$results\"}")

http_code="$response"
response_body=$(cat /tmp/callback_response_body.txt)

log "🔍 HTTP Status Code: $http_code"
log "🔍 Response Body: $response_body"

# Check if API call was successful (should get 200 immediately)
if [ "$http_code" = "200" ] && [ -n "$response_body" ]; then
    log "✅ Callback processing request accepted successfully"
    
    # Parse the response to get status information
    if command -v jq >/dev/null 2>&1; then
        # Use jq if available
        status=$(echo "$response_body" | jq -r '.status // "unknown"')
        message=$(echo "$response_body" | jq -r '.message // "unknown"')
        
        log "📊 Callback Processing Status:"
        log "  - Status: $status"
        log "  - Message: $message"
        log "  - Dataset ID: $dataset_id"
        
    else
        # Fallback parsing without jq
        log "⚠️ jq not available, using grep/sed for parsing"
        
        status=$(echo "$response_body" | grep -o '"status":"[^"]*"' | sed 's/.*"status":"\([^"]*\)".*/\1/' || echo "unknown")
        message=$(echo "$response_body" | grep -o '"message":"[^"]*"' | sed 's/.*"message":"\([^"]*\)".*/\1/' || echo "unknown")
        
        log "📊 Callback Processing Status:"
        log "  - Status: $status"
        log "  - Message: $message"
        log "  - Dataset ID: $dataset_id"
    fi
    
    # Check if callback processing was accepted
    if [ "$status" = "accepted" ]; then
        log "✅ Dataset generation callback submitted for background processing"
        log "🔄 Background task will create the following payload structure:"
        log "   - agencies: [{agencyId: X, syncStatus: Synced_with_CKB/Sync_with_CKB_Failed}, ...]"
        log "   - datasetId: $dataset_id"
        log "   - generationStatus: Generation_Success/Generation_Failed"
        
        log "📋 Note: Actual callback processing is happening in the background"
        log "📋 Check the S3 processor service logs for detailed processing results"
        
    else
        log "⚠️ Unexpected status received: $status"
        log "⚠️ Message: $message"
    fi
    
else
    log "❌ Callback processing request failed"
    log "HTTP Status: $http_code"
    log "Response: $response_body"
    
    # Clean up temp files
    rm -f /tmp/callback_response_body.txt
    exit 1
fi

# Clean up temp files
rm -f /tmp/callback_response_body.txt

log "✅ Dataset generation callback processing completed successfully"
log "📋 Summary: Dataset ID: $dataset_id, Request Status: $status"
log "📋 Background processing will generate the final callback payload"

exit 0