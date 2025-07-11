import os
import argparse
import time
import json
from datetime import datetime
from typing import Dict, Any, List

import torch
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    get_linear_schedule_with_warmup
)

from scripts.utils import (
    log_confusion_matrix_with_names,
    compute_metrics,
    preprocess_training_summary_from_dict,
    set_random_seeds,
    measure_inference_time,
    evaluate,
    update_job_status
)

import mlflow
from scripts.s3_utility_handler import S3DatasetService
from scripts.create_datasets import ScalableDatasetProcessor
import sys
from scripts.constants import (
    LOG_DIRECTORY,
    LOG_FORMAT,
    LOG_FILE_NAME,
    ROTATION_SIZE,
    RETENTION_PERIOD,
    LOG_FILE_HANDLER_FORMAT,
    MODEL_CONFIG,
    REQUIRED_TRAINING_FILES,
    PROCESSED_DATASET_DIR,
    TEST_SIZE,
    VALIDATION_SIZE,
    RANDOM_STATE
)
from transformers.onnx import export
from transformers.onnx.features import FeaturesManager
from pathlib import Path
from loguru import logger

os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Remove default handler and add custom ones
logger.remove()

# Add console handler for immediate feedback
logger.add(
    sys.stderr,
    level="DEBUG",
    format=LOG_FORMAT,
    colorize=True,
)

# Add file handler
logger.add(
    sink=os.path.join(LOG_DIRECTORY, LOG_FILE_NAME),
    level="DEBUG",
    rotation=ROTATION_SIZE,
    retention=RETENTION_PERIOD,
    backtrace=True,
    diagnose=True,
    format=LOG_FILE_HANDLER_FORMAT,
)


class TextClassificationDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length=128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = str(self.texts[idx])
        label = self.labels[idx]

        encoding = self.tokenizer(
            text,
            add_special_tokens=True,
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_attention_mask=True,
            return_tensors="pt",
        )

        return {
            "input_ids": encoding["input_ids"].flatten(),
            "attention_mask": encoding["attention_mask"].flatten(),
            "label": torch.tensor(label, dtype=torch.long),
        }


def convert_model_to_onnx(model_dir: str):
    """
    Convert a Hugging Face model to ONNX format.
    """
    try:
        model = AutoModelForSequenceClassification.from_pretrained(model_dir)
        tokenizer = AutoTokenizer.from_pretrained(model_dir)

        _, model_onnx_config = FeaturesManager.check_supported_model_or_raise(
            model, feature="sequence-classification"
        )
        onnx_config = model_onnx_config(model.config)

        # # Create dummy input
        # dummy_inputs= tokenizer(
        #     "This is a dummy input for ONNX export",
        #     return_tensors="pt",
        #     padding="max_length",
        #     truncation=True,
        #     max_length=128,
        # )

        output_path = Path(model_dir) / "model.onnx"

        logger.info(f"Exporting model to ONNX format at: {output_path}")
        export(tokenizer, model, onnx_config, opset=14, output=output_path)

        logger.info(f"ONNX model exported to: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"ONNX export failed: {e}")
        return None

def validate_processed_dataset(processed_dataset_dir: str) -> Dict[str, Any]:
    """
    Validate that the processed dataset has all required files.

    Args:
        processed_dataset_dir: Path to processed dataset directory

    Returns:
        Dictionary with validation results and dataset info
    """
    try:
        required_files = REQUIRED_TRAINING_FILES
        validation_result = {"valid": True, "missing_files": [], "dataset_info": {}}

        # Check for required files
        for file_name in required_files:
            file_path = os.path.join(processed_dataset_dir, file_name)
            if not os.path.exists(file_path):
                validation_result["valid"] = False
                validation_result["missing_files"].append(file_name)

        if validation_result["valid"]:
            # Load dataset info
            label_mappings_path = os.path.join(
                processed_dataset_dir, "label_mappings.json"
            )
            with open(label_mappings_path, "r", encoding="utf-8") as f:
                label_mappings = json.load(f)

            # Count samples in each split
            for split in ["train", "val", "test"]:
                split_file = os.path.join(processed_dataset_dir, f"{split}.json")
                with open(split_file, "r", encoding="utf-8") as f:
                    split_data = json.load(f)
                validation_result["dataset_info"][f"{split}_samples"] = len(
                    split_data["texts"]
                )

            validation_result["dataset_info"]["num_classes"] = label_mappings[
                "num_classes"
            ]
            validation_result["dataset_info"]["class_names"] = list(
                label_mappings["label_to_id"].keys()
            )

        logger.info(f"Dataset validation result: {validation_result}")
        return validation_result

    except OSError as e:
        logger.error(f"Error validating processed dataset: {str(e)}")
        raise


def load_data_from_dataset_folder(
    dataset_id: str, data_dir: str, split: str = None, download_from_s3: bool = False
):
    """
    Load data from the dataset structure, with option to download from S3.

    Args:
        dataset_id: Dataset ID (e.g., "3")
        data_dir: Base directory containing prcessed datasets which is used in training
        split: Specific split to load (train/val/test)
        download_from_s3: Whether to download from S3 first

    Returns:
        texts, labels, label_mappings or splits, label_mappings
    """
    if download_from_s3:
        logger.info(f"Downloading and preprocessing dataset {dataset_id} from S3...")

        try:
            s3_service = S3DatasetService()

            # Step 1: Download aggregated dataset from S3
            logger.info("Step 1: Downloading aggregated dataset from S3...")
            aggregated_dataset_path = s3_service.download_aggregated_dataset(dataset_id)

            # Step 2: Use ScalableDatasetProcessor directly for preprocessing
            logger.info(
                "Step 2: Preprocessing dataset using ScalableDatasetProcessor..."
            )

            # Set up output directory for processed datasets
            processed_output_dir = PROCESSED_DATASET_DIR

            # Initialize ScalableDatasetProcessor
            processor = ScalableDatasetProcessor(
                dataset_path=aggregated_dataset_path, output_dir=processed_output_dir
            )

            # Process the dataset
            result = processor.process_dataset(
                test_size=TEST_SIZE, val_size=VALIDATION_SIZE, random_state=RANDOM_STATE
            )

            logger.info(f"Dataset processing result: {result}")

            # Step 3: Validate processed dataset
            processed_dataset_dir = result["output_dir"]
            validation_result = validate_processed_dataset(processed_dataset_dir)

            if not validation_result["valid"]:
                raise FileNotFoundError(
                    f"Dataset validation failed. Missing files: {validation_result['missing_files']}"
                )

            logger.info(f"Dataset info: {validation_result['dataset_info']}")

            # Use the processed dataset directory
            dataset_dir = processed_dataset_dir

        except Exception as e:
            logger.error(f"Failed to download and preprocess from S3: {str(e)}")
            raise
    else:
        # This is the legacy format where datasets are stored locally and it should be in processed format
        dataset_dir = os.path.join(data_dir, f"dataset_{dataset_id}")

    if not os.path.exists(dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    # Load label mappings
    mappings_file = os.path.join(dataset_dir, "label_mappings.json")
    with open(mappings_file, "r", encoding="utf-8") as f:
        label_mappings = json.load(f)

    if split:
        # Load specific split
        split_file = os.path.join(dataset_dir, f"{split}.json")
        with open(split_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data["texts"], data["label_ids"], label_mappings
    else:
        # Load all splits
        splits = {}
        for split_name in ["train", "val", "test"]:
            split_file = os.path.join(dataset_dir, f"{split_name}.json")
            if os.path.exists(split_file):
                with open(split_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                splits[split_name] = {
                    "texts": data["texts"],
                    "labels": data["label_ids"],
                }

        return splits, label_mappings


def train_epoch(model, dataloader, optimizer, scheduler, device):
    """
    Execute one training epoch with forward pass, backpropagation, and optimization.
    
    Args:
        model (torch.nn.Module): The model to train.
        dataloader (DataLoader): Training data batches.
        optimizer (torch.optim.Optimizer): Optimizer for parameter updates.
        scheduler: Learning rate scheduler.
        device (torch.device): Device for computation (CPU/CUDA).
    
    Returns:
        float: Average training loss for the epoch.
    
    Note:
        Includes gradient clipping (max_norm=1.0) for training stability.
    """
    model.train()
    total_loss = 0

    for batch in dataloader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        optimizer.zero_grad()

        outputs = model(
            input_ids=input_ids, attention_mask=attention_mask, labels=labels
        )

        loss = outputs.loss
        loss.backward()

        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()
        scheduler.step()

        total_loss += loss.item()

    return total_loss / len(dataloader)

def train_single_model(
    model_type: str,
    train_texts: List[str],
    train_labels: List[int],
    val_texts: List[str],
    val_labels: List[int],
    test_texts: List[str],
    test_labels: List[int],
    label_mappings: Dict,
    num_labels: int,
    class_names: List[str],
    output_dir: str,
    args,
) -> Dict[str, Any]:
    """
    Train a single transformer model for text classification with MLflow tracking.
    
    Args:
        model_type (str): Model architecture (e.g., "bert", "roberta").
        train_texts, train_labels: Training data and labels.
        val_texts, val_labels: Validation data and labels.
        test_texts, test_labels: Test data and labels.
        label_mappings (Dict): Label mappings and metadata.
        num_labels (int): Number of classification classes.
        class_names (List[str]): Class names for logging.
        output_dir (str): Directory to save trained model.
        args: Training hyperparameters and configuration.
    
    Returns:
        Dict[str, Any]: Training results with status, metrics, and model paths.
    
    Note:
        Uses early stopping, MLflow tracking, and saves best model with ONNX export.
    """

    try:
        # Set up device
        device = torch.device(
            "cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu"
        )

        # Get model configuration
        model_name = MODEL_CONFIG.get(model_type, {}).get("name", model_type)
        config_max_length = MODEL_CONFIG.get(model_type, {}).get(
            "max_length", args.max_seq_length
        )
        max_length = config_max_length if config_max_length else args.max_seq_length
        logger.info(f"Device: {device}")
        logger.info(f"Using model: {model_name}")
        logger.info(f"Max sequence length: {max_length}")

        # Set up tokenizer and model
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name, num_labels=num_labels
        )
        model.to(device)

        # Create datasets
        train_dataset = TextClassificationDataset(
            train_texts, train_labels, tokenizer, max_length=max_length
        )
        val_dataset = TextClassificationDataset(
            val_texts, val_labels, tokenizer, max_length=max_length
        )
        test_dataset = TextClassificationDataset(
            test_texts, test_labels, tokenizer, max_length=max_length
        )

        # Create dataloaders
        train_dataloader = DataLoader(
            train_dataset, batch_size=args.batch_size, shuffle=True
        )
        val_dataloader = DataLoader(val_dataset, batch_size=args.batch_size)
        test_dataloader = DataLoader(test_dataset, batch_size=args.batch_size)

        # Set up optimizer and scheduler
        optimizer = AdamW(
            model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay
        )
        total_steps = len(train_dataloader) * args.num_epochs
        warmup_steps = int(total_steps * args.warmup_ratio)
        scheduler = get_linear_schedule_with_warmup(
            optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps
        )

        # Set up MLflow experiment for this model
        experiment_name = f"text_classification_{model_type}_dataset_{args.dataset_id}"
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(
            run_name=f"{model_type}_dataset_{args.dataset_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ):
            # Log parameters
            mlflow.log_params(
                {
                    "dataset_id": args.dataset_id,
                    "model_type": model_type,
                    "model_name": model_name,
                    "num_epochs": args.num_epochs,
                    "batch_size": args.batch_size,
                    "learning_rate": args.learning_rate,
                    "max_seq_length": max_length,
                    "num_labels": num_labels,
                    "train_samples": len(train_dataset),
                    "val_samples": len(val_dataset),
                    "test_samples": len(test_dataset),
                }
            )

            # Training loop
            start_time = time.time()
            best_val_f1 = 0.0
            best_epoch = 0
            best_model_dir = None

            for epoch in range(args.num_epochs):
                logger.info(f"Epoch {epoch + 1}/{args.num_epochs}")

                # Train
                train_loss = train_epoch(
                    model, train_dataloader, optimizer, scheduler, device
                )
                logger.info(f"Train Loss: {train_loss:.4f}")
                mlflow.log_metric("train_loss", train_loss, step=epoch)

                # Validate
                val_preds, val_labels_eval, val_probs = evaluate(
                    model, val_dataloader, device, num_labels
                )
                val_metrics, _ = compute_metrics(
                    val_preds, val_labels_eval, val_probs, class_names
                )

                logger.info(
                    f"Val F1: {val_metrics['f1']:.4f}, Val Acc: {val_metrics['accuracy']:.4f}"
                )

                for metric_name, metric_value in val_metrics.items():
                    mlflow.log_metric(f"val_{metric_name}", metric_value, step=epoch)

                # Save best model
                if val_metrics["f1"] > best_val_f1:
                    best_val_f1 = val_metrics["f1"]
                    best_epoch = epoch

                    # Save model
                    model_dir = os.path.join(output_dir, f"{model_type}_epoch_{epoch}")
                    os.makedirs(model_dir, exist_ok=True)
                    model.save_pretrained(model_dir)
                    tokenizer.save_pretrained(model_dir)

                    # Save label mappings
                    mappings_file = os.path.join(model_dir, "label_mappings.json")
                    with open(mappings_file, "w", encoding="utf-8") as f:
                        json.dump(label_mappings, f, ensure_ascii=False, indent=2)

                    best_model_dir = model_dir
                    logger.info(f"New best model saved at epoch {epoch + 1}")

            training_time = time.time() - start_time
            mlflow.log_metric("training_time_seconds", training_time)

            # Load best model for final evaluation
            if best_model_dir:
                model = AutoModelForSequenceClassification.from_pretrained(
                    best_model_dir
                )
                model.to(device)

            # Final evaluation
            test_preds, test_labels_eval, test_probs = evaluate(
                model, test_dataloader, device, num_labels
            )
            test_metrics, test_cm = compute_metrics(
                test_preds, test_labels_eval, test_probs, class_names
            )

            logger.info(f"\n{model_type.upper()} Test Results:")
            for metric_name, metric_value in test_metrics.items():
                if not metric_name.startswith("class_"):
                    logger.info(f"  {metric_name}: {metric_value:.4f}")
                mlflow.log_metric(f"test_{metric_name}", metric_value)

            # Log confusion matrix
            log_confusion_matrix_with_names(test_cm, class_names)

            # Measure inference time
            inference_time = measure_inference_time(model, test_dataloader, device)
            mlflow.log_metric("avg_inference_time_seconds", inference_time)

        return {
            "status": "success",
            "model_type": model_type,
            "model_name": model_name,
            "best_epoch": best_epoch + 1,
            "best_val_f1": best_val_f1,
            "training_time_seconds": training_time,
            "test_metrics": test_metrics,
            "best_model_path": best_model_dir,
            "inference_time_seconds": inference_time,
            "num_parameters": sum(p.numel() for p in model.parameters()),
        }

    except Exception as e:
        logger.error(f"Error training {model_type}: {str(e)}")
        return {
            "status": "failed",
            "model_type": model_type,
            "error": str(e),
            "test_metrics": {"f1": 0.0, "accuracy": 0.0},
        }


def train_multiple_models(args):
    """
    Train multiple transformer models and select the best performing one.
    
    Orchestrates multi-model training pipeline with data loading, model training,
    evaluation, and best model processing including ONNX export and S3 upload.
    
    Args:
        args (argparse.Namespace): Command line arguments containing:
            - model_types (str): JSON string of model types (e.g., '["bert", "roberta"]')
            - dataset_id (str): Dataset identifier
            - data_dir (str): Base directory for datasets
            - output_dir (str): Directory to save outputs
            - model_id, job_id (int): Unique identifiers
            - Training hyperparameters (num_epochs, batch_size, learning_rate, etc.)
    
    Returns:
        Dict[str, Any]: Preprocessed training results containing:
            - training_summary: Overall statistics and best model info
            - models_performance: Individual model results
            - model_comparison: Performance comparison across models
            - best_model_s3_path: S3 path of uploaded best model (if successful)
            - best_model_onnx_path: ONNX model path (if successful)
    
    Example:
        >>> args = argparse.Namespace(model_types='["bert", "roberta"]', ...)
        >>> results = train_multiple_models(args)
        >>> print(f"Best model: {results['training_summary']['best_overall_model']}")
    
    Note:
        - Downloads data from S3, trains models sequentially with MLflow tracking
        - Uses early stopping, exports best model to ONNX, uploads to S3
        - Failed models don't stop the pipeline
    """

    try:
        logger.info("🔍 Starting train_multiple_models function")
        logger.info(f"📝 Received args: {vars(args)}")
        # Parse model types from JSON string
        try:
            model_types = json.loads(args.model_types)
            if not isinstance(model_types, list):
                model_types = [model_types]
        except (json.JSONDecodeError, AttributeError):
            # Fallback to single model if parsing fails
            model_types = [args.model_type] if hasattr(args, "model_type") else ["bert"]

        logger.info(f"Training models: {model_types}")

        # Results storage
        all_model_results = {}
        best_overall_model = None
        best_overall_score = 0.0

        # Create main output directory
        main_output_dir = args.output_dir
        os.makedirs(main_output_dir, exist_ok=True)

        # Load data once for all models
        logger.info(f"Loading dataset ID: {args.dataset_id}")
        splits, label_mappings = load_data_from_dataset_folder(
            args.dataset_id, args.data_dir, download_from_s3=True
        )

        # Extract data for each split
        train_texts = splits["train"]["texts"]
        train_labels = splits["train"]["labels"]
        val_texts = splits["val"]["texts"]
        val_labels = splits["val"]["labels"]
        test_texts = splits["test"]["texts"]
        test_labels = splits["test"]["labels"]

        num_labels = label_mappings["num_classes"]
        class_names = [label_mappings["id_to_label"][str(i)] for i in range(num_labels)]

        logger.info("Dataset Info:")
        logger.info(f"  Classes: {num_labels}")
        logger.info(f"  Train samples: {len(train_texts)}")
        logger.info(f"  Val samples: {len(val_texts)}")
        logger.info(f"  Test samples: {len(test_texts)}")

        # Train each model type
        for model_type in model_types:
            try:
                logger.info(f"\n{'=' * 60}")
                logger.info(f"🚀 TRAINING MODEL: {model_type.upper()}")
                logger.info(f"{'=' * 60}")

                # Create model-specific output directory
                model_output_dir = os.path.join(main_output_dir, f"model_{model_type}")
                os.makedirs(model_output_dir, exist_ok=True)

                # Train single model
                model_result = train_single_model(
                    model_type=model_type,
                    train_texts=train_texts,
                    train_labels=train_labels,
                    val_texts=val_texts,
                    val_labels=val_labels,
                    test_texts=test_texts,
                    test_labels=test_labels,
                    label_mappings=label_mappings,
                    num_labels=num_labels,
                    class_names=class_names,
                    output_dir=model_output_dir,
                    args=args,
                )

                # Store results
                all_model_results[model_type] = model_result

                # Check if this is the best model overall
                current_score = model_result["test_metrics"]["f1"]
                if current_score > best_overall_score:
                    best_overall_score = current_score
                    best_overall_model = model_type

                logger.info(
                    f"✅ {model_type.upper()} completed - F1: {current_score:.4f}"
                )

            except Exception as e:
                logger.error(f"❌ Failed to train {model_type}: {str(e)}")
                all_model_results[model_type] = {
                    "status": "failed",
                    "error": str(e),
                    "test_metrics": {"f1": 0.0, "accuracy": 0.0},
                }

        # Process the best model: Export to ONNX and upload to S3
        if (
            best_overall_model
            and all_model_results[best_overall_model]["status"] == "success"
        ):
            try:
                logger.info(f"\n{'=' * 60}")
                logger.info(f"🔄 PROCESSING BEST MODEL: {best_overall_model.upper()}")
                logger.info(f"{'=' * 60}")

                best_model_path = all_model_results[best_overall_model][
                    "best_model_path"
                ]

                # Step 1: Export to ONNX BEFORE uploading to S3
                logger.info("🔄 Exporting best model to ONNX format...")
                onnx_path = convert_model_to_onnx(best_model_path)

                if onnx_path:
                    logger.info(f"✅ ONNX export completed: {onnx_path}")
                    # Update the model result to include ONNX info
                    all_model_results[best_overall_model]["onnx_model_path"] = onnx_path
                else:
                    logger.warning(
                        "⚠️ ONNX export failed, proceeding without ONNX model"
                    )

                # Step 2: Upload to S3 (now includes ONNX model)
                logger.info("📦 Uploading best model to S3...")
                s3_service = S3DatasetService()

                s3_model_path = s3_service.upload_trained_model(
                    model_dir=best_model_path,
                    model_id=args.model_id,
                    model_type=best_overall_model,
                )

                if s3_model_path:
                    logger.info(f"✅ Best model uploaded to S3: {s3_model_path}")
                    all_model_results[best_overall_model]["s3_model_path"] = (
                        s3_model_path
                    )
                else:
                    logger.error("❌ Failed to upload best model to S3")

            except Exception as e:
                logger.error(f"❌ Failed to process best model: {e}")

        # Create comprehensive results summary
        results_summary = create_results_summary(
            all_model_results, best_overall_model, args.dataset_id, args.model_id
        )

        # Add S3 path to summary if available
        if (
            best_overall_model
            and "s3_model_path" in all_model_results[best_overall_model]
        ):
            results_summary["best_model_s3_path"] = all_model_results[
                best_overall_model
            ]["s3_model_path"]

        # Add ONNX path to summary if available
        if (
            best_overall_model
            and "onnx_model_path" in all_model_results[best_overall_model]
        ):
            results_summary["best_model_onnx_path"] = all_model_results[
                best_overall_model
            ]["onnx_model_path"]

        preprocessed_result_payload = preprocess_training_summary_from_dict(
            results_summary
        )

        # Save results summary
        summary_path = os.path.join(main_output_dir, "training_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results_summary, f, indent=2, ensure_ascii=False)

        logger.info(f"\n{'=' * 60}")
        logger.info("🏆 MULTI-MODEL TRAINING COMPLETED")
        logger.info(f"Best Model: {best_overall_model}")
        logger.info(f"Best F1 Score: {best_overall_score:.4f}")
        logger.info(f"Results saved to: {summary_path}")
        if (
            best_overall_model
            and "s3_model_path" in all_model_results[best_overall_model]
        ):
            logger.info(
                f"Model uploaded to S3: {all_model_results[best_overall_model]['s3_model_path']}"
            )
        if (
            best_overall_model
            and "onnx_model_path" in all_model_results[best_overall_model]
        ):
            logger.info(
                f"ONNX model created: {all_model_results[best_overall_model]['onnx_model_path']}"
            )
        logger.info(f"{'=' * 60}")

        return preprocessed_result_payload
    except Exception as e:
        logger.error(f"❌ Critical error in train_multiple_models: {str(e)}")
        raise  # raise the exception so main() can handle it


def create_results_summary(
    all_model_results: Dict[str, Dict],
    best_overall_model: str,
    dataset_id: str,
    model_id: int,
) -> Dict[str, Any]:
    """Create comprehensive results summary."""

    # Calculate summary statistics
    successful_models = [
        r for r in all_model_results.values() if r["status"] == "success"
    ]
    failed_models = [r for r in all_model_results.values() if r["status"] == "failed"]

    summary = {
        "training_summary": {
            "dataset_id": dataset_id,
            "model_id": model_id,
            "timestamp": datetime.now().isoformat(),
            "total_models_attempted": len(all_model_results),
            "successful_models": len(successful_models),
            "failed_models": len(failed_models),
            "best_overall_model": best_overall_model,
            "best_overall_f1": all_model_results[best_overall_model]["test_metrics"][
                "f1"
            ]
            if best_overall_model
            else 0.0,
        },
        "model_results": {},
        "model_comparison": {
            "metrics_comparison": {},
            "ranking_by_f1": [],
            "ranking_by_accuracy": [],
        },
    }

    # Add individual model results
    for model_type, result in all_model_results.items():
        summary["model_results"][model_type] = result

    # Create comparison metrics
    if successful_models:
        comparison_metrics = ["f1", "accuracy", "precision", "recall"]
        for metric in comparison_metrics:
            summary["model_comparison"]["metrics_comparison"][metric] = {
                model_type: result["test_metrics"].get(metric, 0.0)
                for model_type, result in all_model_results.items()
                if result["status"] == "success"
            }

        # Create rankings
        summary["model_comparison"]["ranking_by_f1"] = sorted(
            [
                {"model_type": r["model_type"], "f1": r["test_metrics"]["f1"]}
                for r in successful_models
            ],
            key=lambda x: x["f1"],
            reverse=True,
        )

        summary["model_comparison"]["ranking_by_accuracy"] = sorted(
            [
                {
                    "model_type": r["model_type"],
                    "accuracy": r["test_metrics"]["accuracy"],
                }
                for r in successful_models
            ],
            key=lambda x: x["accuracy"],
            reverse=True,
        )

    return summary


def main():
    logger.info("Starting multi-model training script")

    try:
        parser = argparse.ArgumentParser(
            description="Train and evaluate multiple transformer-based text classifiers"
        )

        # Updated argument for multiple models
        parser.add_argument(
            "--model_types",
            type=str,
            required=True,
            help='JSON array of model types to train (e.g., \'["bert","roberta","xlm"]\')',
        )

        # Keep backward compatibility
        parser.add_argument(
            "--model_type",
            type=str,
            help="Single model type (for backward compatibility)",
        )

        # Model Id
        parser.add_argument(
            "--model_id",
            type=int,
            required=True,
            help="Unique identifier for the model",
        )

        # Job ID
        parser.add_argument(
            "--job_id",
            type=int,
            required=True,
            help="Unique identifier for the training job",
        )

        # Dataset ID
        parser.add_argument(
            "--dataset_id",
            type=str,
            required=True,
            help="Dataset ID for new format (e.g., '3'). Uses new dataset structure.",
        )

        # Data directory
        parser.add_argument(
            "--data_dir",
            type=str,
            default="data/processed",
            help="Path to the directory containing the processed datasets",
        )

        # Output directory
        parser.add_argument(
            "--output_dir",
            type=str,
            required=True,
            help="Path to save model checkpoints and outputs",
        )

        parser.add_argument(
            "--model_name",
            type=str,
            help="Custom model name (when model_type is 'other')",
        )

        # Training parameters
        parser.add_argument(
            "--num_epochs", type=int, default=3, help="Number of training epochs"
        )
        parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
        parser.add_argument(
            "--learning_rate", type=float, default=2e-5, help="Learning rate"
        )
        parser.add_argument(
            "--weight_decay", type=float, default=0.01, help="Weight decay"
        )
        parser.add_argument(
            "--warmup_ratio", type=float, default=0.1, help="Warmup ratio"
        )
        parser.add_argument(
            "--max_seq_length", type=int, default=128, help="Maximum sequence length"
        )
        parser.add_argument("--seed", type=int, default=42, help="Random seed")
        parser.add_argument(
            "--no_cuda", action="store_true", help="Don't use CUDA even if available"
        )

        # MLflow parameters
        parser.add_argument(
            "--mlflow_tracking_uri",
            type=str,
            help="MLflow tracking URI",
        )

        args = parser.parse_args()

        # Set random seeds
        set_random_seeds(args.seed)

        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)

        # Set MLflow tracking URI
        if args.mlflow_tracking_uri:
            mlflow.set_tracking_uri(args.mlflow_tracking_uri)

        # Update model_name if provided
        if (
            args.model_name
            and hasattr(args, "model_type")
            and args.model_type == "other"
        ):
            MODEL_CONFIG["other"] = {"name": args.model_name, "max_length": 128}

        # Train multiple models
        preprocessed_result_payload = train_multiple_models(args)

        # Check if training was successful
        if not preprocessed_result_payload or not preprocessed_result_payload.get(
            "models_performance"
        ):
            logger.error("❌ Training failed: No valid results produced")
            sys.exit(1)

        # Check if at least one model was successfully trained
        successful_models = [
            model
            for model in preprocessed_result_payload["models_performance"]
            if model.get("status") == "success"
        ]

        if not successful_models:
            logger.error("❌ Training failed: No models were successfully trained")
            sys.exit(1)

        # ======================TO DO: training results in DB========================
        logger.info(f"Preprocessed result payload: {preprocessed_result_payload}")
        # ===========================================================================

        # Update job status to trained
        job_status = update_job_status(job_id=args.job_id, status="trained")

        if not job_status:
            logger.error(
                f"Failed to update job status for job ID: {args.job_id} || Training pipeline may not be complete."
            )
        else:
            logger.info(f"Job status updated successfully for job ID: {args.job_id}")
            logger.info("🎉 Multi-model training pipeline completed successfully!")
            sys.exit(0)  # Explicit success exit
    except Exception as e:
        # Update job status to failed
        # update_job_status(job_id=args.job_id, status="failed")
        logger.error(f"❌ Training failed with error: {str(e)}")
        logger.error("Full traceback:", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
