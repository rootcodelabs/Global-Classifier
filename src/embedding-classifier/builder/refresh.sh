#!/bin/bash
# Automatic refresh of embedding classifier models from the newest dataset
# version, run by CronManager (DSL/CronManager/DSL/embedding_index_refresh.yml)

EMBEDDING_CLASSIFIER_DIR="/app/src/embedding-classifier"
EMBEDDING_VENV="/app/embedding_venv"

cd "$EMBEDDING_CLASSIFIER_DIR" || exit 1
# The builder's environment, as train_script_starter.sh creates it (kept on a volume)
if [ ! -x "$EMBEDDING_VENV/bin/python" ]; then
    echo "[INFO] Creating the builder's environment in $EMBEDDING_VENV"
    UV_PROJECT_ENVIRONMENT="$EMBEDDING_VENV" uv sync --frozen --no-dev || exit 1
fi
HF_HOME="${EMBEDDING_HF_HOME:-/app/embedding_models}" exec "$EMBEDDING_VENV/bin/python" -m builder.refresh
