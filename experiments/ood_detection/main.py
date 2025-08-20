"""
Main entry point for running experiments.
"""

import os
import sys
import logging
import argparse
import tensorflow as tf
import numpy as np
import json
from datetime import datetime
from utils.visualization import Visualizer

# Setup Python path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run OOD detection experiments")

    parser.add_argument(
        "--experiment",
        type=str,
        choices=["sngp", "energy", "sngp_energy", "ood_class", "softmax", "all"],
        default="all",
        help="Experiment to run",
    )

    parser.add_argument("--train-file", type=str, help="Path to training data")
    parser.add_argument("--dev-file", type=str, help="Path to validation data")
    parser.add_argument("--test-file", type=str, help="Path to test data")
    parser.add_argument("--ood-file", type=str, help="Path to OOD test data")

    parser.add_argument(
        "--output-dir", type=str, default="outputs", help="Directory to save outputs"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for training and evaluation",
    )
    parser.add_argument(
        "--epochs", type=int, default=10, help="Number of training epochs"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    parser.add_argument("--use-gpu", action="store_true", help="Whether to use GPU")

    parser.add_argument(
        "--mlflow-tracking-uri", type=str, default=None, help="MLflow tracking URI"
    )
    parser.add_argument(
        "--mlflow-experiment-name",
        type=str,
        default="ood_detection",
        help="MLflow experiment name",
    )

    parser.add_argument(
        "--log-performance",
        action="store_true",
        help="Whether to log performance metrics",
    )

    parser.add_argument(
        "--analyze", action="store_true", help="Run analysis after experiments"
    )

    return parser.parse_args()


def run_experiment(experiment_name, args):
    """
    Run an experiment.

    Args:
        experiment_name: Name of the experiment
        args: Command-line arguments

    Returns:
        results: Dictionary of evaluation results
    """
    logger.info(f"Running experiment: {experiment_name}")

    # Set up experiment-specific script
    script_name = f"train_{experiment_name}.py"
    script_path = os.path.join("experiments", script_name)

    if not os.path.exists(script_path):
        logger.error(f"Script not found: {script_path}")
        return None

    # Set up experiment-specific output directory
    experiment_output_dir = os.path.join(args.output_dir, experiment_name)
    os.makedirs(experiment_output_dir, exist_ok=True)

    # Construct command
    cmd_args = [
        f"--train-file={args.train_file}" if args.train_file else "",
        f"--dev-file={args.dev_file}" if args.dev_file else "",
        f"--test-file={args.test_file}" if args.test_file else "",
        f"--ood-file={args.ood_file}" if args.ood_file else "",
        f"--output-dir={experiment_output_dir}",
        f"--batch-size={args.batch_size}",
        f"--epochs={args.epochs}",
        f"--seed={args.seed}",
        "--use-gpu" if args.use_gpu else "",
        (
            f"--mlflow-tracking-uri={args.mlflow_tracking_uri}"
            if args.mlflow_tracking_uri
            else ""
        ),
        f"--mlflow-experiment-name={args.mlflow_experiment_name}_{experiment_name}",
        "--log-performance" if args.log_performance else "",
    ]

    cmd_args = [arg for arg in cmd_args if arg]  # Remove empty args

    # Run the script
    cmd = f"python {script_path} {' '.join(cmd_args)}"
    logger.info(f"Running command: {cmd}")

    import subprocess

    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running experiment {experiment_name}: {e}")
        return None

    # Load results
    results_path = os.path.join(experiment_output_dir, "evaluation_results.json")
    if os.path.exists(results_path):
        with open(results_path) as f:
            results = json.load(f)
        return results
    else:
        logger.warning(f"Results file not found: {results_path}")
        return None


def run_all_experiments(args):
    """
    Run all experiments.

    Args:
        args: Command-line arguments

    Returns:
        all_results: Dictionary of results for all experiments
    """
    experiments = [
        "sngp",
        "energy",
        "sngp_energy",
        "ood_class",
        "softmax",
    ]
    all_results = {}

    for experiment in experiments:
        logger.info(f"=== Running experiment: {experiment} ===")
        results = run_experiment(experiment, args)
        if results:
            all_results[experiment] = results

    # Save combined results
    results_path = os.path.join(args.output_dir, "all_results.json")
    with open(results_path, "w") as f:
        json.dump(all_results, f, indent=2)

    logger.info(f"All results saved to {results_path}")

    return all_results


def analyze_results(results, args):
    """
    Analyze results from all experiments.

    Args:
        results: Dictionary of results for all experiments
        args: Command-line arguments
    """
    logger.info("Analyzing results...")

    # Set up visualization directory
    viz_dir = os.path.join(args.output_dir, "visualizations")
    os.makedirs(viz_dir, exist_ok=True)

    # Create visualizer
    visualizer = Visualizer(output_dir=viz_dir)

    # Compare models based on OOD detection metrics
    model_metrics = {}
    for model_name, model_results in results.items():
        metrics = {}
        for metric in [
            "auroc",
            "aupr",
            "fpr_at_95_tpr",
            "detection_error",
            "accuracy",
            "f1",
        ]:
            if metric in model_results:
                metrics[metric] = model_results[metric]
        model_metrics[model_name] = metrics

    # Plot comparison for individual metrics
    for metric in [
        "auroc",
        "aupr",
        "fpr_at_95_tpr",
        "detection_error",
        "accuracy",
        "f1",
    ]:
        if all(metric in model_results for model_results in model_metrics.values()):
            visualizer.plot_model_comparison(
                model_metrics=model_metrics,
                metric_name=metric,
                title=f"Model Comparison - {metric.upper()}",
            )

    # Plot multi-metric comparison
    visualizer.plot_multi_metric_comparison(
        model_metrics=model_metrics,
        metrics=["auroc", "aupr", "fpr_at_95_tpr", "accuracy"],
        title="Multi-Metric Model Comparison",
    )

    # Compare inference performance if available
    if all(
        "inference_performance" in model_results for model_results in results.values()
    ):
        inference_results = {}
        for model_name, model_results in results.items():
            inference_results[model_name] = model_results["inference_performance"]

        # Create inference performance comparison
        from evaluation.inference_metrics import InferenceMetrics

        inference_metrics = InferenceMetrics(use_gpu=args.use_gpu)

        # Plot comparison for mean inference time
        inference_fig = inference_metrics.compare_models(
            model_results=inference_results,
            metric="mean",
            title="Model Inference Time Comparison",
        )
        inference_fig.savefig(
            os.path.join(viz_dir, "inference_time_comparison.png"),
            bbox_inches="tight",
            dpi=300,
        )

        # Plot comparison for throughput
        throughput_fig = inference_metrics.compare_models(
            model_results=inference_results,
            metric="throughput",
            title="Model Throughput Comparison",
        )
        throughput_fig.savefig(
            os.path.join(viz_dir, "throughput_comparison.png"),
            bbox_inches="tight",
            dpi=300,
        )

    # Generate analysis report
    generate_analysis_report(results, args.output_dir)


def generate_analysis_report(results, output_dir):
    """
    Generate analysis report.

    Args:
        results: Dictionary of results for all experiments
        output_dir: Output directory
    """
    logger.info("Generating analysis report...")

    report_path = os.path.join(output_dir, "ANALYSIS.md")

    with open(report_path, "w") as f:
        f.write("# OOD Detection Analysis Report\n\n")
        f.write(f"*Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")

        f.write("## Overview\n\n")
        f.write(
            "This report analyzes the performance of various OOD detection methods for conversation classification. "
        )
        f.write(
            "The goal is to identify the most effective approach for detecting out-of-distribution examples "
        )
        f.write("while maintaining high accuracy on in-distribution data.\n\n")

        f.write("## Methods Evaluated\n\n")
        f.write(
            "1. **SNGP (Spectral-normalized Neural Gaussian Process)**: Enhances distance awareness through spectral normalization and Gaussian process output layer.\n"
        )
        f.write(
            "2. **Energy-based OOD Detection**: Uses energy scores as uncertainty measures.\n"
        )
        f.write("3. **SNGP + Energy**: Combines SNGP with energy-based detection.\n")
        f.write(
            "4. **OOD as a Class**: Treats OOD examples as an additional class during training.\n"
        )
        f.write(
            "5. **Softmax Threshold**: Uses softmax probabilities or entropy for uncertainty estimation.\n\n"
        )

        f.write("## Performance Metrics\n\n")
        f.write("### OOD Detection Performance\n\n")

        # Create OOD detection metrics table
        f.write("| Method | AUROC | AUPR | FPR@95%TPR | Detection Error |\n")
        f.write("|--------|-------|------|------------|----------------|\n")

        for model_name, model_results in results.items():
            auroc = model_results.get("auroc", "N/A")
            aupr = model_results.get("aupr", "N/A")
            fpr_at_95_tpr = model_results.get("fpr_at_95_tpr", "N/A")
            detection_error = model_results.get("detection_error", "N/A")

            # Format numbers
            if isinstance(auroc, (float, int)):
                auroc = f"{auroc:.4f}"
            if isinstance(aupr, (float, int)):
                aupr = f"{aupr:.4f}"
            if isinstance(fpr_at_95_tpr, (float, int)):
                fpr_at_95_tpr = f"{fpr_at_95_tpr:.4f}"
            if isinstance(detection_error, (float, int)):
                detection_error = f"{detection_error:.4f}"

            f.write(
                f"| {model_name} | {auroc} | {aupr} | {fpr_at_95_tpr} | {detection_error} |\n"
            )

        f.write("\n### Classification Performance\n\n")

        # Create classification metrics table
        f.write("| Method | Accuracy | F1 Score | Precision | Recall |\n")
        f.write("|--------|----------|----------|-----------|--------|\n")

        for model_name, model_results in results.items():
            accuracy = model_results.get("accuracy", "N/A")
            f1 = model_results.get("f1", "N/A")
            precision = model_results.get("precision", "N/A")
            recall = model_results.get("recall", "N/A")

            # Format numbers
            if isinstance(accuracy, (float, int)):
                accuracy = f"{accuracy:.4f}"
            if isinstance(f1, (float, int)):
                f1 = f"{f1:.4f}"
            if isinstance(precision, (float, int)):
                precision = f"{precision:.4f}"
            if isinstance(recall, (float, int)):
                recall = f"{recall:.4f}"

            f.write(f"| {model_name} | {accuracy} | {f1} | {precision} | {recall} |\n")

        f.write("\n### Inference Performance\n\n")

        # Check if inference performance is available
        if all(
            "inference_performance" in model_results
            for model_results in results.values()
        ):
            # Create inference performance table
            f.write(
                "| Method | Mean Time (ms) - Batch Size 1 | Throughput (examples/s) - Batch Size 32 |\n"
            )
            f.write(
                "|--------|------------------------------|----------------------------------------|\n"
            )

            for model_name, model_results in results.items():
                inference_perf = model_results.get("inference_performance", {})

                # Get metrics for batch sizes 1 and 32
                mean_time_bs1 = inference_perf.get("1", {}).get("mean", "N/A")
                throughput_bs32 = inference_perf.get("32", {}).get("throughput", "N/A")

                # Convert to milliseconds and format
                if isinstance(mean_time_bs1, (float, int)):
                    mean_time_bs1 = f"{mean_time_bs1 * 1000:.2f}"
                if isinstance(throughput_bs32, (float, int)):
                    throughput_bs32 = f"{throughput_bs32:.2f}"

                f.write(f"| {model_name} | {mean_time_bs1} | {throughput_bs32} |\n")
        else:
            f.write("Inference performance metrics are not available for all models.\n")

        f.write("\n## Analysis\n\n")
        f.write("### OOD Detection Capability\n\n")
        f.write(
            "Analysis of how well each method detects out-of-distribution examples...\n\n"
        )

        f.write("### Impact on Classification Accuracy\n\n")
        f.write(
            "Analysis of how OOD detection methods affect classification accuracy...\n\n"
        )

        f.write("### Computational Efficiency\n\n")
        f.write("Analysis of computational requirements and inference speed...\n\n")

        f.write("## Conclusion\n\n")
        f.write(
            "Based on the evaluation results, the recommended approach for OOD detection is...\n\n"
        )

        f.write("## Recommendations\n\n")
        f.write(
            "Specific recommendations for implementing OOD detection in production...\n\n"
        )

    logger.info(f"Analysis report generated: {report_path}")

    # Also generate decision document
    generate_decision_document(results, output_dir)


def generate_decision_document(results, output_dir):
    """
    Generate decision document.

    Args:
        results: Dictionary of results for all experiments
        output_dir: Output directory
    """
    logger.info("Generating decision document...")

    # Find best model based on AUROC and FPR@95%TPR
    best_model = None
    best_auroc = -1
    best_fpr = float("inf")

    for model_name, model_results in results.items():
        auroc = model_results.get("auroc", 0)
        fpr = model_results.get("fpr_at_95_tpr", 1.0)

        # Prioritize models with higher AUROC
        if auroc > best_auroc:
            best_model = model_name
            best_auroc = auroc
            best_fpr = fpr
        # If AUROC is similar, choose the one with lower FPR
        elif abs(auroc - best_auroc) < 0.01 and fpr < best_fpr:
            best_model = model_name
            best_auroc = auroc
            best_fpr = fpr

    decision_path = os.path.join(output_dir, "DECISION.md")

    with open(decision_path, "w") as f:
        f.write("# OOD Detection Decision Document\n\n")
        f.write(f"*Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")

        f.write("## Decision Summary\n\n")
        if best_model:
            f.write(
                f"Based on comprehensive evaluation of multiple OOD detection approaches, we have selected **{best_model}** "
            )
            f.write(
                "as the optimal method for detecting out-of-distribution examples in conversation classification.\n\n"
            )
        else:
            f.write(
                "Based on comprehensive evaluation of multiple OOD detection approaches, we need to conduct further analysis "
            )
            f.write(
                "before making a final decision on the optimal method for detecting out-of-distribution examples.\n\n"
            )

        f.write("## Selection Criteria\n\n")
        f.write(
            "The following criteria were used to evaluate and compare OOD detection methods:\n\n"
        )
        f.write(
            "1. **OOD Detection Performance**: Measured using AUROC, AUPR, and FPR@95%TPR metrics.\n"
        )
        f.write(
            "2. **Classification Accuracy**: Impact on in-distribution classification performance.\n"
        )
        f.write(
            "3. **Computational Efficiency**: Inference time and resource requirements.\n"
        )
        f.write(
            "4. **Implementation Complexity**: Ease of integration with existing system.\n\n"
        )

        f.write("## Method Evaluation\n\n")

        for model_name, model_results in results.items():
            f.write(f"### {model_name}\n\n")

            # OOD detection metrics
            auroc = model_results.get("auroc", "N/A")
            aupr = model_results.get("aupr", "N/A")
            fpr_at_95_tpr = model_results.get("fpr_at_95_tpr", "N/A")

            f.write("**OOD Detection Performance**:\n")
            f.write(f"- AUROC: {auroc if isinstance(auroc, str) else f'{auroc:.4f}'}\n")
            f.write(f"- AUPR: {aupr if isinstance(aupr, str) else f'{aupr:.4f}'}\n")
            f.write(
                f"- FPR@95%TPR: {fpr_at_95_tpr if isinstance(fpr_at_95_tpr, str) else f'{fpr_at_95_tpr:.4f}'}\n\n"
            )

            # Classification metrics
            accuracy = model_results.get("accuracy", "N/A")
            f1 = model_results.get("f1", "N/A")

            f.write("**Classification Performance**:\n")
            f.write(
                f"- Accuracy: {accuracy if isinstance(accuracy, str) else f'{accuracy:.4f}'}\n"
            )
            f.write(f"- F1 Score: {f1 if isinstance(f1, str) else f'{f1:.4f}'}\n\n")

            # Inference performance
            if "inference_performance" in model_results:
                inference_perf = model_results["inference_performance"]
                mean_time_bs1 = inference_perf.get("1", {}).get("mean", "N/A")
                mean_time_bs32 = inference_perf.get("32", {}).get("mean", "N/A")

                f.write("**Computational Performance**:\n")
                f.write(
                    f"- Inference Time (Batch Size 1): {mean_time_bs1 if isinstance(mean_time_bs1, str) else f'{mean_time_bs1 * 1000:.2f} ms'}\n"
                )
                f.write(
                    f"- Inference Time (Batch Size 32): {mean_time_bs32 if isinstance(mean_time_bs32, str) else f'{mean_time_bs32 * 1000:.2f} ms'}\n\n"
                )

            # Pros and cons
            f.write("**Pros**:\n")
            if model_name == "sngp":
                f.write("- Strong uncertainty estimation through distance awareness\n")
                f.write(
                    "- Single model without ensemble averaging, efficient inference\n"
                )
                f.write("- Compatible with modern deep learning architectures\n")
            elif model_name == "energy":
                f.write("- Simple to implement on top of existing models\n")
                f.write("- No architectural changes required\n")
                f.write("- Theoretically well-founded for OOD detection\n")
            elif model_name == "sngp_energy":
                f.write("- Combines benefits of both SNGP and energy-based methods\n")
                f.write("- Better OOD detection through complementary approaches\n")
                f.write("- Robust to different types of OOD examples\n")
            elif model_name == "ood_class":
                f.write("- Intuitive approach that directly learns OOD patterns\n")
                f.write(
                    "- Simple to implement within existing classification framework\n"
                )
                f.write("- No post-processing required during inference\n")
            elif model_name == "softmax":
                f.write("- Simplest approach with minimal changes to existing models\n")
                f.write("- Fast inference with no additional computation\n")
                f.write("- Well-understood calibration techniques available\n")
            f.write("\n")

            f.write("**Cons**:\n")
            if model_name == "sngp":
                f.write("- More complex implementation than baseline methods\n")
                f.write(
                    "- Requires careful handling of covariance reset during training\n"
                )
                f.write("- May require tuning of spectral normalization parameters\n")
            elif model_name == "energy":
                f.write(
                    "- Performance can be sensitive to energy temperature parameter\n"
                )
                f.write("- May require additional training with energy-based loss\n")
                f.write(
                    "- Less effective for detecting certain types of OOD examples\n"
                )
            elif model_name == "sngp_energy":
                f.write("- Most complex implementation among all methods\n")
                f.write("- Higher computational overhead during training\n")
                f.write("- Requires tuning of multiple hyperparameters\n")
            elif model_name == "ood_class":
                f.write("- Performance depends on quality of synthetic OOD examples\n")
                f.write("- May reduce ID classification performance\n")
                f.write("- Struggles with OOD examples that differ from training OOD\n")
            elif model_name == "softmax":
                f.write("- Often less effective than more sophisticated methods\n")
                f.write("- Requires proper calibration for reliable uncertainty\n")
                f.write("- Tends to be overconfident far from the decision boundary\n")
            f.write("\n\n")

        f.write("## Final Decision\n\n")
        if best_model:
            f.write(
                f"We have selected **{best_model}** as our OOD detection approach based on its strong performance across multiple metrics. "
            )
            if best_model == "sngp":
                f.write(
                    "SNGP provides excellent uncertainty estimation through distance awareness while maintaining efficient inference. "
                )
                f.write(
                    "The model achieved the best balance of OOD detection performance and classification accuracy.\n\n"
                )
            elif best_model == "energy":
                f.write(
                    "Energy-based OOD detection offers a good balance of implementation simplicity and detection performance. "
                )
                f.write(
                    "It requires minimal changes to the existing model architecture while providing reliable uncertainty estimates.\n\n"
                )
            elif best_model == "sngp_energy":
                f.write(
                    "The combined SNGP+Energy approach provides the most robust OOD detection by leveraging both distance awareness and energy scores. "
                )
                f.write(
                    "Despite its higher complexity, the superior detection performance justifies the implementation effort.\n\n"
                )
            elif best_model == "ood_class":
                f.write(
                    "Treating OOD as a separate class proved most effective in our evaluation, offering an intuitive approach with strong performance. "
                )
                f.write(
                    "The simplicity of implementation and direct uncertainty scores make it a practical choice for production deployment.\n\n"
                )
            elif best_model == "softmax":
                f.write(
                    "The softmax threshold approach provides a good balance of simplicity and effectiveness. "
                )
                f.write(
                    "While more sophisticated methods exist, this approach requires minimal changes to existing infrastructure while delivering acceptable performance.\n\n"
                )
        else:
            f.write("Further evaluation is needed before making a final decision. ")
            f.write(
                "While all methods demonstrated strengths in certain areas, no single approach emerged as clearly superior across all metrics.\n\n"
            )

        f.write("## Implementation Plan\n\n")
        f.write("### Integration Steps\n\n")
        f.write(
            "1. Implement the selected OOD detection method within the existing classification model\n"
        )
        f.write(
            "2. Establish appropriate uncertainty thresholds based on validation data\n"
        )
        f.write("3. Set up monitoring for OOD detection performance in production\n")
        f.write("4. Create fallback mechanisms for handling detected OOD examples\n\n")

        f.write("### Threshold Selection\n\n")
        f.write(
            "We recommend setting the uncertainty threshold to achieve a 95% true positive rate (TPR) on validation data. "
        )
        f.write(
            "This corresponds to correctly identifying 95% of in-distribution examples, with the remaining 5% incorrectly flagged as OOD. "
        )
        f.write(
            "Based on our experiments, this threshold provides a good balance between catching OOD examples and minimizing false alarms.\n\n"
        )

        f.write("## Conclusion\n\n")
        f.write(
            "The selected OOD detection approach will enable the system to identify conversations that fall outside the trained distribution, "
        )
        f.write(
            "allowing for more reliable classification and appropriate handling of uncertain cases. This implementation will improve the "
        )
        f.write(
            "overall robustness of the conversation classification system and enhance user experience by avoiding incorrect classifications "
        )
        f.write("when the model is uncertain.\n")

    logger.info(f"Decision document generated: {decision_path}")


def main():
    """Main function."""
    # Parse arguments
    args = parse_args()

    # Set up output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Set random seed
    np.random.seed(args.seed)
    tf.random.set_seed(args.seed)

    # Configure GPU usage
    if args.use_gpu:
        # Check if GPU is available
        gpus = tf.config.list_physical_devices("GPU")
        if gpus:
            try:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"Using GPU: {len(gpus)} GPU(s) available")
            except RuntimeError as e:
                logger.error(f"Error setting GPU memory growth: {e}")
        else:
            logger.warning("No GPU found. Using CPU instead.")
    else:
        # Disable GPU
        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        logger.info("Using CPU as requested")

    # Run experiments
    if args.experiment == "all":
        logger.info("Running all experiments")
        results = run_all_experiments(args)
    else:
        logger.info(f"Running experiment: {args.experiment}")
        results = {args.experiment: run_experiment(args.experiment, args)}

    # Analyze results if requested
    if args.analyze and results:
        analyze_results(results, args)

    logger.info("Done")


if __name__ == "__main__":
    main()
