#!/bin/bash
set -e

echo "=== [ENTRYPOINT DEBUG] Starting MLflow at $(date) ==="
echo "MLFLOW_TRACKING_USERNAME: ${MLFLOW_TRACKING_USERNAME}"
echo "MLFLOW_BACKEND_STORE_URI: ${MLFLOW_BACKEND_STORE_URI}"
echo "MLFLOW_DEFAULT_ARTIFACT_ROOT: ${MLFLOW_DEFAULT_ARTIFACT_ROOT}"
echo "MLFLOW_HOST: ${MLFLOW_HOST:-0.0.0.0}"
echo "MLFLOW_PORT: ${MLFLOW_PORT:-5000}"

# Create necessary directories if they don't exist
mkdir -p /mlflow/mlflow_data /mlflow/mlflow_artifacts

# Start the MLflow server
if [ "$#" -eq 0 ]; then
    exec mlflow server \
        --host "${MLFLOW_HOST:-0.0.0.0}" \
        --port "${MLFLOW_PORT:-5000}" \
        --backend-store-uri "${MLFLOW_BACKEND_STORE_URI:-sqlite:////mlflow/mlflow_data/mlflow.db}" \
        --default-artifact-root "${MLFLOW_DEFAULT_ARTIFACT_ROOT:-file:///mlflow/mlflow_artifacts}" \
        --gunicorn-opts="--workers=1 --timeout 120"
else
    exec "$@"
fi
