# Training Pipeline Documentation

## Overview

The Global Classifier Training Pipeline is a comprehensive machine learning pipeline designed to train and evaluate multiple transformer-based text classification models. It supports multi-model training, automatic model selection, MLflow experiment tracking, ONNX export, and S3 deployment.

## Features

- **Multi-Model Training**: Train multiple transformer models (BERT, RoBERTa, XLM, etc.) simultaneously
- **Automatic Best Model Selection**: Selects the best performing model based on F1 score
- **MLflow Integration**: Complete experiment tracking with metrics, parameters, and artifacts
- **ONNX Export**: Converts best model to ONNX format for optimized inference
- **S3 Integration**: Automatic upload of trained models to S3 storage
- **Early Stopping**: Prevents overfitting with validation-based early stopping
- **Comprehensive Logging**: Detailed logging with rotation and retention policies
- **Docker Support**: Fully containerized training environment
- **Cron Job Integration**: Automated training scheduling through cron manager

## Architecture

```
Training Pipeline
├── Data Loading & Preprocessing
├── Multi-Model Training Loop
├── Model Evaluation & Selection
├── Best Model Processing
│   ├── ONNX Export
│   └── S3 Upload
├── Results Aggregation
└── Job Status Updates
```

## Directory Structure

```
src/training/
├── scripts/
│   ├── train.py                 # Main training script
│   ├── utils.py                 # Utility functions
│   ├── constants.py             # Configuration constants
│   ├── s3_utility_handler.py    # S3 operations
│   └── create_datasets.py       # Dataset processing
├── logs/                        # Training logs
├── dataset_artifacts/           # Processed datasets
└── models/                      # Trained model outputs
```

## Installation & Setup

### Prerequisites

- Python 3.8+
- CUDA (optional, for GPU training)
- Docker & Docker Compose
- MLflow server
- S3-compatible storage

### Environment Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Global-Classifier
   ```

2. **Build Docker containers**:
   ```bash
   docker-compose build
   ```

3. **Start services**:
   ```bash
   docker-compose up -d
   ```

## Configuration

### Model Configuration

Edit `src/training/scripts/constants.py` to configure supported models:

```python
MODEL_CONFIG = {
    "bert": {
        "name": "bert-base-uncased",
        "max_length": 512
    },
    "roberta": {
        "name": "roberta-base", 
        "max_length": 512
    },
    "xlm": {
        "name": "xlm-roberta-base",
        "max_length": 256
    }
}
```

### Training Parameters

Key training parameters in `constants.py`:

```python
# Dataset processing
TEST_SIZE = 0.2
VALIDATION_SIZE = 0.1
RANDOM_STATE = 42

# Logging configuration
LOG_DIRECTORY = "/app/src/training/logs"
ROTATION_SIZE = "50 MB"
RETENTION_PERIOD = "7 days"
```

## Usage

### Command Line Training

#### Single Model Training

```bash
python src/training/scripts/train.py \
    --model_types '["bert"]' \
    --model_id 123 \
    --job_id 456 \
    --dataset_id "3" \
    --data_dir "data/processed" \
    --output_dir "models/output" \
    --num_epochs 3 \
    --batch_size 16 \
    --learning_rate 2e-5 \
    --mlflow_tracking_uri "http://mlflow:5000"
```

#### Multi-Model Training

```bash
python src/training/scripts/train.py \
    --model_types '["bert", "roberta", "xlm"]' \
    --model_id 123 \
    --job_id 456 \
    --dataset_id "3" \
    --data_dir "data/processed" \
    --output_dir "models/output" \
    --num_epochs 3 \
    --batch_size 16 \
    --learning_rate 2e-5 \
    --mlflow_tracking_uri "http://mlflow:5000"
```

### Docker Training

```bash
docker exec -it cron-manager python3 /app/src/training/scripts/train.py \
    --model_types '["bert", "roberta"]' \
    --model_id 123 \
    --job_id 456 \
    --dataset_id "3" \
    --data_dir "/app/data/processed" \
    --output_dir "/app/models" \
    --mlflow_tracking_uri "http://mlflow:5000"
```

### Automated Training via Cron

The pipeline supports automated training through the cron manager:

```bash
# Trigger training via cron script
./DSL/CronManager/script/train_script_starter.sh
```

## Command Line Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `--model_types` | str | Yes | JSON array of model types to train |
| `--model_id` | int | Yes | Unique identifier for the model |
| `--job_id` | int | Yes | Unique identifier for the training job |
| `--dataset_id` | str | Yes | Dataset identifier |
| `--data_dir` | str | No | Path to processed datasets (default: "data/processed") |
| `--output_dir` | str | Yes | Path to save model outputs |
| `--num_epochs` | int | No | Number of training epochs (default: 3) |
| `--batch_size` | int | No | Training batch size (default: 16) |
| `--learning_rate` | float | No | Learning rate (default: 2e-5) |
| `--weight_decay` | float | No | Weight decay (default: 0.01) |
| `--warmup_ratio` | float | No | Warmup ratio (default: 0.1) |
| `--max_seq_length` | int | No | Maximum sequence length (default: 128) |
| `--seed` | int | No | Random seed (default: 42) |
| `--no_cuda` | flag | No | Disable CUDA usage |
| `--mlflow_tracking_uri` | str | No | MLflow tracking server URI |

## Training Pipeline Workflow

### 1. Data Loading & Preprocessing

```python
# Downloads dataset from S3 if needed
splits, label_mappings = load_data_from_dataset_folder(
    dataset_id, data_dir, download_from_s3=True
)
```

- Downloads aggregated dataset from S3
- Processes raw data using `ScalableDatasetProcessor`
- Creates train/validation/test splits
- Validates processed dataset integrity

### 2. Multi-Model Training

```python
for model_type in model_types:
    model_result = train_single_model(
        model_type=model_type,
        train_texts=train_texts,
        train_labels=train_labels,
        # ... other parameters
    )
```

For each model type:
- Initializes tokenizer and model
- Creates data loaders
- Sets up optimizer and scheduler
- Trains with early stopping
- Evaluates on test set
- Measures inference time

### 3. Model Selection & Processing

```python
# Select best model based on F1 score
best_model = max(results, key=lambda x: x["test_metrics"]["f1"])

# Export to ONNX
onnx_path = convert_model_to_onnx(best_model_path)

# Upload to S3
s3_path = s3_service.upload_trained_model(best_model_path, model_id)
```

### 4. Results Aggregation

```python
results_summary = create_results_summary(
    all_model_results, best_overall_model, dataset_id, model_id
)
```

## Output Structure

### Training Results

```json
{
  "training_summary": {
    "dataset_id": "3",
    "model_id": 123,
    "timestamp": "2024-01-15T10:30:00",
    "total_models_attempted": 3,
    "successful_models": 3,
    "failed_models": 0,
    "best_overall_model": "roberta",
    "best_overall_f1": 0.9245
  },
  "model_results": {
    "bert": {
      "status": "success",
      "test_metrics": {"f1": 0.9123, "accuracy": 0.9234},
      "training_time_seconds": 1800,
      "inference_time_seconds": 0.023
    }
  },
  "model_comparison": {
    "ranking_by_f1": [
      {"model_type": "roberta", "f1": 0.9245},
      {"model_type": "bert", "f1": 0.9123}
    ]
  }
}
```

### Model Artifacts

```
models/model_123/
├── model_roberta/
│   ├── roberta_epoch_2/          # Best checkpoint
│   │   ├── pytorch_model.bin
│   │   ├── config.json
│   │   ├── tokenizer.json
│   │   ├── label_mappings.json
│   │   └── model.onnx
│   └── training_logs.txt
├── model_bert/
│   └── ...
└── training_summary.json
```

## MLflow Integration

### Experiment Tracking

Each model training creates a separate MLflow experiment:

```
Experiment: text_classification_bert_dataset_3
├── Run: bert_dataset_3_20240115_103000
│   ├── Parameters: model_type, learning_rate, batch_size, etc.
│   ├── Metrics: train_loss, val_f1, test_accuracy, etc.
│   └── Artifacts: model, confusion_matrix, logs
```

### Logged Metrics

- **Training**: `train_loss` (per epoch)
- **Validation**: `val_f1`, `val_accuracy`, `val_precision`, `val_recall` (per epoch)
- **Test**: `test_f1`, `test_accuracy`, `test_precision`, `test_recall`
- **Performance**: `training_time_seconds`, `avg_inference_time_seconds`
- **Model**: `num_parameters`

### Accessing MLflow

```bash
# View experiments in MLflow UI
http://localhost:5000

## Monitoring & Logging

### Log Levels

- **DEBUG**: Detailed execution information
- **INFO**: General process information  
- **WARNING**: Non-critical issues
- **ERROR**: Error conditions
- **CRITICAL**: Critical failures

### Log Files

```
src/training/logs/
├── training_20240115.log        # Daily rotation
├── training_20240114.log
└── ...
```

### Real-time Monitoring

```bash
# Follow training logs
docker exec -it cron-manager tail -f /app/src/training/logs/training_$(date +%Y%m%d).log

## Error Handling & Troubleshooting

### Common Issues

#### 1. CUDA Out of Memory

```bash
# Reduce batch size
--batch_size 8

# Use CPU training
--no_cuda
```

#### 2. Dataset Loading Errors

```bash
# Check dataset exists in S3
aws s3 ls s3://your-bucket/datasets/dataset_3/

# Verify processed dataset structure
ls -la data/processed/dataset_3/
```

#### 3. MLflow Connection Issues

```bash
# Check MLflow server status
curl http://mlflow:5000/health

# Update tracking URI
--mlflow_tracking_uri "http://localhost:5000"
```

#### 4. Import/Path Issues

```bash
# Set PYTHONPATH in container
export PYTHONPATH="/app:/app/src:/app/src/training:$PYTHONPATH"

# Check imports manually
python -c "from scripts.constants import MODEL_CONFIG; print('OK')"
```

### Debug Mode

Enable detailed debugging:

```python
# In constants.py
LOG_LEVEL = "DEBUG"

# Or set environment variable
export LOG_LEVEL=DEBUG
```

### Performance Optimization

#### GPU Optimization

```python
# Use mixed precision training
--fp16

# Optimize batch size for GPU memory
--batch_size 32  # Adjust based on GPU memory
```

#### Training Speed

```python
# Reduce epochs for quick testing
--num_epochs 1

# Use smaller max sequence length
--max_seq_length 64

# Disable inference time measurement
# Comment out measure_inference_time() calls
```

## API Integration

### Job Status Updates

The pipeline automatically updates job status via REST API:

```python
# Update status to "training-in-progress"
update_job_status(job_id=456, status="training-in-progress")

# Update status to "trained" on success
update_job_status(job_id=456, status="trained")

# Update status to "failed" on error
update_job_status(job_id=456, status="failed")
```

### Result Storage

Training results are stored in:
- Local JSON files
- MLflow experiments
- Database (via API endpoints)
- S3 storage (model artifacts)

### Integration Tests

```bash
# Test full pipeline with sample data
python src/training/scripts/train.py \
    --model_types '["bert"]' \
    --dataset_id "test_dataset" \
    --num_epochs 1 \
    --batch_size 2
```

## Best Practices

### Model Selection

1. **Use appropriate batch sizes**: Start with 16, adjust based on GPU memory
2. **Monitor validation metrics**: Use early stopping to prevent overfitting
3. **Compare multiple models**: Train BERT, RoBERTa, and XLM for best results
4. **Validate on diverse data**: Ensure test set represents real-world distribution

### Resource Management

1. **GPU Memory**: Monitor with `nvidia-smi`, reduce batch size if needed
2. **Disk Space**: Clean up old model checkpoints regularly
3. **Logging**: Configure appropriate log retention policies
4. **MLflow Storage**: Archive old experiments periodically

### Production Deployment

1. **Model Validation**: Always validate model performance before deployment
2. **ONNX Export**: Use ONNX models for optimized inference
3. **A/B Testing**: Compare new models with existing production models
4. **Monitoring**: Set up alerts for model performance degradation

### Testing

- Write unit tests for new functions
- Add integration tests for pipeline changes
- Test with different model types and datasets
- Validate performance benchmarks