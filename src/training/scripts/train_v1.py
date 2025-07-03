import os
import argparse
import time
import json
import random
import numpy as np
import pandas as pd
from datetime import datetime

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW

from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    get_linear_schedule_with_warmup,
    set_seed,
)

from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    roc_auc_score,
    confusion_matrix,
    roc_curve,
)

import mlflow
import matplotlib.pyplot as plt
import seaborn as sns

# Define constants and configurations
AVAILABLE_MODELS = {
    "bert": "bert-base-uncased",
    "roberta": "roberta-base",
    "xlm": "xlm-roberta-base",
}


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


def set_random_seeds(seed_val=42):
    random.seed(seed_val)
    np.random.seed(seed_val)
    torch.manual_seed(seed_val)
    torch.cuda.manual_seed_all(seed_val)
    set_seed(seed_val)


def load_data(data_path, split=None):
    """
    Load the data from the given path.

    Args:
        data_path: Path to the data file (CSV or JSON)
        split: Train/val/test split to load

    Returns:
        texts, labels
    """
    if split:
        data_path = os.path.join(data_path, f"{split}.csv")

    if data_path.endswith(".csv"):
        df = pd.read_csv(data_path)
    elif data_path.endswith(".json"):
        df = pd.read_json(data_path, lines=True)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")

    text_col = "text" if "text" in df.columns else "content"

    # Check for 'agency' column (our case) or fall back to 'label' or 'class'
    if "agency" in df.columns:
        label_col = "agency"
    elif "label" in df.columns:
        label_col = "label"
    elif "class" in df.columns:
        label_col = "class"
    else:
        raise ValueError(
            "No suitable label column found in the data. Need 'agency', 'label', or 'class'."
        )

    # If labels are strings (e.g., agency names), convert to integers
    if df[label_col].dtype == "object":
        # Create a mapping of agency names to integers
        unique_labels = df[label_col].unique()
        label_map = {label: i for i, label in enumerate(unique_labels)}

        # Save the mapping for later reference
        mapping_file = os.path.join(os.path.dirname(data_path), "label_mapping.json")
        os.makedirs(os.path.dirname(mapping_file), exist_ok=True)
        with open(mapping_file, "w") as f:
            json.dump(label_map, f, indent=2)

        # Convert string labels to integers
        labels = df[label_col].map(label_map).values
    else:
        labels = df[label_col].values

    return df[text_col].values, labels


def compute_metrics(preds, labels, probs=None):
    """
    Compute various classification metrics.

    Args:
        preds: Predicted labels
        labels: True labels
        probs: Prediction probabilities for ROC/PR curves

    Returns:
        Dictionary of metrics
    """
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, preds, average="weighted"
    )

    acc = accuracy_score(labels, preds)

    metrics = {
        "accuracy": acc,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }

    # Compute confusion matrix
    cm = confusion_matrix(labels, preds)

    # Calculate class-wise metrics
    class_precision, class_recall, class_f1, _ = precision_recall_fscore_support(
        labels, preds, average=None
    )

    # Add class metrics to the return dict
    for i, (p, r, f) in enumerate(zip(class_precision, class_recall, class_f1)):
        metrics[f"class_{i}_precision"] = p
        metrics[f"class_{i}_recall"] = r
        metrics[f"class_{i}_f1"] = f

    # Compute ROC AUC if probabilities are provided and it's a binary task
    if probs is not None:
        if probs.shape[1] == 2:  # Binary classification
            metrics["roc_auc"] = roc_auc_score(labels, probs[:, 1])
            # Compute FPR@95TPR
            fpr, tpr, thresholds = roc_curve(labels, probs[:, 1])
            if any(tpr >= 0.95):
                idx = np.argmin(np.abs(tpr - 0.95))
                metrics["fpr@95tpr"] = fpr[idx]
        else:  # Multi-class
            try:
                # One-hot encode the labels for multi-class ROC AUC
                labels_one_hot = np.zeros((len(labels), probs.shape[1]))
                for i, label in enumerate(labels):
                    labels_one_hot[i, label] = 1

                metrics["roc_auc"] = roc_auc_score(
                    labels_one_hot, probs, average="weighted", multi_class="ovr"
                )
            except Exception as e:
                print(f"Warning: Could not compute ROC AUC for multi-class: {str(e)}")

    return metrics, cm


def log_confusion_matrix(cm, class_names=None):
    """
    Create and log a confusion matrix figure to MLflow.

    Args:
        cm: Confusion matrix
        class_names: Names of the classes
    """
    if class_names is None:
        class_names = [f"Class {i}" for i in range(cm.shape[0])]

    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=class_names,
        yticklabels=class_names,
    )
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.title("Confusion Matrix")

    # Save the figure
    confusion_matrix_path = "confusion_matrix.png"
    plt.tight_layout()
    plt.savefig(confusion_matrix_path)
    plt.close()

    # Log the figure to MLflow
    mlflow.log_artifact(confusion_matrix_path)

    # Clean up the file
    os.remove(confusion_matrix_path)


def train_epoch(model, dataloader, optimizer, scheduler, device):
    """Run a single training epoch."""
    model.train()
    total_loss = 0

    for batch in dataloader:
        optimizer.zero_grad()

        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        outputs = model(
            input_ids=input_ids, attention_mask=attention_mask, labels=labels
        )

        loss = outputs.loss
        total_loss += loss.item()

        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step()

    return total_loss / len(dataloader)


def evaluate(model, dataloader, device, num_labels):
    """Evaluate the model on the given dataloader."""
    model.eval()
    all_preds = []
    all_labels = []
    all_probs = []

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)

            logits = outputs.logits

            # Convert logits to probabilities
            probs = torch.nn.functional.softmax(logits, dim=1)

            # Get predicted class (argmax)
            preds = torch.argmax(logits, dim=1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    return np.array(all_preds), np.array(all_labels), np.array(all_probs)


def measure_inference_time(model, dataloader, device, num_runs=100):
    """Measure the average inference time."""
    model.eval()
    batch = next(iter(dataloader))

    input_ids = batch["input_ids"].to(device)
    attention_mask = batch["attention_mask"].to(device)

    # Warm-up
    for _ in range(10):
        with torch.no_grad():
            _ = model(input_ids=input_ids, attention_mask=attention_mask)

    # Measure inference time
    start_time = time.time()
    for _ in range(num_runs):
        with torch.no_grad():
            _ = model(input_ids=input_ids, attention_mask=attention_mask)
    end_time = time.time()

    avg_time = (end_time - start_time) / num_runs
    return avg_time


def train_and_evaluate(args):
    """Main training and evaluation function."""
    # Set up random seeds for reproducibility
    set_random_seeds(args.seed)

    # Set up device
    device = torch.device(
        "cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu"
    )

    # Load data
    train_texts, train_labels = load_data(os.path.join(args.data_dir, "train.csv"))
    val_texts, val_labels = load_data(os.path.join(args.data_dir, "val.csv"))
    test_texts, test_labels = load_data(os.path.join(args.data_dir, "test.csv"))

    # Determine number of classes
    num_labels = len(np.unique(train_labels))

    # Set up model name
    model_name = AVAILABLE_MODELS.get(args.model_type, args.model_type)

    # Set up tokenizer and model
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=num_labels
    )
    model.to(device)

    # Create datasets
    train_dataset = TextClassificationDataset(
        train_texts, train_labels, tokenizer, max_length=args.max_seq_length
    )
    val_dataset = TextClassificationDataset(
        val_texts, val_labels, tokenizer, max_length=args.max_seq_length
    )
    test_dataset = TextClassificationDataset(
        test_texts, test_labels, tokenizer, max_length=args.max_seq_length
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

    # Set up MLflow
    mlflow.set_tracking_uri(args.mlflow_tracking_uri)
    experiment_name = f"text_classification_{args.model_type}"
    mlflow.set_experiment(experiment_name)

    # Start MLflow run
    with mlflow.start_run(
        run_name=f"{args.model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ):
        # Log parameters
        mlflow.log_params(
            {
                "model_type": args.model_type,
                "model_name": model_name,
                "num_epochs": args.num_epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "weight_decay": args.weight_decay,
                "warmup_ratio": args.warmup_ratio,
                "max_seq_length": args.max_seq_length,
                "seed": args.seed,
                "device": str(device),
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

        for epoch in range(args.num_epochs):

            train_loss = train_epoch(
                model, train_dataloader, optimizer, scheduler, device
            )

            mlflow.log_metric("train_loss", train_loss, step=epoch)

            # Evaluate on validation set
            val_preds, val_labels, val_probs = evaluate(
                model, val_dataloader, device, num_labels
            )

            val_metrics, _ = compute_metrics(val_preds, val_labels, val_probs)

            for metric_name, metric_value in val_metrics.items():
                mlflow.log_metric(f"val_{metric_name}", metric_value, step=epoch)

            # Save best model
            if val_metrics["f1"] > best_val_f1:
                best_val_f1 = val_metrics["f1"]
                best_epoch = epoch

                # Save the model
                model_dir = os.path.join(
                    args.output_dir, f"{args.model_type}_epoch_{epoch}"
                )
                os.makedirs(model_dir, exist_ok=True)
                model.save_pretrained(model_dir)
                tokenizer.save_pretrained(model_dir)

                # Log the model
                mlflow.pytorch.log_model(
                    model,
                    f"{args.model_type}_best_model",
                    registered_model_name=f"{args.model_type}_classifier",
                )

        training_time = time.time() - start_time
        mlflow.log_metric("training_time_seconds", training_time)

        # Load the best model for final evaluation
        best_model_path = os.path.join(
            args.output_dir, f"{args.model_type}_epoch_{best_epoch}"
        )
        if os.path.exists(best_model_path):
            model = AutoModelForSequenceClassification.from_pretrained(best_model_path)
            model.to(device)

        # Evaluate on test set
        test_preds, test_labels, test_probs = evaluate(
            model, test_dataloader, device, num_labels
        )

        test_metrics, test_cm = compute_metrics(test_preds, test_labels, test_probs)

        for metric_name, metric_value in test_metrics.items():
            print(f"  {metric_name}: {metric_value:.4f}")
            mlflow.log_metric(f"test_{metric_name}", metric_value)

        # Log confusion matrix
        log_confusion_matrix(test_cm)

        # Measure inference time
        inference_time = measure_inference_time(model, test_dataloader, device)
        mlflow.log_metric("avg_inference_time_seconds", inference_time)

        # Save metrics to a JSON file for easy access
        metrics_path = os.path.join(args.output_dir, f"{args.model_type}_metrics.json")
        output_metrics = {
            "model_type": args.model_type,
            "model_name": model_name,
            "training_time_seconds": training_time,
            "avg_inference_time_seconds": inference_time,
            "test_metrics": test_metrics,
            "best_epoch": best_epoch + 1,
            "best_val_f1": best_val_f1,
        }

        with open(metrics_path, "w") as f:
            json.dump(output_metrics, f, indent=2)

        # Log the metrics file
        mlflow.log_artifact(metrics_path)


def main():
    parser = argparse.ArgumentParser(
        description="Train and evaluate transformer-based text classifiers"
    )

    # Required parameters
    parser.add_argument(
        "--model_type",
        type=str,
        required=True,
        choices=list(AVAILABLE_MODELS.keys()) + ["other"],
        help="Type of model to use (bert, roberta, xlm, or other)",
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        required=True,
        help="Path to the directory containing the data files",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Path to save model checkpoints and outputs",
    )

    # Optional parameters
    parser.add_argument(
        "--model_name",
        type=str,
        default=None,
        help="Full model name (if not using a predefined type)",
    )
    parser.add_argument(
        "--mlflow_tracking_uri",
        type=str,
        default="mlruns",
        help="URI for MLflow tracking server",
    )
    parser.add_argument(
        "--num_epochs", type=int, default=5, help="Number of training epochs"
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="Batch size for training and evaluation",
    )
    parser.add_argument(
        "--learning_rate", type=float, default=2e-5, help="Learning rate"
    )
    parser.add_argument("--weight_decay", type=float, default=0.01, help="Weight decay")
    parser.add_argument(
        "--warmup_ratio",
        type=float,
        default=0.1,
        help="Ratio of training steps for LR warmup",
    )
    parser.add_argument(
        "--max_seq_length",
        type=int,
        default=128,
        help="Maximum sequence length for tokenization",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--no_cuda", action="store_true", help="Disable CUDA even if available"
    )

    args = parser.parse_args()

    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)

    # Update model_name if provided
    if args.model_name and args.model_type == "other":
        AVAILABLE_MODELS["other"] = args.model_name

    train_and_evaluate(args)


if __name__ == "__main__":
    main()
