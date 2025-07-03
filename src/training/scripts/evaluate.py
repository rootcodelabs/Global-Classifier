import os
import sys
import argparse
import json
import time
import torch
import numpy as np
from loguru import logger
import pandas as pd
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from torch.utils.data import DataLoader
import mlflow
import psutil
import matplotlib.pyplot as plt
import seaborn as sns

logger.remove()
# add stout handler
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


# Import from our utils script
from utils import (
    set_random_seeds,
    compute_metrics,
    measure_inference_speed,
    measure_model_size,
)

# Import custom dataset class from train.py
from train import TextClassificationDataset


def load_model_and_tokenizer(model_path, device):
    """
    Load a model and tokenizer from the specified path.

    Args:
        model_path (str): Path to the saved model
        device (torch.device): Device to load the model onto

    Returns:
        tuple: (model, tokenizer)
    """
    logger.info(f"Loading model from {model_path}")
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    model.to(device)
    return model, tokenizer


def load_test_data(data_path, tokenizer, max_seq_length=128):
    """
    Load and prepare test data.
    """
    logger.info(f"Loading test data from {data_path}")

    if data_path.endswith(".csv"):
        df = pd.read_csv(data_path)
    elif data_path.endswith(".json"):
        df = pd.read_json(data_path, lines=True)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")

    text_col = next(
        (col for col in ["text", "content", "sentence"] if col in df.columns), None
    )
    label_col = next(
        (col for col in ["label", "class", "target"] if col in df.columns), None
    )

    if text_col is None or label_col is None:
        raise ValueError("Could not identify text and label columns in the data")

    texts = df[text_col].values
    labels = df[label_col].values

    # Create dataset and dataloader
    dataset = TextClassificationDataset(texts, labels, tokenizer, max_seq_length)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=False, num_workers=4)

    return dataloader, texts, labels


def evaluate_model(model, dataloader, device):
    """
    Evaluate the model on the test data.
    """
    logger.info("Evaluating model accuracy...")
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
            probs = torch.nn.functional.softmax(logits, dim=1)
            preds = torch.argmax(logits, dim=1)

            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    return np.array(all_preds), np.array(all_labels), np.array(all_probs)


def measure_inference_performance(
    model, dataloader, device, num_runs=100, batch_sizes=None
):
    """
    Measure inference performance metrics.
    """
    logger.info("Measuring inference performance...")
    performance_metrics = {}

    # Get a sample batch
    sample_batch = next(iter(dataloader))

    # Measure inference time for a single batch
    inference_time = measure_inference_speed(
        model, sample_batch, device, num_runs=num_runs, warm_up=10
    )

    performance_metrics["avg_inference_time_seconds"] = inference_time
    performance_metrics["avg_inference_time_ms"] = inference_time * 1000
    performance_metrics["samples_per_second"] = (
        sample_batch["input_ids"].shape[0] / inference_time
    )

    model_size_mb = measure_model_size(model)
    performance_metrics["model_size_mb"] = model_size_mb

    memory_before = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)  # MB

    with torch.no_grad():
        _ = model(
            input_ids=sample_batch["input_ids"].to(device),
            attention_mask=sample_batch["attention_mask"].to(device),
        )

    memory_after = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)  # MB
    performance_metrics["memory_usage_mb"] = memory_after - memory_before

    if batch_sizes and device == torch.device("cuda"):
        batch_time_results = {}
        for batch_size in batch_sizes:
            batch = {
                "input_ids": sample_batch["input_ids"][:1].repeat(batch_size, 1),
                "attention_mask": sample_batch["attention_mask"][:1].repeat(
                    batch_size, 1
                ),
            }

            # Measure time and average over 10 runs
            start_time = time.time()
            with torch.no_grad():
                for _ in range(10):
                    _ = model(
                        input_ids=batch["input_ids"].to(device),
                        attention_mask=batch["attention_mask"].to(device),
                    )
            end_time = time.time()

            batch_time = (end_time - start_time) / 10
            batch_time_results[batch_size] = batch_time

        performance_metrics["batch_size_benchmarks"] = batch_time_results

    return performance_metrics


def log_evaluation_results(
    accuracy_metrics, performance_metrics, model_name, output_dir, run_id=None
):
    """
    Log evaluation results to files and MLflow.
    """
    os.makedirs(output_dir, exist_ok=True)

    all_metrics = {
        "model_name": model_name,
        "accuracy_metrics": accuracy_metrics,
        "performance_metrics": performance_metrics,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    metrics_path = os.path.join(output_dir, f"{model_name}_evaluation.json")
    with open(metrics_path, "w") as f:

        def convert_for_json(obj):
            if isinstance(
                obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64)
            ):
                return int(obj)
            elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.ndarray,)):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_for_json(i) for i in obj]
            else:
                return obj

        json.dump(convert_for_json(all_metrics), f, indent=2)

    if run_id:
        try:
            mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "mlruns"))
            with mlflow.start_run(run_id=run_id):
                # Log accuracy metrics
                for k, v in accuracy_metrics.items():
                    if k != "confusion_matrix" and not isinstance(
                        v, (dict, list, np.ndarray)
                    ):
                        mlflow.log_metric(f"test_{k}", v)

                # Log performance metrics
                for k, v in performance_metrics.items():
                    if not isinstance(v, (dict, list, np.ndarray)):
                        mlflow.log_metric(k, v)

                # Log the full results file
                mlflow.log_artifact(metrics_path)
        except Exception as e:
            logger.warning(f"Warning: Failed to log to MLflow: {str(e)}")

    logger.info(f"Evaluation results saved to {metrics_path}")


def create_evaluation_plots(
    predictions, true_labels, probabilities, model_name, output_dir
):
    """
    Create evaluation plots and save them.
    """
    os.makedirs(output_dir, exist_ok=True)

    cm = np.zeros((len(np.unique(true_labels)), len(np.unique(true_labels))), dtype=int)
    for i, j in zip(true_labels, predictions):
        cm[i][j] += 1

    plt.figure(figsize=(10, 8))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=[f"Class {i}" for i in range(cm.shape[0])],
        yticklabels=[f"Class {i}" for i in range(cm.shape[0])],
    )
    plt.xlabel("Predicted")
    plt.ylabel("True")
    plt.title(f"{model_name} Confusion Matrix")
    plt.tight_layout()

    cm_path = os.path.join(output_dir, f"{model_name}_confusion_matrix.png")
    plt.savefig(cm_path)
    plt.close()

    # For binary classification, plot ROC curve
    if probabilities.shape[1] == 2:
        from sklearn.metrics import roc_curve, auc

        fpr, tpr, _ = roc_curve(true_labels, probabilities[:, 1])
        roc_auc = auc(fpr, tpr)

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, lw=2, label=f"ROC curve (area = {roc_auc:.2f})")
        plt.plot([0, 1], [0, 1], "k--", lw=2)
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title(f"{model_name} ROC Curve")
        plt.legend(loc="lower right")

        roc_path = os.path.join(output_dir, f"{model_name}_roc_curve.png")
        plt.savefig(roc_path)
        plt.close()

        # Precision-Recall curve
        from sklearn.metrics import precision_recall_curve, average_precision_score

        precision, recall, _ = precision_recall_curve(true_labels, probabilities[:, 1])
        avg_precision = average_precision_score(true_labels, probabilities[:, 1])

        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, lw=2, label=f"PR curve (AP = {avg_precision:.2f})")
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.title(f"{model_name} Precision-Recall Curve")
        plt.legend(loc="lower left")

        pr_path = os.path.join(output_dir, f"{model_name}_pr_curve.png")
        plt.savefig(pr_path)
        plt.close()

    try:
        mlflow.log_artifact(cm_path)
        if probabilities.shape[1] == 2:
            mlflow.log_artifact(roc_path)
            mlflow.log_artifact(pr_path)
    except:
        logger.warning("Warning: Failed to log plots to MLflow")
        pass


def plot_performance_comparison(model_names, performance_metrics_list, output_dir):
    """
    Create performance comparison plots across models.

    """
    os.makedirs(output_dir, exist_ok=True)

    metrics_to_plot = ["avg_inference_time_ms", "samples_per_second", "model_size_mb"]

    for metric in metrics_to_plot:
        values = [metrics.get(metric, 0) for metrics in performance_metrics_list]

        plt.figure(figsize=(10, 6))
        bars = plt.bar(model_names, values)
        plt.title(f"Comparison of {metric}")
        plt.ylabel(metric.replace("_", " ").title())
        plt.xlabel("Model")

        for bar, value in zip(bars, values):
            if metric == "avg_inference_time_ms":
                label = f"{value:.2f} ms"
            elif metric == "samples_per_second":
                label = f"{value:.1f}"
            else:
                label = f"{value:.1f} MB"

            plt.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.1,
                label,
                ha="center",
                va="bottom",
            )

        plt.xticks(rotation=45)
        plt.tight_layout()

        plot_path = os.path.join(output_dir, f"compare_{metric}.png")
        plt.savefig(plot_path)
        plt.close()

        try:
            mlflow.log_artifact(plot_path)
        except:
            logger.warning("Warning: Failed to log comparison plots to MLflow")
            pass


def evaluate_and_compare_models(model_paths, model_names, test_data_path, output_dir):
    """
    Evaluate and compare multiple models on the same test data.

    """
    os.makedirs(output_dir, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    all_accuracy_metrics = []
    all_performance_metrics = []

    for model_path, model_name in zip(model_paths, model_names):
        logger.info(f"\nEvaluating model: {model_name}")

        # Load model and tokenizer
        model, tokenizer = load_model_and_tokenizer(model_path, device)

        # Load test data
        dataloader, _, labels = load_test_data(test_data_path, tokenizer)

        # Determine number of classes
        num_labels = len(np.unique(labels))
        logger.info(f"Detected {num_labels} classes")

        # Evaluate model accuracy
        predictions, true_labels, probabilities = evaluate_model(
            model, dataloader, device
        )

        accuracy_metrics, _ = compute_metrics(true_labels, predictions, probabilities)
        all_accuracy_metrics.append(accuracy_metrics)

        model_output_dir = os.path.join(output_dir, model_name)
        os.makedirs(model_output_dir, exist_ok=True)

        create_evaluation_plots(
            predictions, true_labels, probabilities, model_name, model_output_dir
        )

        # Measure inference performance
        batch_sizes = (
            [1, 2, 4, 8, 16, 32, 64] if device == torch.device("cuda") else None
        )

        performance_metrics = measure_inference_performance(
            model, dataloader, device, batch_sizes=batch_sizes
        )
        all_performance_metrics.append(performance_metrics)

        # Print results
        logger.info(f"\nAccuracy Metrics for {model_name}:")
        for k, v in accuracy_metrics.items():
            if k != "confusion_matrix":
                logger.info(f"  {k}: {v}")

        logger.info(f"\nPerformance Metrics for {model_name}:")
        for k, v in performance_metrics.items():
            if not isinstance(v, dict):
                print(f"  {k}: {v}")

        # Log to files
        log_evaluation_results(
            accuracy_metrics, performance_metrics, model_name, model_output_dir
        )

    plot_performance_comparison(model_names, all_performance_metrics, output_dir)

    comparison_data = []
    for i, (model_name, acc_metrics, perf_metrics) in enumerate(
        zip(model_names, all_accuracy_metrics, all_performance_metrics)
    ):
        model_data = {
            "model_name": model_name,
            "accuracy": acc_metrics.get("accuracy", 0),
            "precision": acc_metrics.get("precision", 0),
            "recall": acc_metrics.get("recall", 0),
            "f1": acc_metrics.get("f1", 0),
            "avg_inference_time_ms": perf_metrics.get("avg_inference_time_ms", 0),
            "samples_per_second": perf_metrics.get("samples_per_second", 0),
            "model_size_mb": perf_metrics.get("model_size_mb", 0),
        }
        comparison_data.append(model_data)

    comparison_df = pd.DataFrame(comparison_data)

    # Save comparison table
    comparison_path = os.path.join(output_dir, "model_comparison.csv")
    comparison_df.to_csv(comparison_path, index=False)

    # Create summary table for markdown
    markdown_table = "# Model Comparison\n\n"
    markdown_table += "| Model | Accuracy | F1 Score | Precision | Recall | Inference Time | Samples/sec | Size (MB) |\n"
    markdown_table += "|-------|----------|----------|-----------|--------|---------------|-------------|----------|\n"

    for _, row in comparison_df.iterrows():
        markdown_table += f"| {row['model_name']} | {row['accuracy']:.4f} | {row['f1']:.4f} | {row['precision']:.4f} | {row['recall']:.4f} | {row['avg_inference_time_ms']:.2f} ms | {row['samples_per_second']:.1f} | {row['model_size_mb']:.1f} |\n"

    markdown_path = os.path.join(output_dir, "model_comparison.md")
    with open(markdown_path, "w") as f:
        f.write(markdown_table)

    logger.info(f"\nComparison results saved to {output_dir}")

    # Log to MLflow if active
    try:
        mlflow.log_artifact(comparison_path)
        mlflow.log_artifact(markdown_path)
    except:
        # MLflow might not be active
        logger.warning("Warning: Failed to log comparison results to MLflow")
        pass

    return comparison_df


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate transformer-based text classifiers"
    )

    # Single model evaluation
    parser.add_argument("--model_path", type=str, help="Path to the model directory")
    parser.add_argument("--model_name", type=str, help="Name of the model")
    parser.add_argument("--test_data", type=str, help="Path to the test data")
    parser.add_argument(
        "--output_dir",
        type=str,
        default="evaluation_results",
        help="Directory to save results",
    )
    parser.add_argument(
        "--mlflow_run_id", type=str, help="MLflow run ID to log results to"
    )

    # Multiple model comparison
    parser.add_argument(
        "--compare", action="store_true", help="Compare multiple models"
    )
    parser.add_argument(
        "--model_paths",
        type=str,
        nargs="+",
        help="Paths to model directories for comparison",
    )
    parser.add_argument(
        "--model_names", type=str, nargs="+", help="Names of models for comparison"
    )

    # Performance evaluation options
    parser.add_argument(
        "--num_runs",
        type=int,
        default=100,
        help="Number of inference runs to average over",
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    # Set random seeds
    set_random_seeds(args.seed)

    if args.compare:
        # Validate arguments for comparison
        if (
            not args.model_paths
            or not args.model_names
            or len(args.model_paths) != len(args.model_names)
        ):
            parser.error(
                "For comparison, --model_paths and --model_names must be provided with equal length"
            )

        # Evaluate and compare models
        evaluate_and_compare_models(
            args.model_paths, args.model_names, args.test_data, args.output_dir
        )
    else:
        # Validate arguments for single model evaluation
        if not args.model_path or not args.model_name or not args.test_data:
            parser.error(
                "--model_path, --model_name, and --test_data are required for single model evaluation"
            )

        # Set up device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Load model and tokenizer
        model, tokenizer = load_model_and_tokenizer(args.model_path, device)

        # Load test data
        dataloader, _, labels = load_test_data(args.test_data, tokenizer)

        # Determine number of classes
        num_labels = len(np.unique(labels))

        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)

        # Evaluate model accuracy
        predictions, true_labels, probabilities = evaluate_model(
            model, dataloader, device
        )

        # Compute accuracy metrics
        accuracy_metrics, _ = compute_metrics(true_labels, predictions, probabilities)

        # Create evaluation plots
        create_evaluation_plots(
            predictions, true_labels, probabilities, args.model_name, args.output_dir
        )

        # Measure inference performance
        performance_metrics = measure_inference_performance(
            model, dataloader, device, num_runs=args.num_runs
        )

        # Print results
        logger.info("\nAccuracy Metrics:")
        for k, v in accuracy_metrics.items():
            if k != "confusion_matrix":
                print(f"  {k}: {v}")

        logger.info("\nPerformance Metrics:")
        for k, v in performance_metrics.items():
            if not isinstance(v, dict):
                print(f"  {k}: {v}")

        # Log to files and MLflow
        log_evaluation_results(
            accuracy_metrics,
            performance_metrics,
            args.model_name,
            args.output_dir,
            args.mlflow_run_id,
        )


if __name__ == "__main__":
    main()
