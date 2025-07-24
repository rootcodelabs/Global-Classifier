#!/bin/bash

# Global Classifier Model Deployment Script
# This script handles model deployment using S3-Ferry service

# Check if unzip package is available, install if not
if ! command -v unzip &> /dev/null; then
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - unzip package not found, installing..."
    apt update && apt install -y unzip
    if [[ $? -ne 0 ]]; then
        echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - ERROR: Failed to install unzip package"
        exit 1
    fi
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - unzip package installed successfully"
else
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - unzip package is available"
fi

# Set default values if not provided by constants.ini
S3_FERRY_URL=${GLOBAL_CLASSIFIER_S3_FERRY:-"http://gc-s3-ferry:3000"}
RUUTER_PRIVATE_URL=${GLOBAL_CLASSIFIER_RUUTER_PRIVATE:-"http://ruuter-private:8088/global-classifier"}
TRITON_TEST_URL=${GLOBAL_CLASSIFIER_TESTING_ENV_MODEL_SERVER:-"http://triton-test-server:8000"}
TRITON_PROD_URL=${GLOBAL_CLASSIFIER_PRODUCTION_ENV_MODEL_SERVER:-"http://triton-production-server:8000"}


# Check if required environment variables are set
if [[ -z "$modelId" ]]; then
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - ERROR: modelId environment variable is required"
    exit 1
fi


echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - Starting deployment for model ID: $modelId to environment: $deploymentEnv"

# Create temp directory for downloading models in CronManager shared volume
EXTRACT_DIR="/app/data/temp_extracted_models/model_id_${modelId}"

mkdir -p "$EXTRACT_DIR"

# S3 Ferry local file path same as above with /app removed since s3 Ferry already adds this from config
S3_FERRY_LOCAL_DOWNLOAD_PATH="data/temp_extracted_models/model_id_${modelId}"


echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - Created working directory: $EXTRACT_DIR"
echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - Path sent to S3 Ferry: $S3_FERRY_LOCAL_DOWNLOAD_PATH"


# Function to call S3-Ferry API
call_s3_ferry() {
    local source_path="$1"
    local source_type="$2"
    local dest_path="$3"
    local dest_type="$4"
    
    local payload=$(cat <<EOF
{
    "sourceFilePath": "$source_path",
    "sourceStorageType": "$source_type",
    "destinationFilePath": "$dest_path",
    "destinationStorageType": "$dest_type"
}
EOF
)
    
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - S3-Ferry transfer: $source_path ($source_type) -> $dest_path ($dest_type)"
    
    local response
    local http_code
    
    response=$(curl -s -w "%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "$payload" \
        "$S3_FERRY_URL/v1/files/copy")
    
    http_code="${response: -3}"
    response_body="${response%???}"
    
    if [[ "$http_code" =~ ^(200|201)$ ]]; then
        echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - S3-Ferry transfer successful (HTTP $http_code)"
        return 0
    else
        echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - ERROR: S3-Ferry transfer failed (HTTP $http_code): $response_body"
        return 1
    fi
}


# Step 1: Download the model zip file from undeployed bucket
echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - Step 1: Downloading model from undeployed bucket..."

MODEL_ZIP_NAME="${modelId}.zip"
LOCAL_ZIP_PATH="${S3_FERRY_LOCAL_DOWNLOAD_PATH}/${MODEL_ZIP_NAME}"
S3_SOURCE_PATH="models/undeployed/${MODEL_ZIP_NAME}"

echo "MODEL S3 LOCATION - $S3_SOURCE_PATH"
echo "MODEL LOCAL PATH - $LOCAL_ZIP_PATH"


if ! call_s3_ferry "$S3_SOURCE_PATH" "S3" "$LOCAL_ZIP_PATH" "FS"; then
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - ERROR: Failed to download model from undeployed bucket"
    exit 1
fi

# Step 2: Verify the zip file was downloaded
if [[ ! -f "$LOCAL_ZIP_PATH" ]]; then
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - ERROR: Model zip file not found at $LOCAL_ZIP_PATH"
    exit 1
fi

echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - Model zip file downloaded successfully: $(ls -lh $LOCAL_ZIP_PATH)"

# Step 3: Unzip and extract model files
echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - Step 2: Extracting model files..."

if ! unzip -qo "$LOCAL_ZIP_PATH" -d "$EXTRACT_DIR"; then
    echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - ERROR: Failed to extract model zip file"
    exit 1
fi

echo "$(date -u +"%Y-%m-%d %H:%M:%S.%3NZ") - Model files extracted successfully"

#TODO - 
