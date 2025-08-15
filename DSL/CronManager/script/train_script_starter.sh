#!/bin/bash
# File: DSL/CronManager/script/train_script_starter.sh

# API Endpoints
CHECK_JOB_STATUS_IN_PROGRESS_SQL="http://resql:8082/global-classifier/get-training-job-status-in-progress"
GET_FIRST_COME_TRAINING_JOB_SQL="http://resql:8082/global-classifier/get-queued-training-job"
GET_DATA_MODEL_BY_MODEL_ID_SQL="http://resql:8082/global-classifier/get-data-model-info-by-given-model-id"
UPDATE_JOB_STATUS="http://resql:8082/global-classifier/update-training-job-status"

echo "🔄 [START] Training script starter"

# Check if training is in progress
echo "🔍 [CHECK] Checking if training is in progress..."
response_job_status_in_progres=$(curl -s -X POST "$CHECK_JOB_STATUS_IN_PROGRESS_SQL")
echo "🔍 [DEBUG] Training status response: '$response_job_status_in_progres'"

if [ $? -ne 0 ] || [ -z "$response_job_status_in_progres" ]; then
    echo "❌ [ERROR] Failed to check training status"
    exit 1
fi

if echo "$response_job_status_in_progres" | grep -q '"hasTrainingInProgress":true'; then
    echo "⚠️ [INFO] Training is already in progress. Exiting..."
    exit 0
fi

echo "✅ [AVAILABLE] No training in progress."

# Get first queued training job
echo "🎯 [QUEUE] Getting first queued training job..."
response_first_come_training_job=$(curl -s -X POST "$GET_FIRST_COME_TRAINING_JOB_SQL")
echo "🔍 [DEBUG] First queued job response: '$response_first_come_training_job'"

# Handle empty response (no queued jobs) - this is normal, not an error
if [ -z "$response_first_come_training_job" ]; then
    echo "ℹ️ [INFO] No queued training jobs found. Nothing to process."
    echo "✅ [DONE] Training script starter completed - no work to do"
    exit 0
fi

# Handle explicit "no jobs" responses from API - INCLUDING EMPTY ARRAY
if echo "$response_first_come_training_job" | grep -q '"hasQueuedJobs":false' || \
   echo "$response_first_come_training_job" | grep -q '"modelId":null' || \
   echo "$response_first_come_training_job" | grep -q '"jobId":null' || \
   [ "$response_first_come_training_job" = "{}" ] || \
   [ "$response_first_come_training_job" = "null" ] || \
   [ "$response_first_come_training_job" = "[]" ]; then
    echo "ℹ️ [INFO] No queued training jobs available. Queue is empty."
    echo "✅ [DONE] Training script starter completed - no work to do"
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

echo "🔍 [----DEBUG----] Raw response: '$response_first_come_training_job'"

if [ -z "$model_id" ]; then
    echo "❌ [ERROR] Model ID not found in response"
    echo "🔍 [DEBUG] Raw response: '$response_first_come_training_job'"
    exit 1
fi

if [ -z "$job_id" ] || [ "$job_id" = "$response_first_come_training_job" ]; then
    echo "❌ [ERROR] Job ID not found or invalid in response"
    echo "🔍 [DEBUG] Raw response: '$response_first_come_training_job'"
    exit 1
fi

echo "📦 [MODEL] Model ID: $model_id"
echo "📦 [JOB] Job ID: $job_id"
echo "📦 [MODEL] Model Name: $model_name"
echo "📦 [VERSION] Major Version: $major_version"
echo "📦 [VERSION] Minor Version: $minor_version"
echo "📦 [VERSION] Latest: $latest"
echo "📦 [ENVIRONMENT] Deployment Environment: $deployment_environment"

response_update_job_status=$(curl -s -X POST "$UPDATE_JOB_STATUS" \
    -H "Content-Type: application/json" \
    -d "{\"jobId\": $job_id, \"jobStatus\": \"training-in-progress\"}")
echo "🔍 [DEBUG] Update job status response: '$response_update_job_status'"

# Get dataset ID
response_get_dataset_id=$(curl -s -X POST "$GET_DATA_MODEL_BY_MODEL_ID_SQL" \
    -H "Content-Type: application/json" \
    -d "{\"model_id\": $model_id}")
echo "🔍 [DEBUG] Dataset ID response: '$response_get_dataset_id'"

# Handle empty response
if [ -z "$response_get_dataset_id" ] || [ "$response_get_dataset_id" = "[]" ]; then
    echo "❌ [ERROR] No dataset information found for model ID: $model_id"
    exit 1
fi

dataset_id=$(echo "$response_get_dataset_id" | sed -E 's/.*"connectedDsId":([0-9]+).*/\1/')

if [ -z "$dataset_id" ] || [ "$dataset_id" = "$response_get_dataset_id" ]; then
    echo "❌ [ERROR] Connected Dataset ID not found in response"
    echo "🔍 [DEBUG] Raw response: '$response_get_dataset_id'"
    exit 1
fi

echo "📦 [DATASET] Dataset ID: $dataset_id"

base_models_json=$(echo "$response_get_dataset_id" | sed -nE 's/.*"value":"(\[[^]]+\])".*/\1/p' | sed 's/\\"/"/g')

if [[ "$base_models_json" == "["* ]] && [[ "$base_models_json" == *"]" ]]; then
    model_types="$base_models_json"
    echo "📦 [MODELS] Model types extracted from DB: $model_types"
else
    echo "❌ [ERROR] Failed to extract base models from response"
    echo "❌ [ERROR] Raw response: $response_get_dataset_id"
    echo "❌ [ERROR] Extracted base_models: $base_models_json"
    exit 1
fi

# Activate existing virtualenv
echo "✅ Activating existing virtualenv at /app/python_virtual_env"
source /app/python_virtual_env/bin/activate || { echo "❌ Failed to activate virtualenv"; exit 1; }
export PYTHONPATH="/app:/app/src:/app/src/training:/app/src/s3_dataset_processor:$PYTHONPATH"
echo "🔍 [DEBUG] PYTHONPATH set to: $PYTHONPATH"
# Add these debug commands
echo "🔍 [DEBUG] Virtual environment debugging:"
echo "  - VIRTUAL_ENV: $VIRTUAL_ENV"
echo "  - Python path: $(which python)"
echo "  - Python version: $(python --version)"
echo "  - Pip path: $(which pip)"
echo "  - Site packages: $(python -c "import site; print(site.getsitepackages())")"

# List installed packages
echo "📦 [DEBUG] Installed packages in current environment:"
pip list | head -20  # Show first 20 packages

# Check required packages
echo "🔍 [DEBUG] Testing individual package imports inside virtualenv..."
missing_pkgs=()
for pkg in torch transformers sklearn mlflow pandas numpy loguru; do
    echo "🔍 [DEBUG] Testing import for $pkg"
    if ! python -c "import $pkg" &>/dev/null; then
        echo "❌ [MISSING or failed import] Package '$pkg'"
        missing_pkgs+=("$pkg")
    else
        echo "✅ [FOUND] Package '$pkg'"
    fi
done

# Install if missing
if [ ${#missing_pkgs[@]} -ne 0 ]; then
    echo "⚡ [ACTION] Missing packages detected: ${missing_pkgs[*]}"

    if ! command -v uv &>/dev/null; then
        echo "⚡ Installing uv inside virtualenv..."
        pip install uv || { echo "❌ Failed to install uv"; exit 1; }
    else
        echo "✅ uv already installed."
    fi

    if [ ! -f /app/src/training/requirements-gpu.txt ]; then
        echo "❌ /app/src/training/requirements-gpu.txt not found!"
        exit 1
    fi

    echo "📦 [INSTALL] Installing from /app/src/training/requirements-gpu.txt using uv..."
    uv pip install -r /app/src/training/requirements-gpu.txt || {
        echo "⚠️ uv install failed — trying pip as fallback..."
        pip install -r /app/src/training/requirements-gpu.txt || {
            echo "❌ Both uv and pip install failed inside virtualenv"
            exit 1
        }
    }

    echo "🎉 [SUCCESS] Required packages installed successfully inside virtualenv."
else
    echo "🎉 [SUCCESS] All required Python packages are already installed inside virtualenv."
fi
echo "✅ [VIRTUALENV] All checks passed, proceeding with training script..."
echo "🚀 [TRAINING] Starting training for Model ID: $model_id, Dataset ID: $dataset_id, Model Major Version: $major_version, Model Minor Version: $minor_version, Model Name: $model_name"

# Set up training parameters
TRAINING_SCRIPT="/app/src/training/model_trainer.py"
TRAINING_OUTPUT_DIR="/app/models"
MLFLOW_TRACKING_URI="${MLFLOW_TRACKING_URI:-http://mlflow:5000}"
PROCESSED_DATA_DIR="/app/data/processed"

# Create output directory for this training job
training_output_dir="${TRAINING_OUTPUT_DIR}/model_${model_id}"
mkdir -p "$training_output_dir"

# # Set default training parameters (can be made configurable)
# max_seq_length=128
# num_epochs=3
# batch_size=8
# learning_rate=2e-5

echo "📋 [PARAMS] Training parameters:"
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
echo "🎓 [EXECUTE] Calling training script..."

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
    # --data_dir "$PROCESSED_DATA_DIR" \
    # --output_dir "$training_output_dir" \
    # --mlflow_tracking_uri "$MLFLOW_TRACKING_URI" \

training_exit_code=$?

# Check training result
if [ $training_exit_code -eq 0 ]; then
    echo "🎉 [SUCCESS] Training completed successfully"
    echo "📁 [OUTPUT] Training outputs saved to: $training_output_dir"

    # Update job status to trained
    echo "[UPDATE] Updating job status to trained..."
    response_update_job_status=$(curl -s -X POST "$UPDATE_JOB_STATUS" \
    -H "Content-Type: application/json" \
    -d "{\"jobId\": $job_id, \"jobStatus\": \"trained\"}")
        
    echo "🔍 [DEBUG] Update job status to trained response: '$response_update_job_status_trained'"
else
    echo "[FAILED] Training failed with exit code: $training_exit_code"

    echo "[UPDATE] Updating job status to training-failed..."
    response_update_job_status=$(curl -s -X POST "$UPDATE_JOB_STATUS" \
    -H "Content-Type: application/json" \
    -d "{\"jobId\": $job_id, \"jobStatus\": \"training-failed\"}")

    exit 1
fi

echo "✅ [DONE] Training script starter completed"