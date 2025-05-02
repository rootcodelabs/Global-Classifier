#!/bin/bash

# Ensure GPU is available
nvidia-smi

# Start Ollama in background
ollama serve &

# Give server time to initialize
sleep 5

# Pull the specified model
ollama pull "$MODEL_NAME"