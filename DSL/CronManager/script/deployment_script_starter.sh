#!/bin/bash
# File: DSL/CronManager/script/deployment_script_starter.sh
# Bridge script between CronManager DSL and Python deployment orchestrator

# Script metadata
SCRIPT_NAME="deployment_script_starter.sh"
SCRIPT_VERSION="1.0.0"

echo "[START] $SCRIPT_NAME v$SCRIPT_VERSION"
echo "[TIMESTAMP] $(date '+%Y-%m-%d %H:%M:%S')"

# Python deployment orchestrator path
PYTHON_SCRIPT="/app/inference_scripts/deployment_orchestrator.py"

# Environment variable validation
echo "[ENV] Validating required environment variables..."

# Check for required environment variables passed from CronManager DSL
required_vars=("modelId" "currentEnv" "targetEnv" "firstDeployment")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        missing_vars+=("$var")
        echo "[MISSING] Environment variable: $var"
    else
        echo "[FOUND] $var=${!var}"
    fi
done

# Exit if any required variables are missing
if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "[ERROR] Missing required environment variables: ${missing_vars[*]}"
    echo "[ERROR] This script requires all environment variables to be set by CronManager DSL"
    exit 1
fi

# Validate firstDeployment boolean value
if [[ "$firstDeployment" != "true" && "$firstDeployment" != "false" ]]; then
    echo "[ERROR] firstDeployment must be 'true' or 'false', got: '$firstDeployment'"
    exit 1
fi

# Validate environment names
valid_envs=("undeployed" "testing" "production")
if [[ ! " ${valid_envs[@]} " =~ " ${currentEnv} " ]]; then
    echo "[ERROR] Invalid currentEnv: '$currentEnv'. Must be one of: ${valid_envs[*]}"
    exit 1
fi

if [[ ! " ${valid_envs[@]} " =~ " ${targetEnv} " ]]; then
    echo "[ERROR] Invalid targetEnv: '$targetEnv'. Must be one of: ${valid_envs[*]}"
    exit 1
fi

# Validate modelId is numeric
if ! [[ "$modelId" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] modelId must be numeric, got: '$modelId'"
    exit 1
fi

echo "[VALIDATION] All environment variables validated successfully"

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "[ERROR] Python deployment orchestrator not found at: $PYTHON_SCRIPT"
    exit 1
fi

echo "[FOUND] Python deployment orchestrator at: $PYTHON_SCRIPT"

# Activate Python virtual environment if it exists
VENV_PATH="/app/python_virtual_env"
if [ -d "$VENV_PATH" ]; then
    echo "[VENV] Activating virtual environment at: $VENV_PATH"
    source "$VENV_PATH/bin/activate" || { 
        echo "[ERROR] Failed to activate virtual environment"; 
        exit 1; 
    }
    echo "[VENV] Virtual environment activated successfully"
    echo "[DEBUG] Python path: $(which python3)"
    echo "[DEBUG] Python version: $(python3 --version)"
else
    echo "[WARNING] Virtual environment not found at: $VENV_PATH"
    echo "[INFO] Using system Python: $(which python3)"
fi

# Install required Python packages from requirements.txt
REQUIREMENTS_FILE="/app/inference_scripts/requirements.txt"
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "[PACKAGES] Installing required Python packages from requirements.txt..."
    python3 -m pip install --quiet --no-cache-dir -r "$REQUIREMENTS_FILE" || {
        echo "[ERROR] Failed to install required packages from requirements.txt"
        exit 1
    }
    echo "[PACKAGES] Required packages installed successfully"
else
    echo "[ERROR] Requirements file not found at: $REQUIREMENTS_FILE"
    exit 1
    echo "[PACKAGES] Required packages installed successfully"
fi

# Log the command that will be executed
echo "[COMMAND] Executing deployment orchestrator with parameters:"
echo "  --model-id: $modelId"
echo "  --current-env: $currentEnv"
echo "  --target-env: $targetEnv"
echo "  --first-deployment: $firstDeployment"

# Execute the Python deployment orchestrator
echo "[EXECUTE] Starting deployment orchestrator..."
python3 "$PYTHON_SCRIPT" \
    --model-id "$modelId" \
    --current-env "$currentEnv" \
    --target-env "$targetEnv" \
    --first-deployment "$firstDeployment"

# Capture exit code
deployment_exit_code=$?

# Report results
if [ $deployment_exit_code -eq 0 ]; then
    echo "[SUCCESS] Deployment completed successfully"
    echo "[RESULT] Model $modelId deployed from $currentEnv to $targetEnv"
    if [ "$firstDeployment" = "true" ]; then
        echo "[INFO] This was a first deployment"
    else
        echo "[INFO] This was a regular deployment"
    fi
else
    echo "[FAILED] Deployment failed with exit code: $deployment_exit_code"
    echo "[DEBUG] Check deployment orchestrator logs located at /app/deployment_logs.log for detailed error information"
    exit $deployment_exit_code
fi

echo "[DONE] $SCRIPT_NAME completed successfully"
echo "[TIMESTAMP] $(date '+%Y-%m-%d %H:%M:%S')"
