#!/bin/bash

echo "Started Shell Script for S3 DataSet Processing"

# Check if environment variable is set
if [ -z "$signedUrls" ] || [ -z "$datasetId" ]; then
  echo "Please set the signedUrls and datasetId environment variables."
  exit 1
fi

# Logging function
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

data_generation_request="$signedUrls"

# Install required Python packages if not present
echo "🔍 Installing required Python packages..."
python3 -m pip install --quiet --no-cache-dir requests pydantic || {
    echo "❌ Failed to install packages"
    exit 1
}
echo "✅ Required packages installed"

log "S3 data processing request received"
log "Encoded data length: ${#data_generation_request} characters"

# Direct Python script path for downloading datasets (inside container)
DOWNLOAD_SCRIPT="/app/src/s3_dataset_processor/download_source_dataset.py"
CURRENT_DATASET_ID="$datasetId"
CURRENT_DATASET_ID=$(echo "$CURRENT_DATASET_ID" | tr -d '"')

log "🔍 Calling direct Python script to download files..."

# Create temporary file for response
temp_response="/tmp/download_response.json"

# Call the direct Python script instead of FastAPI
python3 "$DOWNLOAD_SCRIPT" \
  --encoded-data "$data_generation_request" \
  --extract-files \
  --output-json "$temp_response"

exit_code=$?
log "🔍 Python script exit code: $exit_code"

if [ -f "$temp_response" ]; then
    log "📄 Contents of output JSON:"
    cat "$temp_response"
else
    log "⚠️ No output JSON file was generated."
fi

# Check if script execution was successful
if [ "$exit_code" -eq 0 ] && [ -f "$temp_response" ]; then
    log "✅ Python script execution successful"
    
    response_body=$(cat "$temp_response")
    log "🔍 Response: $response_body"
    
    # Improved JSON parsing - remove whitespace and check for success
    # Use multiple methods to ensure we catch the success field
    success_check1=$(echo "$response_body" | grep -o '"success"[[:space:]]*:[[:space:]]*true' | wc -l)
    success_check2=$(echo "$response_body" | grep -o '"success":true' | wc -l)
    success_check3=$(echo "$response_body" | tr -d ' \n\r\t' | grep -o '"success":true' | wc -l)
    
    log "🔍 Success check results: method1=$success_check1, method2=$success_check2, method3=$success_check3"
    
    if [ "$success_check1" -gt 0 ] || [ "$success_check2" -gt 0 ] || [ "$success_check3" -gt 0 ]; then
        success_status="true"
    else
        success_status="false"
    fi
    
    log "🔍 Success status: $success_status"
    
    if [ "$success_status" = "true" ]; then
        log "✅ S3 download and extraction successful"
        
        # Get successful downloads count using improved parsing
        successful_downloads=$(echo "$response_body" | grep -o '"successful_downloads"[[:space:]]*:[[:space:]]*[0-9]*' | grep -o '[0-9]*' | tail -1)
        [ -z "$successful_downloads" ] && successful_downloads=0
        log "Successfully downloaded and extracted $successful_downloads files"
        
        # Prepare dataset generation payload as a list
        log "🔄 Preparing dataset generation payload..."
        
        # Create temporary file for building the JSON payload
        temp_payload="/tmp/dataset_payload.json"
        echo '{"datasets": [' > "$temp_payload"
        
        first_entry=true
        
        # Extract folder information and build the payload list
        # Use improved parsing to handle the extracted_folders array
        if command -v jq >/dev/null 2>&1; then
            # Use jq if available - more reliable
            echo "$response_body" | jq -r '.extracted_folders[]? | "\(.agency_id):\(.agency_name):\(.folder_path)"' 2>/dev/null | while IFS=':' read -r agency_id agency_name folder_path; do
                if [ -n "$agency_id" ] && [ -n "$agency_name" ] && [ -n "$folder_path" ]; then
                    if [ "$first_entry" = false ]; then
                        echo ',' >> "$temp_payload"
                    fi
                    echo "    {" >> "$temp_payload"
                    echo "      \"agency_id\": \"$agency_id\"," >> "$temp_payload"
                    echo "      \"agency_name\": \"$agency_name\"," >> "$temp_payload"
                    echo "      \"data_path\": \"$folder_path\"," >> "$temp_payload"
                    echo "      \"output_filename\": \"$CURRENT_DATASET_ID\"" >> "$temp_payload"
                    echo "    }" >> "$temp_payload"
                    first_entry=false
                fi
            done
        else
            # Fallback parsing without jq - improved regex
            log "⚠️ jq not available, using grep/sed for parsing"
            
            # Clean the response body and extract agency_id and folder_path pairs
            cleaned_response=$(echo "$response_body" | tr -d '\n\r\t' | tr -s ' ')
            echo "$cleaned_response" | grep -o '"agency_id"[[:space:]]*:[[:space:]]*"[^"]*"[[:space:]]*,[[:space:]]*"agency_name"[[:space:]]*:[[:space:]]*"[^"]*"[[:space:]]*,[[:space:]]*"folder_path"[[:space:]]*:[[:space:]]*"[^"]*"' | while read -r folder_info; do
                agency_id=$(echo "$folder_info" | sed 's/.*"agency_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
                agency_name=$(echo "$folder_info" | sed 's/.*"agency_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
                folder_path=$(echo "$folder_info" | sed 's/.*"folder_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/')
                
                if [ -n "$agency_id" ] && [ -n "$agency_name" ] && [ -n "$folder_path" ]; then
                    if [ "$first_entry" = false ]; then
                        echo ',' >> "$temp_payload"
                    fi
                    echo "    {" >> "$temp_payload"
                    echo "      \"agency_id\": \"$agency_id\"," >> "$temp_payload"
                    echo "      \"agency_name\": \"$agency_name\"," >> "$temp_payload"
                    echo "      \"data_path\": \"$folder_path\"," >> "$temp_payload"
                    echo "      \"output_filename\": \"$CURRENT_DATASET_ID\"" >> "$temp_payload"
                    echo "    }" >> "$temp_payload"
                    first_entry=false
                fi
            done
        fi
        
        # Close the JSON array and object
        echo '' >> "$temp_payload"
        echo ']}' >> "$temp_payload"
        
        # Read the complete payload
        payload_content=$(cat "$temp_payload")
        log "🔍 Dataset generation payload: $payload_content"
        
        # Call the dataset generation service with the list payload
        log "🔄 Calling dataset generation service for bulk processing..."
        
        dataset_response=$(curl -s -o /tmp/dataset_response_body.txt -w "%{http_code}" -X POST "http://dataset-gen-service:8000/generate-bulk" \
            -H "Content-Type: application/json" \
            -d "$payload_content")
        
        dataset_http_code="$dataset_response"
        dataset_response_body=$(cat /tmp/dataset_response_body.txt)

        log "🔍 Dataset Generation HTTP Status Code: $dataset_http_code"
        log "🔍 Dataset Generation Response: $dataset_response_body"
        
        if [ "$dataset_http_code" = "200" ]; then
            log "✅ Dataset generation request submitted successfully"
            log "✅ Background task initiated for dataset processing"
            log "Response: $dataset_response_body"
        else
            log "❌ Failed to submit dataset generation request"
            log "HTTP Status: $dataset_http_code"
            log "Error response: $dataset_response_body"
            # Cleanup temp files
            rm -f /tmp/dataset_payload.json /tmp/dataset_response_body.txt /tmp/download_response.json
            exit 1
        fi
        
        # Cleanup temp files
        rm -f /tmp/dataset_payload.json /tmp/dataset_response_body.txt
        
        log "✅ S3 Dataset Processing completed successfully"
        log "✅ Dataset generation is running in background"
        
    else
        log "❌ S3 download failed - success status: $success_status"
        log "Response: $response_body"
        rm -f /tmp/download_response.json
        exit 1
    fi
    
else
    log "❌ Python script execution failed with exit code: $exit_code"
    if [ -f "$temp_response" ]; then
        log "Error response: $(cat $temp_response)"
        rm -f /tmp/download_response.json
    fi
    exit 1
fi

# Cleanup temp file
rm -f /tmp/download_response.json

log "🎉 S3 Dataset Processing script completed successfully"
log "📋 Note: Dataset generation is running as a background task"

exit 0