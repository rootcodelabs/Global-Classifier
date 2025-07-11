#!/bin/bash

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 [ENTRYPOINT] Starting container setup..."

REQUIREMENTS_FILE="/app/requirements.txt"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ requirements.txt not found at $REQUIREMENTS_FILE"
  exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚡ Installing uv (ultra-fast installer)..."
python3 -m pip install --no-cache-dir uv
if [ $? -ne 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Failed to install uv"
  exit 1
fi

# Verify uv is accessible
if ! command -v uv >/dev/null 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ uv command not found in PATH, falling back to pip"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📦 Installing requirements with pip..."
  python3 -m pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
  if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Failed to install requirements with pip"
    exit 1
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ All requirements installed with pip."
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] 📦 Installing requirements with uv..."
  uv pip install --no-cache --requirement "$REQUIREMENTS_FILE"
  if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Failed to install requirements with uv, falling back to pip..."
    python3 -m pip install --no-cache-dir -r "$REQUIREMENTS_FILE"
    if [ $? -ne 0 ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Failed to install requirements with pip"
      exit 1
    fi
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ All requirements installed with pip (fallback)."
  else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ All requirements installed with uv."
  fi
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚀 Executing: $@"
exec "$@"
