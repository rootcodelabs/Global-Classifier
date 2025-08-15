"""
Evaluate models on test and OOD data.
"""

# This script evaluates trained models on test and OOD datasets,
# generating visualizations and metrics for comparison.

set -e  # Exit on any error

# Set parameters
TEST_FILE="data/test.csv"
OOD_FILE="data/ood_test.csv"
OUTPUT_DIR="outputs/evaluation"
USE_GPU="--use-gpu"  # Leave empty to use CPU, set to "--use-gpu" to use GPU

# Check for GPU flag
if [ "$1" == "--use-gpu" ]; then
    USE_GPU="--use-gpu"
    echo "Using GPU for evaluation"
else
    echo "Using CPU for evaluation"
fi

# Create output directory
mkdir -p $OUTPUT_DIR

# Models to evaluate
MODELS=("sngp" "energy" "sngp_energy" "ood_class" "softmax")

# Evaluate each model
for MODEL in "${MODELS[@]}"; do
    echo "=== Evaluating $MODEL model ==="
    
    # Path to model directory
    MODEL_DIR="outputs/$MODEL/model/final_model.keras"
    
    # Check if model exists
    if [ ! -d "$MODEL_DIR" ]; then
        echo "Model not found: $MODEL_DIR"
        continue
    fi
    
    # Evaluate on test and OOD data
    python experiments/evaluate_model.py \
        --model-path $MODEL_DIR \
        --model-type $MODEL \
        --test-file $TEST_FILE \
        --ood-file $OOD_FILE \
        --output-dir $OUTPUT_DIR/$MODEL \
        $USE_GPU
        
    echo "Evaluation complete for $MODEL"
    echo "Results saved to $OUTPUT_DIR/$MODEL"
done

# Generate comparison visualizations
echo "=== Generating model comparisons ==="
python utils/comparison_viz.py --results-dir $OUTPUT_DIR --output-dir $OUTPUT_DIR/comparison

echo "=== Evaluation complete ==="
echo "Results saved to $OUTPUT_DIR"