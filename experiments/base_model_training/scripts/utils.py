import os
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    roc_curve,
    precision_recall_curve,
    auc,
    roc_auc_score,
    average_precision_score,
)
import torch
from transformers import set_seed
import mlflow
import json
import time
from datetime import datetime


def set_random_seeds(seed_val=42):
    """
    Set random seeds for reproducibility across Python, NumPy and PyTorch.

    Args:
        seed_val (int): The seed value to use
    """
    random.seed(seed_val)
    np.random.seed(seed_val)
    torch.manual_seed(seed_val)
    torch.cuda.manual_seed_all(seed_val)
    set_seed(seed_val)
    # Set deterministic behavior for reproducibility
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def preprocess_data(data_path, text_col="text", label_col="label", save_path=None):
    """
    Preprocess the data from a CSV or JSON file.

    Args:
        data_path (str): Path to the data file
        text_col (str): Name of the column containing the text
        label_col (str): Name of the column containing the labels
        save_path (str, optional): Path to save the preprocessed data

    Returns:
        pd.DataFrame: Preprocessed dataframe
    """
    # Load the data
    if data_path.endswith(".csv"):
        df = pd.read_csv(data_path)
    elif data_path.endswith(".json"):
        df = pd.read_json(data_path, lines=True)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")

    # Verify columns exist
    if text_col not in df.columns:
        raise ValueError(f"Text column '{text_col}' not found in data")
    if label_col not in df.columns:
        raise ValueError(f"Label column '{label_col}' not found in data")

    # Basic preprocessing
    df = df.dropna(subset=[text_col, label_col])

    # Ensure labels are numeric
    if not pd.api.types.is_numeric_dtype(df[label_col]):
        # If labels are strings, convert to integers
        label_map = {label: i for i, label in enumerate(df[label_col].unique())}
        df[label_col] = df[label_col].map(label_map)

        # Save the label mapping for reference
        if save_path:
            label_map_path = os.path.join(os.path.dirname(save_path), "label_map.json")
            with open(label_map_path, "w") as f:
                json.dump(label_map, f, indent=2)

    # Save preprocessed data if a path is provided
    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        if save_path.endswith(".csv"):
            df.to_csv(save_path, index=False)
        elif save_path.endswith(".json"):
            df.to_json(save_path, orient="records", lines=True)

    return df


def split_data(
    df,
    text_col="text",
    label_col="label",
    test_size=0.2,
    val_size=0.1,
    stratify=True,
    random_state=42,
    save_dir=None,
):
    """
    Split the data into train, validation, and test sets.
    """
    actual_val_size = val_size / (1 - test_size)

    stratify_col = df[label_col] if stratify else None
    train_val_df, test_df = train_test_split(
        df, test_size=test_size, random_state=random_state, stratify=stratify_col
    )

    stratify_col = train_val_df[label_col] if stratify else None
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=actual_val_size,
        random_state=random_state,
        stratify=stratify_col,
    )

    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        train_df.to_csv(os.path.join(save_dir, "train.csv"), index=False)
        val_df.to_csv(os.path.join(save_dir, "val.csv"), index=False)
        test_df.to_csv(os.path.join(save_dir, "test.csv"), index=False)

        split_info = {
            "total_samples": len(df),
            "train_samples": len(train_df),
            "val_samples": len(val_df),
            "test_samples": len(test_df),
            "test_size": test_size,
            "val_size": val_size,
            "stratify": stratify,
            "random_state": random_state,
            "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        with open(os.path.join(save_dir, "split_info.json"), "w") as f:
            json.dump(split_info, f, indent=2)

    return train_df, val_df, test_df


def compute_metrics(y_true, y_pred, y_proba=None, average="weighted"):
    """
    Compute classification metrics.

    """
    metrics = {}

    # Basic classification metrics
    metrics["accuracy"] = accuracy_score(y_true, y_pred)

    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average=average
    )

    metrics["precision"] = precision
    metrics["recall"] = recall
    metrics["f1"] = f1

    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    metrics["confusion_matrix"] = cm

    # Calculate per-class metrics
    class_precision, class_recall, class_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average=None
    )

    # Add class metrics
    num_classes = len(np.unique(y_true))
    for i in range(num_classes):
        metrics[f"class_{i}_precision"] = class_precision[i]
        metrics[f"class_{i}_recall"] = class_recall[i]
        metrics[f"class_{i}_f1"] = class_f1[i]

    # ROC and PR curve metrics if probabilities are provided
    if y_proba is not None:
        # For binary classification
        if num_classes == 2 and y_proba.shape[1] == 2:
            fpr, tpr, _ = roc_curve(y_true, y_proba[:, 1])
            metrics["roc_auc"] = auc(fpr, tpr)

            # Find the FPR at 95% TPR
            if any(tpr >= 0.95):
                idx_95 = next(i for i, x in enumerate(tpr) if x >= 0.95)
                metrics["fpr@95tpr"] = fpr[idx_95]
            else:
                metrics["fpr@95tpr"] = float("nan")

            # Precision-Recall AUC
            precision, recall, _ = precision_recall_curve(y_true, y_proba[:, 1])
            metrics["pr_auc"] = auc(recall, precision)

        # For multi-class classification
        else:
            try:
                # One-hot encode the labels
                y_true_onehot = np.zeros((len(y_true), num_classes))
                for i, val in enumerate(y_true):
                    y_true_onehot[i, val] = 1

                # Calculate ROC AUC for multi-class
                metrics["roc_auc"] = roc_auc_score(
                    y_true_onehot, y_proba, average=average, multi_class="ovr"
                )

                # Calculate average precision score
                metrics["pr_auc"] = average_precision_score(
                    y_true_onehot, y_proba, average=average
                )
            except Exception as e:
                print(f"Warning: Could not compute ROC/PR metrics: {str(e)}")

    return metrics


def plot_confusion_matrix(
    cm,
    class_names=None,
    normalize=False,
    title="Confusion Matrix",
    save_path=None,
    figsize=(10, 8),
    cmap="Blues",
):
    """
    Plot a confusion matrix.

    """
    if normalize:
        cm = cm.astype("float") / cm.sum(axis=1)[:, np.newaxis]
        fmt = ".2f"
    else:
        fmt = "d"

    if class_names is None:
        class_names = [f"Class {i}" for i in range(cm.shape[0])]

    plt.figure(figsize=figsize)
    sns.heatmap(
        cm,
        annot=True,
        fmt=fmt,
        cmap=cmap,
        xticklabels=class_names,
        yticklabels=class_names,
    )
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.title(title)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)

    return plt.gcf()


def plot_roc_curve(fpr, tpr, roc_auc, save_path=None, figsize=(8, 6)):
    """
    Plot a ROC curve
    """
    plt.figure(figsize=figsize)
    plt.plot(fpr, tpr, lw=2, label=f"ROC curve (area = {roc_auc:.2f})")
    plt.plot([0, 1], [0, 1], "k--", lw=2)
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("Receiver Operating Characteristic (ROC) Curve")
    plt.legend(loc="lower right")

    if save_path:
        plt.savefig(save_path)

    return plt.gcf()


def plot_precision_recall_curve(
    precision, recall, average_precision, save_path=None, figsize=(8, 6)
):
    """
    Plot a precision-recall curve
    """
    plt.figure(figsize=figsize)
    plt.plot(recall, precision, lw=2, label=f"PR curve (AP = {average_precision:.2f})")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve")
    plt.legend(loc="lower left")

    if save_path:
        plt.savefig(save_path)

    return plt.gcf()


def log_plots_to_mlflow(metrics, class_names=None, output_dir=None):
    """
    Create and log plots to MLflow based on computed metrics
    """
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Plot confusion matrix
    if "confusion_matrix" in metrics:
        cm = metrics["confusion_matrix"]
        cm_path = (
            os.path.join(output_dir, "confusion_matrix.png") if output_dir else None
        )
        plot_confusion_matrix(cm, class_names=class_names, save_path=cm_path)

        if cm_path:
            mlflow.log_artifact(cm_path)

    # Plot ROC curve for binary classification
    if "roc_curve" in metrics:
        fpr = metrics["roc_curve"]["fpr"]
        tpr = metrics["roc_curve"]["tpr"]
        roc_auc = metrics["roc_auc"]

        roc_path = os.path.join(output_dir, "roc_curve.png") if output_dir else None
        plot_roc_curve(fpr, tpr, roc_auc, save_path=roc_path)

        if roc_path:
            mlflow.log_artifact(roc_path)

    # Plot precision-recall curve
    if "pr_curve" in metrics:
        precision = metrics["pr_curve"]["precision"]
        recall = metrics["pr_curve"]["recall"]
        avg_precision = metrics["pr_auc"]

        pr_path = os.path.join(output_dir, "pr_curve.png") if output_dir else None
        plot_precision_recall_curve(precision, recall, avg_precision, save_path=pr_path)

        if pr_path:
            mlflow.log_artifact(pr_path)


def measure_model_size(model):
    """
    Measure the size of a PyTorch model in MB.

    Args:
        model (torch.nn.Module): The model to measure

    Returns:
        float: Size of the model in MB
    """
    model_size = 0
    for param in model.parameters():
        model_size += param.nelement() * param.element_size()

    # Convert to MB
    model_size_mb = model_size / (1024 * 1024)
    return model_size_mb


def measure_inference_speed(model, sample_input, device, num_runs=100, warm_up=10):
    """
    Measure the inference speed of a model
    """
    model.eval()

    # Move inputs to the appropriate device
    input_ids = sample_input["input_ids"].to(device)
    attention_mask = sample_input["attention_mask"].to(device)

    # Warm-up runs
    with torch.no_grad():
        for _ in range(warm_up):
            _ = model(input_ids=input_ids, attention_mask=attention_mask)

    # Measure inference time
    start_time = time.time()
    with torch.no_grad():
        for _ in range(num_runs):
            _ = model(input_ids=input_ids, attention_mask=attention_mask)
    end_time = time.time()

    avg_time = (end_time - start_time) / num_runs
    return avg_time


def log_model_metadata(model, tokenizer, config=None, output_dir=None):
    """
    Log model metadata to a file and MLflow
    """
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # Collect model metadata
    model_info = {
        "model_type": model.__class__.__name__,
        "model_parameters": sum(p.numel() for p in model.parameters()),
        "trainable_parameters": sum(
            p.numel() for p in model.parameters() if p.requires_grad
        ),
        "tokenizer_type": tokenizer.__class__.__name__,
        "vocab_size": len(tokenizer),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # Add any additional config
    if config:
        model_info.update(config)

    # Save metadata to file
    if output_dir:
        metadata_path = os.path.join(output_dir, "model_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(model_info, f, indent=2)

        # Log to MLflow
        mlflow.log_dict(model_info, "model_metadata.json")

    return model_info


def analyze_dataset(data_path, text_col="text", label_col="label", output_dir=None):
    """
    Analyze a dataset and generate statistics.

    Args:
        data_path (str): Path to the dataset
        text_col (str): Name of the column containing the text
        label_col (str): Name of the column containing the labels
        output_dir (str, optional): Directory to save the analysis results

    Returns:
        dict: Dataset statistics
    """
    # Load the data
    if data_path.endswith(".csv"):
        df = pd.read_csv(data_path)
    elif data_path.endswith(".json"):
        df = pd.read_json(data_path, lines=True)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")

    # Basic dataset statistics
    stats = {
        "num_samples": len(df),
        "num_classes": len(df[label_col].unique()),
        "class_distribution": df[label_col].value_counts().to_dict(),
        "avg_text_length": df[text_col].str.len().mean(),
        "min_text_length": df[text_col].str.len().min(),
        "max_text_length": df[text_col].str.len().max(),
        "median_text_length": df[text_col].str.len().median(),
    }

    # Plot class distribution
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

        # Class distribution plot
        plt.figure(figsize=(10, 6))
        sns.countplot(
            y=df[label_col].astype(str),
            order=df[label_col].value_counts().index.astype(str),
        )
        plt.title("Class Distribution")
        plt.xlabel("Count")
        plt.ylabel("Class")
        plt.tight_layout()

        class_dist_path = os.path.join(output_dir, "class_distribution.png")
        plt.savefig(class_dist_path)
        plt.close()

        # Text length distribution
        plt.figure(figsize=(10, 6))
        sns.histplot(df[text_col].str.len(), bins=50)
        plt.title("Text Length Distribution")
        plt.xlabel("Text Length (characters)")
        plt.ylabel("Count")
        plt.tight_layout()

        text_len_path = os.path.join(output_dir, "text_length_distribution.png")
        plt.savefig(text_len_path)
        plt.close()

        # Save statistics to a JSON file
        stats_path = os.path.join(output_dir, "dataset_stats.json")
        with open(stats_path, "w") as f:
            # Convert any non-serializable values (like numpy.int64) to standard Python types
            stats_serializable = {
                k: v if isinstance(v, (str, int, float, bool, list, dict)) else int(v)
                for k, v in stats.items()
            }
            json.dump(stats_serializable, f, indent=2)

        # Log to MLflow if active
        try:
            mlflow.log_artifact(class_dist_path)
            mlflow.log_artifact(text_len_path)
            mlflow.log_dict(stats, "dataset_stats.json")
        except Exception as e:
            print(f"Warning: Could not log dataset analysis to MLflow: {str(e)}")
            # MLflow might nt be active

    return stats


def format_time(seconds):
    """
    Format time in seconds to a human-readable string.

    Args:
        seconds (float): Time in seconds

    Returns:
        str: Formatted time string
    """
    if seconds < 1e-3:  # Less than a millisecond
        return f"{seconds * 1e6:.2f} µs"
    elif seconds < 1:  # Less than a second
        return f"{seconds * 1e3:.2f} ms"
    elif seconds < 60:  # Less than a minute
        return f"{seconds:.2f} s"
    elif seconds < 3600:  # Less than an hour
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.2f}s"
    else:  # Hours or more
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}h {minutes}m {secs:.2f}s"


def compare_models(metrics_list, model_names=None, output_dir=None):
    """
    Compare multiple models based on their metrics
    """
    if model_names is None:
        model_names = [f"Model {i + 1}" for i in range(len(metrics_list))]

    if len(model_names) != len(metrics_list):
        raise ValueError(
            "Number of model names must match number of metric dictionaries"
        )

    # Extract common metrics for comparison
    common_metrics = [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "pr_auc",
        "fpr@95tpr",
        "avg_inference_time_seconds",
        "training_time_seconds",
    ]

    # Create comparison dictionary
    comparison = {name: {} for name in model_names}

    for i, (name, metrics) in enumerate(zip(model_names, metrics_list)):
        for metric in common_metrics:
            if metric in metrics:
                comparison[name][metric] = metrics[metric]
            # Handle nested metrics
            elif "test_metrics" in metrics and metric in metrics["test_metrics"]:
                comparison[name][metric] = metrics["test_metrics"][metric]

    # Convert to DataFrame for easier comparison
    comp_df = pd.DataFrame(comparison).T

    # Format time metrics if present
    time_cols = [col for col in comp_df.columns if "time" in col]
    for col in time_cols:
        if col in comp_df.columns:
            comp_df[f"{col}_formatted"] = comp_df[col].apply(format_time)

    # Save comparison to CSV and JSON
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

        # Save as CSV
        csv_path = os.path.join(output_dir, "model_comparison.csv")
        comp_df.to_csv(csv_path)

        # Save as JSON
        json_path = os.path.join(output_dir, "model_comparison.json")
        comp_df.to_json(json_path, orient="index", indent=2)

        # Create comparison plots
        for metric in common_metrics:
            if metric in comp_df.columns:
                plt.figure(figsize=(10, 6))

                # Skip time metrics for bar plots (they're often on different scales)
                if "time" in metric:
                    continue

                # Create bar plot
                ax = sns.barplot(x=comp_df.index, y=comp_df[metric])
                plt.title(f"Comparison of {metric}")
                plt.ylabel(metric)
                plt.xlabel("Model")

                # Add value labels on top of each bar
                for i, v in enumerate(comp_df[metric]):
                    ax.text(i, v, f"{v:.4f}", ha="center", va="bottom")

                plt.xticks(rotation=45)
                plt.tight_layout()

                # Save the plot
                plot_path = os.path.join(output_dir, f"compare_{metric}.png")
                plt.savefig(plot_path)
                plt.close()

                # Log to MLflow if active
                try:
                    mlflow.log_artifact(plot_path)
                except Exception as e:
                    print(
                        f"Warning: Could not log plot {plot_path} to MLflow: {str(e)}"
                    )
                    # MLflow might not be active

        # Log to MLflow if active
        try:
            mlflow.log_artifact(csv_path)
            mlflow.log_artifact(json_path)
        except Exception as e:
            print(f"Warning: Could not log comparison files to MLflow: {str(e)}")
            # MLflow might not be active

    return comp_df
