#!/bin/bash

# Redirect shell wrapper messages to stderr so only Python JSON goes to stdout
exec 2>&1

# Get parameters
TEST_PARAM="${testParam:-default}"
DELAY_SECONDS="${delaySeconds:-0}"

# Export environment variables for Python script
export testParam="$TEST_PARAM"
export delaySeconds="$DELAY_SECONDS"

# Execute Python script and capture ONLY its JSON output
# Redirect all shell logging to stderr, keep Python JSON on stdout
python3 /app/src/s3_dataset_processor/python_test.py 2>/dev/null

# Exit with Python script's exit code
exit $?