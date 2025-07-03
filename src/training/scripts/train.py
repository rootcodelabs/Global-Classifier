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


def load_data_from_dataset_folder(dataset_id: str, data_dir: str = "data/processed", split: str = None):
    """
    Load data from the new dataset structure.
    
    Args:
        dataset_id: Dataset ID (e.g., "3")
        data_dir: Base directory containing processed datasets
        split: Specific split to load (train/val/test)
    
    Returns:
        texts, labels, label_mappings or splits, label_mappings
    """
    dataset_dir = os.path.join(data_dir, f"dataset_{dataset_id}")
    
    if not os.path.exists(dataset_dir):
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    
    # Load label mappings
    mappings_file = os.path.join(dataset_dir, "label_mappings.json")
    with open(mappings_file, 'r', encoding='utf-8') as f:
        label_mappings = json.load(f)
    
    if split:
        # Load specific split
        split_file = os.path.join(dataset_dir, f"{split}.json")
        with open(split_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data['texts'], data['label_ids'], label_mappings
    else:
        # Load all splits
        splits = {}
        for split_name in ['train', 'val', 'test']:
            split_file = os.path.join(dataset_dir, f"{split_name}.json")
            if os.path.exists(split_file):
                with open(split_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                splits[split_name] = {
                    'texts': data['texts'],
                    'labels': data['label_ids']  # Use numeric labels
                }
        
        return splits, label_mappings


def load_data(data_path, split=None):
    """
    Load the data from the given path (legacy format).

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


# ...existing code...

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

    # Compute ROC AUC if probabilities are provided
    if probs is not None:
        if probs.shape[1] == 2:  # Binary classification
            metrics["roc_auc"] = roc_auc_score(labels, probs[:, 1])
            
            # Compute FPR at 95% TPR (using MLflow-compatible naming)
            fpr, tpr, thresholds = roc_curve(labels, probs[:, 1])
            if any(tpr >= 0.95):
                idx = np.argmin(np.abs(tpr - 0.95))
                metrics["fpr_at_95_tpr"] = fpr[idx]
                
            # Additional useful metrics with proper naming
            if any(tpr >= 0.90):
                idx_90 = np.argmin(np.abs(tpr - 0.90))
                metrics["fpr_at_90_tpr"] = fpr[idx_90]
                
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


def log_confusion_matrix_with_names(cm, class_names):
    """
    Create and log a confusion matrix figure with class names to MLflow.
    """
    plt.figure(figsize=(max(10, len(class_names) * 1.2), max(8, len(class_names) * 1.0)))
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
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)

    # Save the figure
    confusion_matrix_path = "confusion_matrix.png"
    plt.tight_layout()
    plt.savefig(confusion_matrix_path, dpi=300, bbox_inches='tight')
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


def train_and_evaluate_new_format(args):
    """Main training and evaluation function for new dataset format."""
    # Set up random seeds for reproducibility
    set_random_seeds(args.seed)

    # Set up device
    device = torch.device(
        "cuda" if torch.cuda.is_available() and not args.no_cuda else "cpu"
    )

    # Load data from new dataset structure
    print(f"Loading dataset ID: {args.dataset_id}")
    splits, label_mappings = load_data_from_dataset_folder(args.dataset_id, args.data_dir)
    
    # Extract data for each split
    train_texts = splits['train']['texts']
    train_labels = splits['train']['labels']
    val_texts = splits['val']['texts']
    val_labels = splits['val']['labels']
    test_texts = splits['test']['texts']
    test_labels = splits['test']['labels']

    # Get number of classes and class names
    num_labels = label_mappings['num_classes']
    class_names = [label_mappings['id_to_label'][str(i)] for i in range(num_labels)]
    
    print(f"Dataset Info:")
    print(f"  Classes: {num_labels}")
    print(f"  Class names: {class_names}")
    print(f"  Train samples: {len(train_texts)}")
    print(f"  Val samples: {len(val_texts)}")
    print(f"  Test samples: {len(test_texts)}")

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

    # Create output directory with dataset ID
    output_dir = os.path.join(args.output_dir, f"dataset_{args.dataset_id}")
    os.makedirs(output_dir, exist_ok=True)

    # Set up MLflow
    mlflow.set_tracking_uri(args.mlflow_tracking_uri)
    experiment_name = f"text_classification_{args.model_type}_dataset_{args.dataset_id}"
    mlflow.set_experiment(experiment_name)

    # Start MLflow run
    with mlflow.start_run(
        run_name=f"{args.model_type}_dataset_{args.dataset_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ):
        # Log parameters
        mlflow.log_params(
            {
                "dataset_id": args.dataset_id,
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
                "class_names": class_names,
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
            print(f"\nEpoch {epoch + 1}/{args.num_epochs}")
            
            train_loss = train_epoch(
                model, train_dataloader, optimizer, scheduler, device
            )
            
            print(f"Train Loss: {train_loss:.4f}")
            mlflow.log_metric("train_loss", train_loss, step=epoch)

            # Evaluate on validation set
            val_preds, val_labels, val_probs = evaluate(
                model, val_dataloader, device, num_labels
            )

            val_metrics, _ = compute_metrics(val_preds, val_labels, val_probs)
            
            print(f"Val F1: {val_metrics['f1']:.4f}, Val Acc: {val_metrics['accuracy']:.4f}")

            for metric_name, metric_value in val_metrics.items():
                mlflow.log_metric(f"val_{metric_name}", metric_value, step=epoch)

            # Save best model
            if val_metrics["f1"] > best_val_f1:
                best_val_f1 = val_metrics["f1"]
                best_epoch = epoch

                # Save the model
                model_dir = os.path.join(output_dir, f"{args.model_type}_epoch_{epoch}")
                os.makedirs(model_dir, exist_ok=True)
                model.save_pretrained(model_dir)
                tokenizer.save_pretrained(model_dir)
                
                # Save label mappings with the model
                mappings_file = os.path.join(model_dir, "label_mappings.json")
                with open(mappings_file, 'w', encoding='utf-8') as f:
                    json.dump(label_mappings, f, ensure_ascii=False, indent=2)

                print(f"New best model saved at epoch {epoch + 1}")

                # Log the model
                mlflow.pytorch.log_model(
                    model,
                    f"{args.model_type}_best_model",
                    registered_model_name=f"{args.model_type}_classifier_dataset_{args.dataset_id}",
                )

        training_time = time.time() - start_time
        mlflow.log_metric("training_time_seconds", training_time)
        print(f"\nTraining completed in {training_time:.2f} seconds")

        # Load the best model for final evaluation
        best_model_path = os.path.join(output_dir, f"{args.model_type}_epoch_{best_epoch}")
        if os.path.exists(best_model_path):
            model = AutoModelForSequenceClassification.from_pretrained(best_model_path)
            model.to(device)

        # Evaluate on test set
        print("\nEvaluating on test set...")
        test_preds, test_labels, test_probs = evaluate(
            model, test_dataloader, device, num_labels
        )

        test_metrics, test_cm = compute_metrics(test_preds, test_labels, test_probs)

        print("\nTest Results:")
        for metric_name, metric_value in test_metrics.items():
            if not metric_name.startswith('class_'):  # Only show overall metrics
                print(f"  {metric_name}: {metric_value:.4f}")
            mlflow.log_metric(f"test_{metric_name}", metric_value)

        # Log confusion matrix with class names
        log_confusion_matrix_with_names(test_cm, class_names)

        # Measure inference time
        inference_time = measure_inference_time(model, test_dataloader, device)
        mlflow.log_metric("avg_inference_time_seconds", inference_time)
        print(f"Average inference time: {inference_time:.6f} seconds")

        # Save comprehensive metrics to a JSON file
        metrics_path = os.path.join(output_dir, f"{args.model_type}_metrics.json")
        output_metrics = {
            "dataset_id": args.dataset_id,
            "model_type": args.model_type,
            "model_name": model_name,
            "num_classes": num_labels,
            "class_names": class_names,
            "training_time_seconds": training_time,
            "avg_inference_time_seconds": inference_time,
            "test_metrics": test_metrics,
            "best_epoch": best_epoch + 1,
            "best_val_f1": best_val_f1,
            "label_mappings": label_mappings,
            "training_params": {
                "num_epochs": args.num_epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "max_seq_length": args.max_seq_length,
                "seed": args.seed
            }
        }

        with open(metrics_path, "w", encoding='utf-8') as f:
            json.dump(output_metrics, f, indent=2, ensure_ascii=False)

        # Log the metrics file
        mlflow.log_artifact(metrics_path)
        
        print(f"\nMetrics saved to: {metrics_path}")
        print(f"Best model saved to: {best_model_path}")

        return output_metrics


def train_and_evaluate(args):
    """Main training and evaluation function for legacy format."""
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

        return output_metrics


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
    
    # New dataset structure parameters
    parser.add_argument(
        "--dataset_id",
        type=str,
        help="Dataset ID for new format (e.g., '3'). If provided, uses new dataset structure.",
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        default="data/processed",
        help="Path to the directory containing the processed datasets",
    )
    
    # Legacy parameter for backward compatibility
    parser.add_argument(
        "--legacy_data_dir",
        type=str,
        help="Path to legacy data directory (for old format)",
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

    # Choose training function based on dataset format
    if args.dataset_id:
        # Use new dataset structure
        print(f"Using new dataset structure with dataset ID: {args.dataset_id}")
        train_and_evaluate_new_format(args)
    elif args.legacy_data_dir:
        # Use legacy format
        print("Using legacy dataset structure")
        args.data_dir = args.legacy_data_dir  # Set for legacy function
        train_and_evaluate(args)
    else:
        raise ValueError("Either --dataset_id (for new format) or --legacy_data_dir (for old format) must be provided")


if __name__ == "__main__":
    main()