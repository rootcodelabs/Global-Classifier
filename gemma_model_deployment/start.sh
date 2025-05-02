#!/bin/bash

# Load environment variables
source /root/config/env.sh

# Run commands to start Ollama
source /root/scripts/ollama-commands.sh

# Final log and keep container alive
echo "✅ Model is ready for inference!"
echo "🎉 Ollama service is fully operational with $MODEL_NAME model"

exec tail -f /dev/null