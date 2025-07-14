from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
import random
import time
import torch
from transformers import set_seed
import mlflow
import numpy as np
import requests
import os
import json
import sys
from loguru import logger
from typing import Dict, Any
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from scripts.constants import (
    LOG_DIRECTORY,
    LOG_FORMAT,
    LOG_FILE_NAME,
    ROTATION_SIZE,
    RETENTION_PERIOD,
    LOG_FILE_HANDLER_FORMAT,
    TRAINING_JOB_STATUS_UPDATE_URL,
    DATA_MODEL_TRAINING_UPDATE_URL,
    SEED,
)

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


def log_confusion_matrix(cm, class_names=None):
    """
    Create and log a confusion matrix figure to MLflow.
    """
    plt.figure(figsize=(10, 8))
    if class_names:
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=class_names,
            yticklabels=class_names,
        )
    else:
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues")

    plt.title("Confusion Matrix")
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.tight_layout()

    # Log to MLflow
    mlflow.log_figure(plt.gcf(), "confusion_matrix.png")
    plt.close()


def log_confusion_matrix_with_names(cm, class_names):
    """
    Create and log a confusion matrix figure with class names to MLflow.
    """
    plt.figure(figsize=(12, 10))

    # Create heatmap
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=class_names,
        yticklabels=class_names,
        cbar_kws={"label": "Count"},
    )

    plt.title("Confusion Matrix", fontsize=16)
    plt.ylabel("True Label", fontsize=14)
    plt.xlabel("Predicted Label", fontsize=14)

    # Rotate labels for better readability
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)

    plt.tight_layout()

    # Log to MLflow
    mlflow.log_figure(plt.gcf(), "confusion_matrix_with_names.png")
    plt.close()


def compute_metrics(predictions, labels, probs, class_names=None):
    """
    Compute comprehensive metrics including per-class accuracy with class names.

    Args:
        predictions: Model predictions
        labels: True labels
        probs: Prediction probabilities
        class_names: List of class names (optional)
    """

    # Overall metrics
    accuracy = accuracy_score(labels, predictions)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="macro"
    )

    # Per-class metrics
    precision_per_class, recall_per_class, f1_per_class, _ = (
        precision_recall_fscore_support(labels, predictions, average=None)
    )

    # Calculate per-class accuracy
    cm = confusion_matrix(labels, predictions)
    per_class_accuracy = cm.diagonal() / cm.sum(axis=1)

    # Build metrics dictionary - FLAT structure with meaningful names
    metrics = {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
    }

    # Add per-class metrics directly to main dictionary (no nesting)
    for i in range(len(precision_per_class)):
        if class_names and i < len(class_names):
            # Use actual class name
            class_key = class_names[i].replace(" ", "_").lower()
        else:
            # Fallback to class_N format
            class_key = f"class_{i}"

        # Add metrics directly to main dictionary
        metrics[f"{class_key}_precision"] = float(precision_per_class[i])
        metrics[f"{class_key}_recall"] = float(recall_per_class[i])
        metrics[f"{class_key}_f1"] = float(f1_per_class[i])
        metrics[f"{class_key}_accuracy"] = float(per_class_accuracy[i])

    # ROC AUC for binary/multiclass
    if len(np.unique(labels)) == 2:
        metrics["roc_auc"] = float(roc_auc_score(labels, probs[:, 1]))
    else:
        metrics["roc_auc"] = float(roc_auc_score(labels, probs, multi_class="ovr"))

    return metrics, cm


def update_job_status(job_id: int, status: str) -> bool:
    """Update training job status in database."""
    try:
        payload = {"jobId": job_id, "jobStatus": status}

        response = requests.post(
            TRAINING_JOB_STATUS_UPDATE_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code == 200:
            logger.info(f"✅ Job status updated to '{status}' for job ID: {job_id}")
            return True
        else:
            logger.error(f"Failed to update job status: HTTP {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        return False

def update_data_model_training(model_id: int, training_results: dict, model_s3_location: str) -> bool:
    """
    Send training results to the API endpoint for database storage.
    
    Args:
        model_id (int): The model ID
        training_results (dict): Preprocessed training results payload
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        api_url = DATA_MODEL_TRAINING_UPDATE_URL
        
        payload = {
            "modelId": model_id,
            "trainingResults": training_results,
            "modelS3Location": model_s3_location
        }
        
        logger.info(f"Sending training results to API for model ID: {model_id}")
        logger.debug(f"API URL: {api_url}")
        logger.debug(f"Payload size: {len(json.dumps(payload))} characters")
        
        # Send POST request
        response = requests.post(
            api_url,
            json=payload,
            headers={
                "Content-Type": "application/json"
            }
        )
        
        # Check response
        if response.status_code == 200:
            logger.info("✅ Training results successfully sent to API")
            logger.debug(f"API Response: {response.text}")
            return True
        else:
            logger.error(f"❌ API request failed with status code: {response.status_code}")
            logger.error(f"Response text: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error when sending training results to API: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error when sending training results to API: {str(e)}")
        return False


def preprocess_training_summary_from_dict(
    training_summary_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Efficiently preprocess training_summary dictionary to create a sorted payload.
    Use this when you already have the data loaded as a dictionary.

    Args:
        training_summary_dict: Training summary data as dictionary

    Returns:
        Dictionary with preprocessed payload sorted by F1 score
    """
    try:
        # Extract basic info
        training_summary = training_summary_dict.get("training_summary", {})
        model_results = training_summary_dict.get("model_results", {})

        # Build models performance list with efficient processing
        models_performance = []

        for model_type, result in model_results.items():
            if result.get("status") == "success":
                test_metrics = result.get("test_metrics", {})

                # Extract overall metrics (non-class specific)
                overall_metrics = {
                    "accuracy": test_metrics.get("accuracy", 0.0),
                    "precision": test_metrics.get("precision", 0.0),
                    "recall": test_metrics.get("recall", 0.0),
                    "f1": test_metrics.get("f1", 0.0),
                    "roc_auc": test_metrics.get("roc_auc", 0.0),
                }

                # Extract class-specific metrics efficiently using dict comprehension
                class_metrics = {}
                class_metric_items = [
                    (k, v)
                    for k, v in test_metrics.items()
                    if "_" in k
                    and k.endswith(("_precision", "_recall", "_f1", "_accuracy"))
                ]

                for key, value in class_metric_items:
                    parts = key.rsplit("_", 1)
                    if len(parts) == 2:
                        class_name, metric_type = parts
                        if class_name not in class_metrics:
                            class_metrics[class_name] = {}
                        class_metrics[class_name][metric_type] = value

                # Build model performance entry
                model_entry = {
                    "model_type": model_type,
                    "model_name": result.get("model_name", ""),
                    "status": result.get("status", "success"),
                    "best_epoch": result.get("best_epoch", 0),
                    "best_val_f1": result.get("best_val_f1", 0.0),
                    "training_time_seconds": result.get("training_time_seconds", 0.0),
                    "inference_time_seconds": result.get("inference_time_seconds", 0.0),
                    "num_parameters": result.get("num_parameters", 0),
                    "overall_metrics": overall_metrics,
                    "class_metrics": class_metrics,
                }

                models_performance.append(model_entry)

        # Sort by F1 score (descending) - most efficient sort
        models_performance.sort(key=lambda x: x["overall_metrics"]["f1"], reverse=True)

        # Get best model info (first in sorted list)
        best_model_info = {}
        if models_performance:
            best_model = models_performance[0]
            best_model_info = {
                "model_type": best_model["model_type"],
                "overall_metrics": {
                    "f1_score": best_model["overall_metrics"]["f1"],
                    "accuracy": best_model["overall_metrics"]["accuracy"],
                    "precision": best_model["overall_metrics"]["precision"],
                    "recall": best_model["overall_metrics"]["recall"],
                    "roc_auc": best_model["overall_metrics"]["roc_auc"],
                },
                "class_metrics": best_model["class_metrics"],
            }

        # Build final payload
        payload = {
            "training_summary": training_summary,
            "models_performance": models_performance,
            "best_model_info": best_model_info,
        }

        return payload

    except Exception as e:
        logger.error(f"Error preprocessing training summary: {str(e)}")
        raise


def set_random_seeds(seed_val=SEED):
    random.seed(seed_val)
    np.random.seed(seed_val)
    torch.manual_seed(seed_val)
    torch.cuda.manual_seed_all(seed_val)
    set_seed(seed_val)


def evaluate(model, dataloader, device, num_labels):
    """
    Evaluate a trained model on a given dataset and return predictions, true labels, and probabilities.

    This function performs inference on the provided dataloader to compute model predictions,
    extract true labels, and calculate class probabilities. It's used for validation during
    training and final testing to assess model performance.

    Args:
        model (torch.nn.Module): The trained PyTorch model to evaluate. Should be a
            transformers AutoModelForSequenceClassification or compatible model.
        dataloader (torch.utils.data.DataLoader): DataLoader containing the evaluation dataset.
            Expected to yield batches with 'input_ids', 'attention_mask', and 'label' keys.
        device (torch.device): The device (CPU or CUDA) where the model and data should be processed.
        num_labels (int): Number of classes in the classification task. Used for validation
            but not directly in computation.

    Returns:
        tuple: A tuple containing three numpy arrays:
            - predictions (np.ndarray): Array of predicted class indices with shape (n_samples,).
                Contains the argmax of model logits for each sample.
            - true_labels (np.ndarray): Array of ground truth class indices with shape (n_samples,).
                Contains the actual labels from the dataset.
            - all_probs (np.ndarray): Array of class probabilities with shape (n_samples, num_labels).
                Contains softmax probabilities for each class for each sample.

    Example:
        >>> # During validation
        >>> val_preds, val_labels, val_probs = evaluate(model, val_dataloader, device, num_labels)
        >>> val_metrics, _ = compute_metrics(val_preds, val_labels, val_probs, class_names)
        >>>
        >>> # During final testing
        >>> test_preds, test_labels, test_probs = evaluate(model, test_dataloader, device, num_labels)
        >>> test_metrics, test_cm = compute_metrics(test_preds, test_labels, test_probs, class_names)

    Notes:
        - The function sets the model to evaluation mode (model.eval()) and disables gradient
          computation (torch.no_grad()) for efficient inference.
        - Predictions are computed using argmax of logits, while probabilities use softmax.
        - All tensors are moved to CPU and converted to numpy arrays before returning.
        - The function processes data in batches to handle large datasets efficiently.
        - This function is compatible with Hugging Face transformers models and custom PyTorch models
          that return outputs with a 'logits' attribute.

    Raises:
        RuntimeError: If the model forward pass fails (e.g., shape mismatches, CUDA errors).
        KeyError: If the expected keys ('input_ids', 'attention_mask', 'label') are missing
            from dataloader batches.
        AttributeError: If the model outputs don't have the expected 'logits' attribute.

    See Also:
        - compute_metrics(): Used to calculate evaluation metrics from the returned arrays
        - measure_inference_time(): For measuring model inference speed
        - train_epoch(): For the training counterpart of this evaluation function
    """
    model.eval()
    predictions = []
    true_labels = []
    all_probs = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

            logits = outputs.logits
            probs = torch.nn.functional.softmax(logits, dim=-1)

            predictions.extend(torch.argmax(logits, dim=-1).cpu().numpy())
            true_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    return np.array(predictions), np.array(true_labels), np.array(all_probs)


def measure_inference_time(model, dataloader, device, num_runs=100):
    """
    Measure the average inference time per batch for model performance benchmarking.

    Args:
        model (torch.nn.Module): The trained model to benchmark.
        dataloader (torch.utils.data.DataLoader): DataLoader with test batches.
        device (torch.device): Device for model computation (CPU/CUDA).
        num_runs (int, optional): Number of batches to time. Defaults to 100.

    Returns:
        float: Average inference time per batch in seconds.

    Example:
        >>> avg_time = measure_inference_time(model, test_dataloader, device)
        >>> mlflow.log_metric("avg_inference_time_seconds", avg_time)

    Note:
        Used for production deployment planning and model comparison.
    """
    model.eval()
    times = []

    with torch.no_grad():
        for i, batch in enumerate(dataloader):
            if i >= num_runs:
                break

            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)

            start_time = time.time()
            _ = model(input_ids=input_ids, attention_mask=attention_mask)
            end_time = time.time()

            times.append(end_time - start_time)

    return float(np.mean(times))
