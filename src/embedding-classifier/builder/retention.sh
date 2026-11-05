#!/bin/bash
# Daily retention of embedding classifier collections, run by CronManager
# (DSL/CronManager/DSL/embedding_index_retention.yml)

EMBEDDING_CLASSIFIER_DIR="/app/src/embedding-classifier"
EMBEDDING_VENV="/app/embedding_venv"

cd "$EMBEDDING_CLASSIFIER_DIR" || exit 1
# The builder's environment, as train_script_starter.sh creates it (kept on a volume)
if [ ! -x "$EMBEDDING_VENV/bin/python" ]; then
    echo "[INFO] Creating the builder's environment in $EMBEDDING_VENV"
    UV_PROJECT_ENVIRONMENT="$EMBEDDING_VENV" uv sync --frozen --no-dev || exit 1
fi
exec "$EMBEDDING_VENV/bin/python" -m builder.retention
