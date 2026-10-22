#!/bin/bash
# Exports KEY=value pairs from constants.ini so cron scripts use the same endpoints as Ruuter.
# Usage (at the top of a script): source /app/scripts/load_constants.sh

CONSTANTS_FILE="${CONSTANTS_FILE:-/app/constants.ini}"

if [ ! -f "$CONSTANTS_FILE" ]; then
  echo "[ERROR] Constants file not found: $CONSTANTS_FILE"
  exit 1
fi

while IFS='=' read -r key value || [ -n "$key" ]; do
  key="${key//[[:space:]]/}"
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue   # skip [DSL] header and blank lines
  export "$key=${value%$'\r'}"
done < "$CONSTANTS_FILE"
