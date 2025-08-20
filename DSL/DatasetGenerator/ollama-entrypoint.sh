#!/bin/bash

MODEL_NAME=${MODEL_NAME:-"gemma3:1b-it-qat"}

# Start Ollama in the background
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama API to be ready
until ollama list > /dev/null 2>&1; do
  echo "Waiting for Ollama to start..."
  sleep 2
done

# Pull the model if not already present
if ! ollama list | grep -q "$MODEL_NAME"; then
  echo "Pulling model $MODEL_NAME..."
  ollama pull "$MODEL_NAME"
fi

echo "Ollama is ready with model $MODEL_NAME"
wait $OLLAMA_PID