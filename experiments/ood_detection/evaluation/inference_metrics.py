"""
Inference performance metrics for OOD detection models.
"""

import tensorflow as tf
import numpy as np
from typing import Dict, List, Optional, Any, Callable
import time
import logging
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InferenceMetrics:
    """
    Inference performance metrics for OOD detection models.

    This class provides methods for measuring and analyzing
    inference performance of OOD detection models.
    """

    def __init__(self, use_gpu: bool = False):
        """
        Initialize inference metrics calculator.

        Args:
            use_gpu: Whether to use GPU for inference
        """
        self.use_gpu = use_gpu

        # Set TensorFlow device
        if use_gpu:
            # Check if GPU is available
            gpus = tf.config.list_physical_devices("GPU")
            if not gpus:
                logger.warning("No GPU found. Using CPU instead.")
                self.device = "/CPU:0"
            else:
                self.device = "/GPU:0"
        else:
            self.device = "/CPU:0"

    def measure_inference_time(
        self,
        model: tf.keras.Model,
        inputs: Dict[str, tf.Tensor],
        batch_sizes: List[int] = [1, 4, 8, 16, 32, 64],
        num_runs: int = 100,
        warmup_runs: int = 10,
        use_uncertainty: bool = True,
    ) -> Dict[str, Dict[str, float]]:
        """
        Measure inference time for different batch sizes.

        Args:
            model: The model to measure
            inputs: Example inputs to the model
            batch_sizes: List of batch sizes to test
            num_runs: Number of inference runs for each batch size
            warmup_runs: Number of warmup runs
            use_uncertainty: Whether to use predict_with_uncertainty

        Returns:
            results: Dictionary of inference times for each batch size
        """
        results = {}

        # Sample input data
        sample_input_ids = inputs["input_ids"]
        sample_attention_mask = inputs["attention_mask"]

        for batch_size in batch_sizes:
            logger.info(f"Measuring inference time for batch size {batch_size}")

            # Create batch of data
            if batch_size <= len(sample_input_ids):
                input_ids = sample_input_ids[:batch_size]
                attention_mask = sample_attention_mask[:batch_size]
            else:
                # Replicate data to reach the desired batch size
                copies = batch_size // len(sample_input_ids) + 1
                input_ids = tf.tile(sample_input_ids, [copies, 1])[:batch_size]
                attention_mask = tf.tile(sample_attention_mask, [copies, 1])[
                    :batch_size
                ]

            batch_inputs = {"input_ids": input_ids, "attention_mask": attention_mask}

            # Warmup runs
            for _ in range(warmup_runs):
                if use_uncertainty:
                    _ = model.predict_with_uncertainty(batch_inputs)
                else:
                    _ = model(batch_inputs, training=False)

            # Measure inference time
            times = []
            with tf.device(self.device):
                for _ in range(num_runs):
                    start_time = time.time()

                    if use_uncertainty:
                        _ = model.predict_with_uncertainty(batch_inputs)
                    else:
                        _ = model(batch_inputs, training=False)

                    end_time = time.time()
                    times.append(end_time - start_time)

            # Calculate statistics
            mean_time = np.mean(times)
            std_time = np.std(times)
            median_time = np.median(times)
            p95_time = np.percentile(times, 95)

            # Store results
            results[str(batch_size)] = {
                "mean": mean_time,
                "std": std_time,
                "median": median_time,
                "p95": p95_time,
                "throughput": batch_size / mean_time,
            }

        return results

    def measure_training_time(
        self,
        model_fn: Callable[[], tf.keras.Model],
        train_dataset: tf.data.Dataset,
        val_dataset: tf.data.Dataset,
        epochs: int = 5,
        num_runs: int = 3,
    ) -> Dict[str, float]:
        """
        Measure training time for the model.

        Args:
            model_fn: Function that returns a new model instance
            train_dataset: Training dataset
            val_dataset: Validation dataset
            epochs: Number of epochs to train
            num_runs: Number of training runs

        Returns:
            results: Dictionary of training time statistics
        """
        times = []

        for run in range(num_runs):
            logger.info(f"Training run {run + 1}/{num_runs}")

            # Create new model instance
            model = model_fn()

            # Measure training time
            start_time = time.time()

            # Train the model
            model.fit(
                train_dataset, validation_data=val_dataset, epochs=epochs, verbose=0
            )

            end_time = time.time()
            total_time = end_time - start_time
            times.append(total_time)

            logger.info(f"Training time: {total_time:.2f} seconds")

        # Calculate statistics
        mean_time = np.mean(times)
        std_time = np.std(times)
        min_time = np.min(times)
        max_time = np.max(times)

        return {
            "mean": mean_time,
            "std": std_time,
            "min": min_time,
            "max": max_time,
            "per_epoch": mean_time / epochs,
        }

    def measure_memory_usage(
        self,
        model: tf.keras.Model,
        inputs: Dict[str, tf.Tensor],
        batch_sizes: List[int] = [1, 4, 8, 16, 32, 64],
        use_uncertainty: bool = True,
    ) -> Dict[str, float]:
        """
        Estimate memory usage for different batch sizes.

        Note: This is a rough estimation and may not be accurate for all models.

        Args:
            model: The model to measure
            inputs: Example inputs to the model
            batch_sizes: List of batch sizes to test
            use_uncertainty: Whether to use predict_with_uncertainty

        Returns:
            results: Dictionary of memory usage for each batch size
        """
        results = {}

        # Sample input data
        sample_input_ids = inputs["input_ids"]
        sample_attention_mask = inputs["attention_mask"]

        for batch_size in batch_sizes:
            logger.info(f"Measuring memory usage for batch size {batch_size}")

            # Create batch of data
            if batch_size <= len(sample_input_ids):
                input_ids = sample_input_ids[:batch_size]
                attention_mask = sample_attention_mask[:batch_size]
            else:
                # Replicate data to reach the desired batch size
                copies = batch_size // len(sample_input_ids) + 1
                input_ids = tf.tile(sample_input_ids, [copies, 1])[:batch_size]
                attention_mask = tf.tile(sample_attention_mask, [copies, 1])[
                    :batch_size
                ]

            batch_inputs = {"input_ids": input_ids, "attention_mask": attention_mask}

            # Clear memory
            if self.use_gpu:
                tf.keras.backend.clear_session()

            # Run once to initialize
            if use_uncertainty:
                _ = model.predict_with_uncertainty(batch_inputs)
            else:
                _ = model(batch_inputs, training=False)

            # Estimate memory usage (rough estimate)
            # This only works for certain environments and may not be accurate
            try:
                if self.use_gpu and tf.config.list_physical_devices("GPU"):
                    memory_info = tf.config.experimental.get_memory_info("GPU:0")
                    memory_usage = memory_info["current"] / (1024**2)  # Convert to MB
                else:
                    # For CPU, we use the model size as a proxy
                    model_size = model.count_params() * 4  # 4 bytes per parameter
                    memory_usage = model_size / (1024**2)  # Convert to MB
            except Exception as e:
                logger.warning(
                    f"Could not retrieve memory info: {e}. Using model size as proxy."
                )
                # If memory info is not available, use a placeholder
                memory_usage = -1

            results[str(batch_size)] = memory_usage

        return results

    def plot_inference_times(
        self,
        inference_results: Dict[str, Dict[str, float]],
        title: str = "Inference Time vs Batch Size",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """
        Plot inference times for different batch sizes.

        Args:
            inference_results: Results from measure_inference_time
            title: Plot title
            save_path: Path to save the plot

        Returns:
            fig: The figure object
        """
        batch_sizes = sorted([int(bs) for bs in inference_results.keys()])
        mean_times = [inference_results[str(bs)]["mean"] for bs in batch_sizes]
        p95_times = [inference_results[str(bs)]["p95"] for bs in batch_sizes]

        fig, ax1 = plt.subplots(figsize=(10, 6))

        # Plot inference time
        line1 = ax1.plot(batch_sizes, mean_times, "b-", marker="o", label="Mean Time")
        line2 = ax1.plot(batch_sizes, p95_times, "b--", marker="s", label="P95 Time")
        ax1.set_xlabel("Batch Size")
        ax1.set_ylabel("Inference Time (seconds)", color="b")
        ax1.tick_params(axis="y", labelcolor="b")

        # Plot throughput on secondary axis
        ax2 = ax1.twinx()
        throughput = [inference_results[str(bs)]["throughput"] for bs in batch_sizes]
        line3 = ax2.plot(batch_sizes, throughput, "r-", marker="x", label="Throughput")
        ax2.set_ylabel("Throughput (examples/second)", color="r")
        ax2.tick_params(axis="y", labelcolor="r")

        # Combine legends
        lines = line1 + line2 + line3
        labels = [line.get_label() for line in lines]
        ax1.legend(lines, labels, loc="upper left")

        plt.title(title)
        plt.grid(True, alpha=0.3)

        if save_path is not None:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)

        return fig

    def compare_models(
        self,
        model_results: Dict[str, Dict[str, Dict[str, float]]],
        metric: str = "mean",
        title: str = "Model Inference Time Comparison",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """
        Compare inference times across different models.

        Args:
            model_results: Dictionary of results for each model
            metric: Which metric to compare ('mean', 'p95', 'throughput')
            title: Plot title
            save_path: Path to save the plot

        Returns:
            fig: The figure object
        """
        fig, ax = plt.subplots(figsize=(12, 8))

        # Extract batch sizes from the first model
        model_name = list(model_results.keys())[0]
        batch_sizes = sorted([int(bs) for bs in model_results[model_name].keys()])

        # Prepare data for plotting
        data = []
        for model, results in model_results.items():
            for bs in batch_sizes:
                value = results[str(bs)][metric]
                data.append({"Model": model, "Batch Size": bs, "Value": value})

        # Create DataFrame
        df = pd.DataFrame(data)

        # Plot
        if metric == "throughput":
            # For throughput, higher is better
            sns.barplot(x="Batch Size", y="Value", hue="Model", data=df, ax=ax)
            ax.set_ylabel("Throughput (examples/second)")
        else:
            # For time metrics, lower is better
            sns.barplot(x="Batch Size", y="Value", hue="Model", data=df, ax=ax)
            ax.set_ylabel(f"Inference Time ({metric})")

        ax.set_title(title)
        ax.grid(True, alpha=0.3)

        # Rotate x-axis labels if there are many batch sizes
        if len(batch_sizes) > 6:
            plt.xticks(rotation=45)

        plt.tight_layout()

        if save_path is not None:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)

        return fig

    def save_results(
        self, results: Dict[str, Any], model_name: str, output_dir: str
    ) -> str:
        """
        Save inference results to a file.

        Args:
            results: Results dictionary
            model_name: Name of the model
            output_dir: Directory to save the results

        Returns:
            file_path: Path to the saved file
        """
        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{model_name}_inference_metrics.json")

        with open(file_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"Results saved to {file_path}")
        return file_path

    def generate_performance_report(
        self,
        inference_results: Dict[str, Dict[str, float]],
        training_results: Optional[Dict[str, float]] = None,
        model_name: str = "Model",
        output_dir: str = "results",
    ) -> str:
        """
        Generate a performance report.

        Args:
            inference_results: Results from measure_inference_time
            training_results: Results from measure_training_time
            model_name: Name of the model
            output_dir: Directory to save the report

        Returns:
            report_path: Path to the generated report
        """
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, f"{model_name}_performance_report.txt")

        with open(report_path, "w") as f:
            f.write(f"Performance Report for {model_name}\n")
            f.write("=" * 50 + "\n\n")

            f.write("Inference Performance:\n")
            f.write("-" * 30 + "\n")

            f.write(
                "Batch Size | Mean Time (s) | P95 Time (s) | Throughput (examples/s)\n"
            )
            f.write("-" * 70 + "\n")

            for bs in sorted([int(bs) for bs in inference_results.keys()]):
                results = inference_results[str(bs)]
                f.write(
                    f"{bs:^10} | {results['mean']:^13.4f} | {results['p95']:^12.4f} | {results['throughput']:^24.2f}\n"
                )

            f.write("\n")

            if training_results is not None:
                f.write("\nTraining Performance:\n")
                f.write("-" * 30 + "\n")

                f.write(
                    f"Total Training Time: {training_results['mean']:.2f} seconds\n"
                )
                f.write(
                    f"Time per Epoch: {training_results['per_epoch']:.2f} seconds\n"
                )
                f.write(f"Standard Deviation: {training_results['std']:.2f} seconds\n")
                f.write(f"Min Training Time: {training_results['min']:.2f} seconds\n")
                f.write(f"Max Training Time: {training_results['max']:.2f} seconds\n")

        logger.info(f"Performance report saved to {report_path}")
        return report_path
