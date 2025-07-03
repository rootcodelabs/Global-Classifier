import os
import sys
import argparse
import json
import time
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from loguru import logger
import mlflow
import psutil
import platform
import gc
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

logger.remove()
# add stout handler
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")


# Import utilities
from utils import set_random_seeds, measure_model_size


def get_system_info():
    """
    Get information about the system hardware.

    Returns:
        dict: Dictionary of system information
    """
    system_info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "torch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cpu_count": os.cpu_count(),
        "memory_total_gb": psutil.virtual_memory().total / (1024**3),
    }

    if torch.cuda.is_available():
        system_info.update(
            {
                "cuda_version": torch.version.cuda,
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_count": torch.cuda.device_count(),
                "gpu_memory_gb": torch.cuda.get_device_properties(0).total_memory
                / (1024**3),
            }
        )

    return system_info


def create_dummy_input(tokenizer, batch_size, seq_length, device):
    """
    Create a dummy input batch for benchmarking.

    Args:
        tokenizer: The tokenizer to use
        batch_size: Number of examples in the batch
        seq_length: Sequence length for each example
        device: Device to put the tensor on

    Returns:
        dict: Dictionary with input_ids and attention_mask
    """
    # Create a dummy text sequence
    text = " ".join(["word"] * (seq_length // 2))

    # Tokenize it
    sample_encoding = tokenizer(
        text,
        padding="max_length",
        truncation=True,
        max_length=seq_length,
        return_tensors="pt",
    )

    # Expand to the desired batch size
    input_ids = sample_encoding["input_ids"].repeat(batch_size, 1).to(device)
    attention_mask = sample_encoding["attention_mask"].repeat(batch_size, 1).to(device)

    return {"input_ids": input_ids, "attention_mask": attention_mask}


def benchmark_inference_time(model, inputs, num_runs=100, warm_up=10):
    """
    Benchmark the inference time for a model.

    Args:
        model: The model to benchmark
        inputs: Input tensors for the model
        num_runs: Number of runs to average over
        warm_up: Number of warm-up runs

    Returns:
        dict: Dictionary of timing statistics
    """
    model.eval()
    timings = []

    # Warm-up runs
    with torch.no_grad():
        for _ in range(warm_up):
            _ = model(**inputs)

    # Timed runs
    with torch.no_grad():
        for _ in range(num_runs):
            start_time = time.time()
            _ = model(**inputs)
            # Make sure GPU operations are completed
            if torch.cuda.is_available():
                torch.cuda.synchronize()
            end_time = time.time()
            timings.append(end_time - start_time)

    # Calculate statistics
    timings_ms = np.array(timings) * 1000

    stats = {
        "avg_time_ms": np.mean(timings_ms),
        "min_time_ms": np.min(timings_ms),
        "max_time_ms": np.max(timings_ms),
        "median_time_ms": np.median(timings_ms),
        "std_time_ms": np.std(timings_ms),
        "p90_time_ms": np.percentile(timings_ms, 90),
        "p95_time_ms": np.percentile(timings_ms, 95),
        "p99_time_ms": np.percentile(timings_ms, 99),
    }

    # Calculate throughput (samples per second)
    batch_size = inputs["input_ids"].shape[0]
    stats["samples_per_second"] = batch_size * 1000 / stats["avg_time_ms"]

    return stats


def benchmark_memory_usage(model, inputs):
    """
    Benchmark the memory usage for a model.

    Args:
        model: The model to benchmark
        inputs: Input tensors for the model

    Returns:
        dict: Dictionary of memory usage statistics
    """
    # Force garbage collection
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    # Measure memory before
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
        memory_before = torch.cuda.memory_allocated() / (1024**2)
    else:
        memory_before = psutil.Process(os.getpid()).memory_info().rss / (1024**2)

    # Run inference
    model.eval()
    with torch.no_grad():
        _ = model(**inputs)
        # Make sure GPU operations are completed
        if torch.cuda.is_available():
            torch.cuda.synchronize()

    # Measure memory after
    if torch.cuda.is_available():
        memory_peak = torch.cuda.max_memory_allocated() / (1024**2)
        memory_current = torch.cuda.memory_allocated() / (1024**2)
        memory_usage = memory_peak - memory_before
    else:
        memory_current = psutil.Process(os.getpid()).memory_info().rss / (1024**2)
        memory_usage = memory_current - memory_before
        memory_peak = memory_current

    return {
        "memory_before_mb": memory_before,
        "memory_peak_mb": memory_peak,
        "memory_current_mb": memory_current,
        "memory_usage_mb": memory_usage,
    }


def benchmark_model(
    model_path, device, batch_sizes, seq_lengths, num_runs=100, warm_up=10
):
    """
    Run comprehensive benchmarks for a model.
    """
    logger.info(f"Loading model from {model_path}...")

    # Load model and tokenizer
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    tokenizer = AutoTokenizer.from_pretrained(model_path)

    model.to(device)
    model.eval()

    # Measure model size
    model_size_mb = measure_model_size(model)
    logger.info(f"Model size: {model_size_mb:.2f} MB")

    # Run benchmarks for different batch sizes and sequence lengths
    results = {
        "model_path": model_path,
        "device": str(device),
        "model_size_mb": model_size_mb,
        "benchmarks": {},
    }

    for batch_size in batch_sizes:
        for seq_length in seq_lengths:
            logger.info(
                f"Benchmarking batch_size={batch_size}, seq_length={seq_length}..."
            )

            # Create dummy inputs
            inputs = create_dummy_input(tokenizer, batch_size, seq_length, device)

            # Benchmark timing
            timing_stats = benchmark_inference_time(
                model, inputs, num_runs=num_runs, warm_up=warm_up
            )

            # Benchmark memory
            memory_stats = benchmark_memory_usage(model, inputs)

            # Store results
            key = f"batch_{batch_size}_seq_{seq_length}"
            results["benchmarks"][key] = {
                "batch_size": batch_size,
                "seq_length": seq_length,
                "timing": timing_stats,
                "memory": memory_stats,
            }

    return results


def compare_batch_throughput(results, output_dir):
    """
    Create comparison plots for throughput vs batch size.

    Args:
        results: Dictionary of benchmark results
        output_dir: Directory to save plots
    """
    os.makedirs(output_dir, exist_ok=True)

    # Extract batch sizes and sequence lengths
    batch_sizes = sorted(
        list({result["batch_size"] for result in results["benchmarks"].values()})
    )
    seq_lengths = sorted(
        list({result["seq_length"] for result in results["benchmarks"].values()})
    )

    # Create plots for each sequence length
    for seq_length in seq_lengths:
        data = []

        for batch_size in batch_sizes:
            key = f"batch_{batch_size}_seq_{seq_length}"
            if key in results["benchmarks"]:
                throughput = results["benchmarks"][key]["timing"]["samples_per_second"]
                latency = results["benchmarks"][key]["timing"]["avg_time_ms"]
                data.append(
                    {
                        "batch_size": batch_size,
                        "throughput": throughput,
                        "latency": latency,
                    }
                )

        if not data:
            continue

        df = pd.DataFrame(data)

        # Create throughput plot
        plt.figure(figsize=(10, 6))
        plt.plot(df["batch_size"], df["throughput"], marker="o")
        plt.xlabel("Batch Size")
        plt.ylabel("Throughput (samples/second)")
        plt.title(f"Throughput vs Batch Size (Sequence Length = {seq_length})")
        plt.grid(True)
        plt.tight_layout()

        throughput_path = os.path.join(output_dir, f"throughput_seq_{seq_length}.png")
        plt.savefig(throughput_path)
        plt.close()

        # Create latency plot
        plt.figure(figsize=(10, 6))
        plt.plot(df["batch_size"], df["latency"], marker="o")
        plt.xlabel("Batch Size")
        plt.ylabel("Latency (ms)")
        plt.title(f"Latency vs Batch Size (Sequence Length = {seq_length})")
        plt.grid(True)
        plt.tight_layout()

        latency_path = os.path.join(output_dir, f"latency_seq_{seq_length}.png")
        plt.savefig(latency_path)
        plt.close()

        # Log to MLflow if active
        try:
            mlflow.log_artifact(throughput_path)
            mlflow.log_artifact(latency_path)
        except:
            # MLflow might not be active
            pass


def compare_sequence_length_impact(results, output_dir):
    """
    Create comparison plots for latency vs sequence length.

    Args:
        results: Dictionary of benchmark results
        output_dir: Directory to save plots
    """
    os.makedirs(output_dir, exist_ok=True)

    # Extract batch sizes and sequence lengths
    batch_sizes = sorted(
        list({result["batch_size"] for result in results["benchmarks"].values()})
    )
    seq_lengths = sorted(
        list({result["seq_length"] for result in results["benchmarks"].values()})
    )

    # Create plots for each batch size
    for batch_size in batch_sizes:
        data = []

        for seq_length in seq_lengths:
            key = f"batch_{batch_size}_seq_{seq_length}"
            if key in results["benchmarks"]:
                latency = results["benchmarks"][key]["timing"]["avg_time_ms"]
                data.append({"seq_length": seq_length, "latency": latency})

        if not data:
            continue

        df = pd.DataFrame(data)

        # Create latency plot
        plt.figure(figsize=(10, 6))
        plt.plot(df["seq_length"], df["latency"], marker="o")
        plt.xlabel("Sequence Length")
        plt.ylabel("Latency (ms)")
        plt.title(f"Latency vs Sequence Length (Batch Size = {batch_size})")
        plt.grid(True)
        plt.tight_layout()

        latency_path = os.path.join(output_dir, f"seq_latency_batch_{batch_size}.png")
        plt.savefig(latency_path)
        plt.close()

        # Log to MLflow if active
        try:
            mlflow.log_artifact(latency_path)
        except:
            # MLflow might not be active
            logger.warning(
                f"Warning: Failed to log latency plot for batch size {batch_size} to MLflow"
            )
            pass


def create_heatmap(results, output_dir):
    """
    Create a heatmap of latency across batch sizes and sequence lengths.

    Args:
        results: Dictionary of benchmark results
        output_dir: Directory to save plots
    """
    os.makedirs(output_dir, exist_ok=True)

    # Extract batch sizes and sequence lengths
    batch_sizes = sorted(
        list({result["batch_size"] for result in results["benchmarks"].values()})
    )
    seq_lengths = sorted(
        list({result["seq_length"] for result in results["benchmarks"].values()})
    )

    # Create data for heatmap
    latency_matrix = np.zeros((len(batch_sizes), len(seq_lengths)))
    throughput_matrix = np.zeros((len(batch_sizes), len(seq_lengths)))

    for i, batch_size in enumerate(batch_sizes):
        for j, seq_length in enumerate(seq_lengths):
            key = f"batch_{batch_size}_seq_{seq_length}"
            if key in results["benchmarks"]:
                latency_matrix[i, j] = results["benchmarks"][key]["timing"][
                    "avg_time_ms"
                ]
                throughput_matrix[i, j] = results["benchmarks"][key]["timing"][
                    "samples_per_second"
                ]

    # Create latency heatmap
    plt.figure(figsize=(12, 8))
    sns.heatmap(
        latency_matrix,
        annot=True,
        fmt=".1f",
        xticklabels=seq_lengths,
        yticklabels=batch_sizes,
        cmap="YlOrRd",
    )
    plt.xlabel("Sequence Length")
    plt.ylabel("Batch Size")
    plt.title("Inference Latency (ms)")
    plt.tight_layout()

    latency_heatmap_path = os.path.join(output_dir, "latency_heatmap.png")
    plt.savefig(latency_heatmap_path)
    plt.close()

    # Create throughput heatmap
    plt.figure(figsize=(12, 8))
    sns.heatmap(
        throughput_matrix,
        annot=True,
        fmt=".1f",
        xticklabels=seq_lengths,
        yticklabels=batch_sizes,
        cmap="viridis",
    )
    plt.xlabel("Sequence Length")
    plt.ylabel("Batch Size")
    plt.title("Throughput (samples/second)")
    plt.tight_layout()

    throughput_heatmap_path = os.path.join(output_dir, "throughput_heatmap.png")
    plt.savefig(throughput_heatmap_path)
    plt.close()

    # Log to MLflow if active
    try:
        mlflow.log_artifact(latency_heatmap_path)
        mlflow.log_artifact(throughput_heatmap_path)
    except:
        # MLflow might not be active
        logger.warning("Warning: Failed to log heatmap plots to MLflow")
        pass


def create_summary_report(results, system_info, output_dir):
    """
    Create a markdown summary report of the benchmarks.

    Args:
        results: Dictionary of benchmark results
        system_info: Dictionary of system information
        output_dir: Directory to save the report
    """
    os.makedirs(output_dir, exist_ok=True)

    model_path = results["model_path"]
    model_name = os.path.basename(model_path)

    # Create report content
    report = f"# Inference Performance Report for {model_name}\n\n"

    # System information
    report += "## System Information\n\n"
    report += "| Component | Details |\n"
    report += "|-----------|--------|\n"
    for key, value in system_info.items():
        if isinstance(value, float):
            value = f"{value:.2f}"
        report += f"| {key} | {value} |\n"

    report += "\n## Model Information\n\n"
    report += f"- Model path: {model_path}\n"
    report += f"- Model size: {results['model_size_mb']:.2f} MB\n"
    report += f"- Device: {results['device']}\n\n"

    # Create a summary table for batch size = 1
    report += "## Inference Latency (Batch Size = 1)\n\n"
    report += "| Sequence Length | Latency (ms) | Throughput (samples/sec) |\n"
    report += "|-----------------|-------------|---------------------------|\n"

    seq_lengths = sorted(
        list({result["seq_length"] for result in results["benchmarks"].values()})
    )

    for seq_length in seq_lengths:
        key = f"batch_1_seq_{seq_length}"
        if key in results["benchmarks"]:
            latency = results["benchmarks"][key]["timing"]["avg_time_ms"]
            throughput = results["benchmarks"][key]["timing"]["samples_per_second"]
            report += f"| {seq_length} | {latency:.2f} | {throughput:.2f} |\n"

    # Create a table for batch effects on typical length
    mid_seq = seq_lengths[len(seq_lengths) // 2] if seq_lengths else 128

    report += f"\n## Batch Size Impact (Sequence Length = {mid_seq})\n\n"
    report += "| Batch Size | Latency (ms) | Throughput (samples/sec) |\n"
    report += "|------------|-------------|---------------------------|\n"

    batch_sizes = sorted(
        list({result["batch_size"] for result in results["benchmarks"].values()})
    )

    for batch_size in batch_sizes:
        key = f"batch_{batch_size}_seq_{mid_seq}"
        if key in results["benchmarks"]:
            latency = results["benchmarks"][key]["timing"]["avg_time_ms"]
            throughput = results["benchmarks"][key]["timing"]["samples_per_second"]
            report += f"| {batch_size} | {latency:.2f} | {throughput:.2f} |\n"

    # Memory usage
    report += "\n## Memory Usage\n\n"
    report += "| Batch Size | Sequence Length | Memory Usage (MB) |\n"
    report += "|------------|-----------------|-------------------|\n"

    for batch_size in batch_sizes:
        for seq_length in seq_lengths:
            key = f"batch_{batch_size}_seq_{seq_length}"
            if key in results["benchmarks"]:
                memory = results["benchmarks"][key]["memory"]["memory_usage_mb"]
                report += f"| {batch_size} | {seq_length} | {memory:.2f} |\n"

    # Detailed timing statistics for a typical case
    key = f"batch_1_seq_{mid_seq}"
    if key in results["benchmarks"]:
        report += (
            "\n## Detailed Timing Statistics (Batch Size = 1, Sequence Length = "
            + str(mid_seq)
            + ")\n\n"
        )
        report += "| Metric | Value |\n"
        report += "|--------|-------|\n"

        timing = results["benchmarks"][key]["timing"]
        for k, v in timing.items():
            if k != "samples_per_second":
                report += f"| {k} | {v:.2f} ms |\n"

    # Write the report
    report_path = os.path.join(output_dir, f"{model_name}_inference_report.md")
    with open(report_path, "w") as f:
        f.write(report)

    logger.info(f"Report saved to {report_path}")

    # Log to MLflow if active
    try:
        mlflow.log_artifact(report_path)
    except:
        # MLflow might not be active
        logger.warning("Warning: Failed to log report to MLflow")
        pass


def compare_models(model_results, output_dir):
    """
    Compare multiple models in terms of inference performance.

    Args:
        model_results: List of benchmark results for different models
        output_dir: Directory to save comparison results
    """
    os.makedirs(output_dir, exist_ok=True)

    model_names = [os.path.basename(results["model_path"]) for results in model_results]

    # Extract batch sizes and sequence lengths
    batch_sizes = set()
    seq_lengths = set()

    for results in model_results:
        for result in results["benchmarks"].values():
            batch_sizes.add(result["batch_size"])
            seq_lengths.add(result["seq_length"])

    batch_sizes = sorted(list(batch_sizes))
    seq_lengths = sorted(list(seq_lengths))

    # Compare latency for batch size = 1 across different sequence lengths
    data = []

    for model_idx, results in enumerate(model_results):
        for seq_length in seq_lengths:
            key = f"batch_1_seq_{seq_length}"
            if key in results["benchmarks"]:
                latency = results["benchmarks"][key]["timing"]["avg_time_ms"]
                throughput = results["benchmarks"][key]["timing"]["samples_per_second"]

                data.append(
                    {
                        "model": model_names[model_idx],
                        "seq_length": seq_length,
                        "latency": latency,
                        "throughput": throughput,
                    }
                )

    if data:
        df = pd.DataFrame(data)

        # Plot latency comparison
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=df, x="seq_length", y="latency", hue="model", marker="o")
        plt.xlabel("Sequence Length")
        plt.ylabel("Latency (ms)")
        plt.title("Inference Latency Comparison (Batch Size = 1)")
        plt.grid(True)
        plt.tight_layout()

        latency_comp_path = os.path.join(output_dir, "model_latency_comparison.png")
        plt.savefig(latency_comp_path)
        plt.close()

        # Plot throughput comparison
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=df, x="seq_length", y="throughput", hue="model", marker="o")
        plt.xlabel("Sequence Length")
        plt.ylabel("Throughput (samples/second)")
        plt.title("Inference Throughput Comparison (Batch Size = 1)")
        plt.grid(True)
        plt.tight_layout()

        throughput_comp_path = os.path.join(
            output_dir, "model_throughput_comparison.png"
        )
        plt.savefig(throughput_comp_path)
        plt.close()

    # Compare latency for different batch sizes with a fixed sequence length
    mid_seq = seq_lengths[len(seq_lengths) // 2] if seq_lengths else 128
    data = []

    for model_idx, results in enumerate(model_results):
        for batch_size in batch_sizes:
            key = f"batch_{batch_size}_seq_{mid_seq}"
            if key in results["benchmarks"]:
                latency = results["benchmarks"][key]["timing"]["avg_time_ms"]
                throughput = results["benchmarks"][key]["timing"]["samples_per_second"]

                data.append(
                    {
                        "model": model_names[model_idx],
                        "batch_size": batch_size,
                        "latency": latency,
                        "throughput": throughput,
                    }
                )

    if data:
        df = pd.DataFrame(data)

        # Plot latency comparison for different batch sizes
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=df, x="batch_size", y="latency", hue="model", marker="o")
        plt.xlabel("Batch Size")
        plt.ylabel("Latency (ms)")
        plt.title(f"Inference Latency Comparison (Sequence Length = {mid_seq})")
        plt.grid(True)
        plt.tight_layout()

        batch_latency_path = os.path.join(output_dir, "batch_latency_comparison.png")
        plt.savefig(batch_latency_path)
        plt.close()

        # Plot throughput comparison for different batch sizes
        plt.figure(figsize=(12, 6))
        sns.lineplot(data=df, x="batch_size", y="throughput", hue="model", marker="o")
        plt.xlabel("Batch Size")
        plt.ylabel("Throughput (samples/second)")
        plt.title(f"Inference Throughput Comparison (Sequence Length = {mid_seq})")
        plt.grid(True)
        plt.tight_layout()

        batch_throughput_path = os.path.join(
            output_dir, "batch_throughput_comparison.png"
        )
        plt.savefig(batch_throughput_path)
        plt.close()

    # Create a comparison table
    comparison_table = "# Model Inference Performance Comparison\n\n"

    # Model size comparison
    comparison_table += "## Model Size\n\n"
    comparison_table += "| Model | Size (MB) |\n"
    comparison_table += "|-------|----------|\n"

    for model_idx, results in enumerate(model_results):
        comparison_table += (
            f"| {model_names[model_idx]} | {results['model_size_mb']:.2f} |\n"
        )

    # Latency comparison for batch=1, seq=128
    comparison_table += "\n## Single Sample Inference Latency (ms)\n\n"
    comparison_table += "| Model | "
    for seq_length in seq_lengths:
        comparison_table += f"Seq={seq_length} | "
    comparison_table += "\n|-------|"
    for _ in seq_lengths:
        comparison_table += "-------|"
    comparison_table += "\n"

    for model_idx, results in enumerate(model_results):
        comparison_table += f"| {model_names[model_idx]} | "
        for seq_length in seq_lengths:
            key = f"batch_1_seq_{seq_length}"
            if key in results["benchmarks"]:
                latency = results["benchmarks"][key]["timing"]["avg_time_ms"]
                comparison_table += f"{latency:.2f} | "
            else:
                comparison_table += "N/A | "
        comparison_table += "\n"

    # Throughput comparison for batch=32, seq=128
    comparison_table += "\n## Throughput (samples/second) with Batch Size = 32\n\n"
    comparison_table += "| Model | "
    for seq_length in seq_lengths:
        comparison_table += f"Seq={seq_length} | "
    comparison_table += "\n|-------|"
    for _ in seq_lengths:
        comparison_table += "-------|"
    comparison_table += "\n"

    for model_idx, results in enumerate(model_results):
        comparison_table += f"| {model_names[model_idx]} | "
        for seq_length in seq_lengths:
            key = f"batch_32_seq_{seq_length}"
            if key in results["benchmarks"]:
                throughput = results["benchmarks"][key]["timing"]["samples_per_second"]
                comparison_table += f"{throughput:.2f} | "
            else:
                comparison_table += "N/A | "
        comparison_table += "\n"

    # Write the comparison table
    comparison_path = os.path.join(output_dir, "model_comparison.md")
    with open(comparison_path, "w") as f:
        f.write(comparison_table)

    logger.info(f"Comparison saved to {comparison_path}")

    # Log to MLflow if active
    try:
        mlflow.log_artifact(latency_comp_path)
        mlflow.log_artifact(throughput_comp_path)
        mlflow.log_artifact(batch_latency_path)
        mlflow.log_artifact(batch_throughput_path)
        mlflow.log_artifact(comparison_path)
    except:
        # MLflow might not be active
        logger.warning("Warning: Failed to log comparison plots to MLflow")
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Measure inference performance for transformer models"
    )

    # Single model benchmark
    parser.add_argument("--model_path", type=str, help="Path to the model")
    parser.add_argument(
        "--output_dir",
        type=str,
        default="inference_results",
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
        "--model_paths", type=str, nargs="+", help="Paths to models for comparison"
    )

    # Benchmark parameters
    parser.add_argument(
        "--batch_sizes",
        type=int,
        nargs="+",
        default=[1, 2, 4, 8, 16, 32, 64, 128],
        help="Batch sizes to benchmark",
    )
    parser.add_argument(
        "--seq_lengths",
        type=int,
        nargs="+",
        default=[32, 64, 128, 256, 512],
        help="Sequence lengths to benchmark",
    )
    parser.add_argument(
        "--num_runs", type=int, default=100, help="Number of runs to average over"
    )
    parser.add_argument(
        "--warm_up", type=int, default=10, help="Number of warm-up runs"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--cpu_only",
        action="store_true",
        help="Force CPU inference even if CUDA is available",
    )

    args = parser.parse_args()

    # Set random seeds
    set_random_seeds(args.seed)

    # Set up device
    if args.cpu_only:
        device = torch.device("cpu")
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    logger.info(f"Using device: {device}")

    # Get system information
    system_info = get_system_info()
    logger.info("System information:")
    for key, value in system_info.items():
        logger.info(f"  {key}: {value}")

    if args.compare:
        # Validate arguments for comparison
        if not args.model_paths:
            parser.error("--model_paths must be provided for comparison")

        # Benchmark multiple models
        model_results = []

        for model_path in args.model_paths:
            logger.info(f"\nBenchmarking model: {model_path}")
            model_output_dir = os.path.join(
                args.output_dir, os.path.basename(model_path)
            )
            os.makedirs(model_output_dir, exist_ok=True)

            results = benchmark_model(
                model_path,
                device,
                args.batch_sizes,
                args.seq_lengths,
                args.num_runs,
                args.warm_up,
            )

            # Save results to file
            results_path = os.path.join(model_output_dir, "benchmark_results.json")
            with open(results_path, "w") as f:
                # Convert any non-serializable values
                def convert_for_json(obj):
                    if isinstance(
                        obj,
                        (
                            np.int_,
                            np.intc,
                            np.intp,
                            np.int8,
                            np.int16,
                            np.int32,
                            np.int64,
                        ),
                    ):
                        return int(obj)
                    elif isinstance(
                        obj, (np.float_, np.float16, np.float32, np.float64)
                    ):
                        return float(obj)
                    elif isinstance(obj, (np.ndarray,)):
                        return obj.tolist()
                    elif isinstance(obj, dict):
                        return {k: convert_for_json(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_for_json(i) for i in obj]
                    else:
                        return obj

                json.dump(convert_for_json(results), f, indent=2)

            # Create individual model plots
            compare_batch_throughput(results, model_output_dir)
            compare_sequence_length_impact(results, model_output_dir)
            create_heatmap(results, model_output_dir)

            # Create summary report
            create_summary_report(results, system_info, model_output_dir)

            model_results.append(results)

        # Compare models
        compare_models(model_results, args.output_dir)

    else:
        # Validate arguments for single model
        if not args.model_path:
            parser.error("--model_path is required for single model benchmarking")

        # Benchmark single model
        results = benchmark_model(
            args.model_path,
            device,
            args.batch_sizes,
            args.seq_lengths,
            args.num_runs,
            args.warm_up,
        )

        # Save results to file
        os.makedirs(args.output_dir, exist_ok=True)
        results_path = os.path.join(args.output_dir, "benchmark_results.json")
        with open(results_path, "w") as f:
            # Convert any non-serializable values
            def convert_for_json(obj):
                if isinstance(
                    obj,
                    (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, np.int64),
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

            json.dump(convert_for_json(results), f, indent=2)

        # Create plots
        compare_batch_throughput(results, args.output_dir)
        compare_sequence_length_impact(results, args.output_dir)
        create_heatmap(results, args.output_dir)

        # Create summary report
        create_summary_report(results, system_info, args.output_dir)

        # Log to MLflow if run ID is provided
        if args.mlflow_run_id:
            try:
                mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "mlruns"))
                with mlflow.start_run(run_id=args.mlflow_run_id):
                    # Log the benchmark results file
                    mlflow.log_artifact(results_path)

                    # Log key metrics
                    key = f"batch_1_seq_128"
                    if key in results["benchmarks"]:
                        mlflow.log_metric(
                            "inference_latency_ms",
                            results["benchmarks"][key]["timing"]["avg_time_ms"],
                        )
                        mlflow.log_metric(
                            "inference_throughput",
                            results["benchmarks"][key]["timing"]["samples_per_second"],
                        )

                    mlflow.log_metric("model_size_mb", results["model_size_mb"])

                    # Log system info
                    mlflow.log_dict(system_info, "system_info.json")
            except Exception as e:
                logger.warning(f"Warning: Failed to log to MLflow: {str(e)}")


if __name__ == "__main__":
    main()
