#!/bin/bash
# Run all experiments and generate analysis reports.
# This script runs all OOD detection experiments sequentially
# and then generates the analysis and decision documents.

set -e  # Exit on any error

# Setup environment first
echo "Setting up environment..."
python setup_environment.py

# Set PYTHONPATH to include current directory
export PYTHONPATH="${PWD}:${PYTHONPATH}"

# Create output directory
mkdir -p outputs

# Set parameters
TRAIN_FILE="data/train.csv"
DEV_FILE="data/dev.csv"
TEST_FILE="data/test.csv"
OOD_FILE="data/ood_test.csv"
BATCH_SIZE=32
EPOCHS=10
SEED=42
OUTPUT_DIR="outputs"
USE_GPU="--use-gpu"  # Leave empty to use CPU, set to "--use-gpu" to use GPU

# Check for GPU flag
if [ "$1" = "--use-gpu" ]; then
    USE_GPU="--use-gpu"
    echo "Using GPU for training"
else
    echo "Using CPU for training"
fi

# Run all experiments
echo "=== Running all OOD detection experiments ==="
python main.py --experiment all \
    --train-file $TRAIN_FILE \
    --dev-file $DEV_FILE \
    --test-file $TEST_FILE \
    --ood-file $OOD_FILE \
    --output-dir $OUTPUT_DIR \
    --batch-size $BATCH_SIZE \
    --epochs $EPOCHS \
    --seed $SEED \
    $USE_GPU \
    --log-performance \
    --analyze

echo "=== All experiments completed ==="
echo "Results saved to $OUTPUT_DIR"
echo "Analysis report: $OUTPUT_DIR/ANALYSIS.md"
echo "Decision document: $OUTPUT_DIR/DECISION.md"