#!/bin/bash

echo "Started Shell Script for removing agencies that left the network from the dataset"

# Check if environment variables are set
if [ -z "$datasetId" ] || [ -z "$previousDatasetId" ] || [ -z "$agencyIds" ]; then
  echo "Please set the datasetId, previousDatasetId and agencyIds environment variables."
  exit 1
fi

# Logging function
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

GENERATION_STATUS_UPDATE_URL="http://resql:8082/global-classifier/update-data-generation-status"
REMOVE_AGENCIES_SCRIPT="/app/src/s3_dataset_processor/remove_agencies_from_dataset.py"

# Marks the new version failed, so it doesn't block generation until the stuck check
mark_version_failed() {
  curl -s -X POST "$GENERATION_STATUS_UPDATE_URL" \
    -H "Content-Type: application/json" \
    -d "{\"datasetId\": \"$datasetId\", \"generationStatus\": \"Generation_Failed\"}" > /dev/null
  log "Dataset version $datasetId set to Generation_Failed"
}

log "Installing required Python packages..."
python3 -m pip install --quiet --no-cache-dir requests pydantic pandas || {
    log "Failed to install packages"
    mark_version_failed
    exit 1
}

log "Creating dataset version $datasetId from version $previousDatasetId without agencies: $agencyIds"

python3 "$REMOVE_AGENCIES_SCRIPT" \
  --dataset-id "$datasetId" \
  --previous-dataset-id "$previousDatasetId" \
  --agency-ids "$agencyIds"
exit_code=$?

log "Python script exit code: $exit_code"

if [ "$exit_code" -ne 0 ]; then
  mark_version_failed
  exit 1
fi

log "Dataset version $datasetId created successfully"
exit 0
