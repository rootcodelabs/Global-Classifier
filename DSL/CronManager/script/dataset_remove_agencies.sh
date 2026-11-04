#!/bin/bash
source /app/scripts/load_constants.sh

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

GENERATION_STATUS_UPDATE_URL="${GLOBAL_CLASSIFIER_RESQL}/update-data-generation-status"
REMOVE_AGENCIES_SCRIPT="/app/src/s3_dataset_processor/remove_agencies_from_dataset.py"

# Marks the new version failed, so it doesn't block generation until the stuck check
mark_version_failed() {
  curl -s -X POST "$GENERATION_STATUS_UPDATE_URL" \
    -H "Content-Type: application/json" \
    -d "{\"datasetId\": \"$datasetId\", \"generationStatus\": \"Generation_Failed\"}" > /dev/null
  log "Dataset version $datasetId set to Generation_Failed"
}

# CronManager runs jobs with an environment limited to the job's declared
# allowedEnvs (see CronService.executeJob) - PATH is never included, so
# bare `python3`/`pip` calls would resolve via bash's bare-bones fallback
# PATH and miss the venv entirely. Activating by absolute path fixes PATH
# for the rest of this script regardless of what CronManager passed in.
UV_BIN="/usr/local/bin/uv"
if [ ! -f "$UV_BIN" ]; then
    UV_BIN="/root/.local/bin/uv"
fi
if [ ! -f "$UV_BIN" ]; then
    echo "[UV] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || {
        log "Failed to install uv"
        mark_version_failed
        exit 1
    }
    UV_BIN="/root/.local/bin/uv"
fi

VENV_PATH="/app/python_virtual_env"
source "$VENV_PATH/bin/activate" || {
    log "Failed to activate virtual environment"
    mark_version_failed
    exit 1
}

log "Installing required Python packages..."
"$UV_BIN" pip install --python "$VENV_PATH/bin/python3" --quiet requests pydantic pandas || {
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
