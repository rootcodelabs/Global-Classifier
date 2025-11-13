#!/bin/bash
# File: DSL/CronManager/script/train_script_starter.sh

# API Endpoints
CHECK_JOB_STATUS_IN_PROGRESS_SQL="http://resql:8082/global-classifier/get-training-job-status-in-progress"
GET_FIRST_COME_TRAINING_JOB_SQL="http://resql:8082/global-classifier/get-queued-training-job"
GET_DATA_MODEL_BY_MODEL_ID_SQL="http://resql:8082/global-classifier/get-data-model-info-by-given-model-id"
UPDATE_JOB_STATUS="http://resql:8082/global-classifier/update-training-job-status"

echo "[START] Training script starter"

# Check if training is in progress
echo "[CHECK] Checking if training is in progress..."
response_job_status_in_progres=$(curl -s -X POST "$CHECK_JOB_STATUS_IN_PROGRESS_SQL")
echo "[DEBUG] Training status response: '$response_job_status_in_progres'"

if [ $? -ne 0 ] || [ -z "$response_job_status_in_progres" ]; then
    echo "[ERROR] Failed to check training status"
    exit 1
fi

if echo "$response_job_status_in_progres" | grep -q '"hasTrainingInProgress":true'; then
    echo "[INFO] Training is already in progress. Exiting..."
    exit 0
fi

echo "[AVAILABLE] No training in progress."
# Get first queued training job
echo "[QUEUE] Getting first queued training job..."
response_first_come_training_job=$(curl -s -X POST "$GET_FIRST_COME_TRAINING_JOB_SQL")
echo "[DEBUG] First queued job response: '$response_first_come_training_job'"
# Handle empty response (no queued jobs) - this is normal, not an error
if [ -z "$response_first_come_training_job" ]; then
    echo "[INFO] No queued training jobs found. Nothing to process."
    echo "[DONE] Training script starter completed - no work to do"
    exit 0
fi

# Handle explicit "no jobs" responses from API - INCLUDING EMPTY ARRAY
if echo "$response_first_come_training_job" | grep -q '"hasQueuedJobs":false' || \
   echo "$response_first_come_training_job" | grep -q '"modelId":null' || \
   echo "$response_first_come_training_job" | grep -q '"jobId":null' || \
   [ "$response_first_come_training_job" = "{}" ] || \
   [ "$response_first_come_training_job" = "null" ] || \
   [ "$response_first_come_training_job" = "[]" ]; then
    echo "[INFO] No queued training jobs available. Queue is empty."
    echo "[DONE] Training script starter completed - no work to do"
    exit 0
fi

# Extract model_id and job_id
model_id=$(echo "$response_first_come_training_job" | sed -E 's/.*"modelId":[[:space:]]*([0-9]+).*/\1/')
job_id=$(echo "$response_first_come_training_job" | sed -E 's/.*"jobId":"?([0-9a-zA-Z-]+)"?.*/\1/')
model_name=$(echo "$response_first_come_training_job" | sed -E 's/.*"modelName":"?([^",}]+)"?.*/\1/')
major_version=$(echo "$response_first_come_training_job" | sed -E 's/.*"majorVersion":[[:space:]]*([0-9]+).*/\1/')
minor_version=$(echo "$response_first_come_training_job" | sed -E 's/.*"minorVersion":[[:space:]]*([0-9]+).*/\1/')
latest=$(echo "$response_first_come_training_job" | sed -E 's/.*"latest":[[:space:]]*(true|false).*/\1/')
deployment_environment=$(echo "$response_first_come_training_job" | sed -E 's/.*"deploymentEnvironment":"?([^",}]+)"?.*/\1/')

echo "[DEBUG] Raw response: '$response_first_come_training_job'"

if [ -z "$model_id" ]; then
    echo "[ERROR] Model ID not found in response"
    echo "[DEBUG] Raw response: '$response_first_come_training_job'"
    exit 1
fi

if [ -z "$job_id" ] || [ "$job_id" = "$response_first_come_training_job" ]; then
    echo "[ERROR] Job ID not found or invalid in response"
    echo "[DEBUG] Raw response: '$response_first_come_training_job'"
    exit 1
fi

echo "[MODEL] Model ID: $model_id"
echo "[JOB] Job ID: $job_id"
echo "[MODEL] Model Name: $model_name"
echo "[VERSION] Major Version: $major_version"
echo "[VERSION] Minor Version: $minor_version"
echo "[VERSION] Latest: $latest"
echo "[ENVIRONMENT] Deployment Environment: $deployment_environment"

response_update_job_status=$(curl -s -X POST "$UPDATE_JOB_STATUS" \
    -H "Content-Type: application/json" \
    -d "{\"jobId\": $job_id, \"jobStatus\": \"training-in-progress\"}")
echo "[DEBUG] Update job status response: '$response_update_job_status'"

# Create training progress session
echo "[SESSION] Creating training progress session..."
CREATE_PROGRESS_SESSION_ENDPOINT="http://ruuter-public:8086/global-classifier/datamodels/progress/create"

response_create_session=$(curl -s -X POST "$CREATE_PROGRESS_SESSION_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{
        \"modelId\": $model_id,
        \"modelName\": \"$model_name\",
        \"majorVersion\": $major_version,
        \"minorVersion\": $minor_version,
        \"latest\": $latest
    }")

echo "[DEBUG] Create session response: '$response_create_session'"

# Extract session ID from response
if [ -z "$response_create_session" ]; then
    echo "[ERROR] Failed to create training progress session - empty response"
    exit 1
fi

# Check if session creation was successful
if echo "$response_create_session" | grep -q '"operationSuccessful":true'; then
    session_id=$(echo "$response_create_session" | sed -E 's/.*"sessionId":"?([0-9]+)"?.*/\1/')
    
    if [ -z "$session_id" ] || [ "$session_id" = "$response_create_session" ]; then
        echo "[ERROR] Failed to extract session ID from response"
        echo "[DEBUG] Raw response: '$response_create_session'"
        exit 1
    fi
    
    echo "[SESSION] Training progress session created successfully with ID: $session_id"
else
    echo "[ERROR] Training progress session creation failed"
    echo "[DEBUG] Raw response: '$response_create_session'"
    exit 1
fi

# Update initial training progress
echo "[PROGRESS] Updating initial training progress..."
UPDATE_PROGRESS_SESSION_ENDPOINT="http://ruuter-public:8086/global-classifier/datamodels/progress/update"

response_update_progress=$(curl -s -X POST "$UPDATE_PROGRESS_SESSION_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{
        \"sessionId\": $session_id,
        \"trainingStatus\": \"Initiating Training\",
        \"trainingMessage\": \"Download and preparing dataset\",
        \"progressPercentage\": 20,
        \"processComplete\": false
    }")

echo "[DEBUG] Update progress response: '$response_update_progress'"

# Check if progress update was successful
if [ -z "$response_update_progress" ]; then
    echo "[WARNING] Failed to update initial training progress - empty response"
else
    echo "[PROGRESS] Initial training progress updated successfully"
fi

# Get dataset ID
response_get_dataset_id=$(curl -s -X POST "$GET_DATA_MODEL_BY_MODEL_ID_SQL" \
    -H "Content-Type: application/json" \
    -d "{\"model_id\": $model_id}")
echo "[DEBUG] Dataset ID response: '$response_get_dataset_id'"

# Handle empty response
if [ -z "$response_get_dataset_id" ] || [ "$response_get_dataset_id" = "[]" ]; then
    echo "[ERROR] No dataset information found for model ID: $model_id"
    exit 1
fi

dataset_id=$(echo "$response_get_dataset_id" | sed -E 's/.*"connectedDsId":([0-9]+).*/\1/')

if [ -z "$dataset_id" ] || [ "$dataset_id" = "$response_get_dataset_id" ]; then
    echo "[ERROR] Connected Dataset ID not found in response"
    echo "[DEBUG] Raw response: '$response_get_dataset_id'"
    exit 1
fi

echo "[DATASET] Dataset ID: $dataset_id"

base_models_json=$(echo "$response_get_dataset_id" | sed -nE 's/.*"value":"(\[[^]]+\])".*/\1/p' | sed 's/\\"/"/g')

if [[ "$base_models_json" == "["* ]] && [[ "$base_models_json" == *"]" ]]; then
    model_types="$base_models_json"
    echo "[MODELS] Model types extracted from DB: $model_types"
else
    echo "[ERROR] Failed to extract base models from response"
    echo "[ERROR] Raw response: $response_get_dataset_id"
    echo "[ERROR] Extracted base_models: $base_models_json"
    exit 1
fi

# Activate existing virtualenv
echo "[INFO] Activating existing virtualenv at /app/python_virtual_env"
source /app/python_virtual_env/bin/activate || { echo "[ERROR] Failed to activate virtualenv"; exit 1; }
export PYTHONPATH="/app:/app/src:/app/src/training:/app/src/s3_dataset_processor:$PYTHONPATH"
echo "[DEBUG] PYTHONPATH set to: $PYTHONPATH"
# Add these debug commands
echo "[DEBUG] Virtual environment debugging:"
echo "  - VIRTUAL_ENV: $VIRTUAL_ENV"
echo "  - Python path: $(which python)"
echo "  - Python version: $(python --version)"
echo "  - Pip path: $(which pip)"
echo "  - Site packages: $(python -c "import site; print(site.getsitepackages())")"

# List installed packages
echo "[DEBUG] Installed packages in current environment:"
pip list | head -20  # Show first 20 packages

# Check required packages
echo "[DEBUG] Testing individual package imports inside virtualenv..."
missing_pkgs=()
for pkg in torch transformers sklearn mlflow pandas numpy loguru; do
    echo "[DEBUG] Testing import for $pkg"
    if ! python -c "import $pkg" &>/dev/null; then
        echo "[ERROR] Package '$pkg' is missing or failed to import"
        missing_pkgs+=("$pkg")
    else
        echo "[INFO] Package '$pkg' found"
    fi
done

# Install if missing
if [ ${#missing_pkgs[@]} -ne 0 ]; then
    echo "[ACTION] Missing packages detected: ${missing_pkgs[*]}"

    # Install uv using secure unmanaged installation (same as presigned_url_generate.sh)
    UV_INSTALL_DIR="/app/tools/uv"
    UV_BIN="$UV_INSTALL_DIR/uv"

    if [ ! -f "$UV_BIN" ]; then
        echo "[UV] Installing uv to isolated directory..."
        
        # Create installation directory
        mkdir -p "$UV_INSTALL_DIR" || {
            echo "[ERROR] Failed to create UV installation directory"
            exit 1
        }
        
        # Use unmanaged installation to avoid root directory modifications
        curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$UV_INSTALL_DIR" sh || {
            echo "[ERROR] Failed to install uv"
            exit 1
        }
        
        # Verify installation
        if [ ! -x "$UV_BIN" ]; then
            echo "[ERROR] UV installation failed or not executable"
            exit 1
        fi
        
        # Verify functionality
        "$UV_BIN" --version || {
            echo "[ERROR] UV installation corrupted"
            exit 1
        }
        
        echo "[UV] Successfully installed uv (unmanaged) to $UV_INSTALL_DIR"
    fi

    if [ ! -f /app/src/training/requirements-gpu.txt ]; then
        echo "/app/src/training/requirements-gpu.txt not found!"
        exit 1
    fi

    echo "[INSTALL] Installing from /app/src/training/requirements-gpu.txt using secure uv..."
    "$UV_BIN" pip install --python "$VIRTUAL_ENV/bin/python3" -r /app/src/training/requirements-gpu.txt || {
        echo "[WARNING] uv install failed — trying pip as fallback..."
        pip install -r /app/src/training/requirements-gpu.txt || {
            echo "[ERROR] Both uv and pip install failed inside virtualenv"
            exit 1
        }
    }

    echo "[SUCCESS] Required packages installed successfully inside virtualenv."
else
    echo "[SUCCESS] All required Python packages are already installed inside virtualenv."
fi
echo "[SUCCESS] All checks passed, proceeding with training script..."
echo "[INFO] Starting training for Model ID: $model_id, Dataset ID: $dataset_id, Model Major Version: $major_version, Model Minor Version: $minor_version, Model Name: $model_name"

# Set up training parameters
TRAINING_SCRIPT="/app/src/training/model_trainer.py"
TRAINING_OUTPUT_DIR="/app/models"
MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://mlflow:5000}"
PROCESSED_DATA_DIR="/app/data/processed"

# Create output directory for this training job
training_output_dir="${TRAINING_OUTPUT_DIR}/model_${model_id}"
mkdir -p "$training_output_dir"

echo "[INFO] Training parameters:"
echo "  - Dataset ID: $dataset_id"
echo "  - Model ID: $model_id"
echo "  - Model Type: $model_types"
echo "  - Output Dir: $training_output_dir"
echo "  - MLflow URI: $MLFLOW_TRACKING_URI"
echo "  - Model Name: $model_name"
echo "  - Major Version: $major_version"
echo "  - Minor Version: $minor_version"
echo "  - Is Latest: $latest"
echo "  - Deployment Environment: $deployment_environment"

# Call the training script
echo "[EXECUTE] Calling training script..."

python3 "$TRAINING_SCRIPT" \
    --model_types "$model_types" \
    --model_id "$model_id" \
    --job_id "$job_id" \
    --dataset_id "$dataset_id" \
    --model_name "$model_name" \
    --major_version "$major_version" \
    --minor_version "$minor_version" \
    --latest "$latest" \
    --deployment_environment "$deployment_environment" \
    --session_id "$session_id" \

training_exit_code=$?

# Check training result
if [ $training_exit_code -eq 0 ]; then
    echo "[SUCCESS] Training completed successfully"
    echo "[OUTPUT] Training outputs saved to: $training_output_dir"

    # Update job status to trained
    echo "[UPDATE] Updating job status to trained..."
    response_update_job_status=$(curl -s -X POST "$UPDATE_JOB_STATUS" \
    -H "Content-Type: application/json" \
    -d "{\"jobId\": $job_id, \"jobStatus\": \"trained\"}")
        
    echo "[DEBUG] Update job status to trained response: '$response_update_job_status_trained'"
else
    echo "[FAILED] Training failed with exit code: $training_exit_code"

    echo "[UPDATE] Updating job status to training-failed..."
    response_update_job_status=$(curl -s -X POST "$UPDATE_JOB_STATUS" \
    -H "Content-Type: application/json" \
    -d "{\"jobId\": $job_id, \"jobStatus\": \"training-failed\"}")

    echo "[MODEL] Updating model training status to failed..."
    UPDATE_MODEL_TRAINING_STATUS_FAILED="http://resql:8082/global-classifier/update-training_status-failed"
    response_update_model_status=$(curl -s -X POST "$UPDATE_MODEL_TRAINING_STATUS_FAILED" \
    -H "Content-Type: application/json" \
    -d "{\"model_id\": $model_id}")

    echo "[DEBUG] Update model training status response: '$response_update_model_status'"

    echo "[PROGRESS] Updating progress session to show training failure..."
    response_update_progress_failure=$(curl -s -X POST "$UPDATE_PROGRESS_SESSION_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "{
        \"sessionId\": $session_id,
        \"trainingStatus\": \"Training Failed\",
        \"trainingMessage\": \"Model training has failed\",
        \"progressPercentage\": 100,
        \"processComplete\": false
    }")

    echo "[DEBUG] Update progress failure response: '$response_update_progress_failure'"

    if [ -z "$response_update_progress_failure" ]; then
        echo "[WARNING] Failed to update progress session with failure status"
    else
        echo "[PROGRESS] Progress session updated with failure status successfully"
    fi

    exit 1
fi

echo "[DONE] Training script starter completed"