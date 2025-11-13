#!/bin/bash

echo "Starting presigned URL generation..."

# Check if environment variable is set
if [ -z "$centopsAgencies" ]; then
  echo "Error: centopsAgencies environment variable is not set"
  exit 1
fi

echo "Received centopsAgencies: $centopsAgencies"

# Decode the URL-encoded string for debugging
decoded_agencies=$(python3 -c "import urllib.parse, sys; print(urllib.parse.unquote(sys.argv[1]))" "$centopsAgencies" 2>/dev/null)
echo "Decoded agencies: $decoded_agencies"

# Install uv if not found (using unmanaged installation for security)
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

# Activate Python virtual environment
VENV_PATH="/app/python_virtual_env"
echo "[VENV] Activating virtual environment at: $VENV_PATH"
source "$VENV_PATH/bin/activate" || {
    echo "[ERROR] Failed to activate virtual environment"
    exit 1
}

# Install required packages
echo "[PACKAGES] Installing required packages..."
"$UV_BIN" pip install --python "$VENV_PATH/bin/python3" "boto3>=1.35.0" || exit 1
"$UV_BIN" pip install --python "$VENV_PATH/bin/python3" "botocore>=1.35.0" || exit 1
"$UV_BIN" pip install --python "$VENV_PATH/bin/python3" "requests>=2.32.0" || exit 1
echo "[PACKAGES] All packages installed successfully"

export PYTHONPATH="/app:/app/src:$PYTHONPATH"

# Call Python script with the agencies data
echo "Calling Python script..."
python3 "/app/src/scripts/generate_signed_urls.py" "$centopsAgencies" 2>&1

# Check if Python script execution was successful
if [ $? -eq 0 ]; then
    echo "Presigned URL generation completed successfully"
else
    echo "Error: Presigned URL generation failed"
    exit 1
fi
