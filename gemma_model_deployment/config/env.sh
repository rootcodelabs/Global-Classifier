#!/bin/bash

# CUDA & Ollama config
export OLLAMA_USE_GPU=1
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
export PATH="/root/.ollama/bin:$PATH"

# Docker-related variables (used optionally)
export OLLAMA_PORT=11434
export MODEL_NAME="gemma3:1b-it-qat"