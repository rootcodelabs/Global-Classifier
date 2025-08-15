import os
import argparse
import json
import glob
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import mlflow
from mlflow.tracking import MlflowClient


def setup_mlflow(tracking_uri, experiment_name):
    """
    Set up MLflow tracking and create or get the experiment.

    Args:
        tracking_uri (str): URI for MLflow tracking server
        experiment_name (str): Name of the experiment

    Returns:
        str: Experiment ID
    """
    mlflow.set_tracking_uri(tracking_uri)

    # Get or create the experiment
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment:
        experiment_id = experiment.experiment_id
    else:
        experiment_id = mlflow.create_experiment(experiment_name)

    print(f"MLflow experiment '{experiment_name}' (ID: {experiment_id}) is ready")
    return experiment_id


def log_model_training(model_dir, metrics_file, artifacts_dir=None, tags=None):
    """
    Log model training metrics and artifacts to MLflow.

    Args:
        model_dir (str): Directory containing the model files
        metrics_file (str): Path to the metrics JSON file
        artifacts_dir (str, optional): Directory containing additional artifacts
        tags (dict, optional): Tags to add to the run

    Returns:
        str: MLflow run ID
    """
    # Load metrics
    with open(metrics_file, "r") as f:
        metrics_data = json.load(f)

    model_type = metrics_data.get("model_type", os.path.basename(model_dir))

    # Start MLflow run
    with mlflow.start_run(
        run_name=f"{model_type}_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ) as run:
        run_id = run.info.run_id

        # Log parameters
        params = {
            k: v
            for k, v in metrics_data.items()
            if not isinstance(v, (dict, list)) and k != "timestamp"
        }
        mlflow.log_params(params)

        # Log metrics
        if "test_metrics" in metrics_data:
            for k, v in metrics_data["test_metrics"].items():
                if not isinstance(v, (dict, list, np.ndarray)):
                    mlflow.log_metric(f"test_{k}", v)

        # Log training time if available
        if "training_time_seconds" in metrics_data:
            mlflow.log_metric(
                "training_time_seconds", metrics_data["training_time_seconds"]
            )

        # Log inference time if available
        if "avg_inference_time_seconds" in metrics_data:
            mlflow.log_metric(
                "avg_inference_time_seconds", metrics_data["avg_inference_time_seconds"]
            )

        # Log the model if available
        model_files = glob.glob(os.path.join(model_dir, "*.bin")) + glob.glob(
            os.path.join(model_dir, "*.pt")
        )
        if model_files:
            mlflow.log_artifact(model_dir, "model")

        # Log the metrics file itself
        mlflow.log_artifact(metrics_file, "metrics")

        # Log additional artifacts if provided
        if artifacts_dir and os.path.exists(artifacts_dir):
            for artifact_file in glob.glob(os.path.join(artifacts_dir, "*")):
                if os.path.isfile(artifact_file):
                    mlflow.log_artifact(artifact_file, "artifacts")

        # Add tags if provided
        if tags:
            mlflow.set_tags(tags)

        # Add default tags
        mlflow.set_tag("model_type", model_type)
        mlflow.set_tag("stage", "training")

    print(f"Training metrics logged to MLflow run: {run_id}")
    return run_id


def log_model_evaluation(evaluation_file, run_id=None, artifacts_dir=None, tags=None):
    """
    Log model evaluation metrics to MLflow.

    Args:
        evaluation_file (str): Path to the evaluation results JSON file
        run_id (str, optional): Existing MLflow run ID to log to
        artifacts_dir (str, optional): Directory containing additional artifacts
        tags (dict, optional): Tags to add to the run

    Returns:
        str: MLflow run ID
    """
    # Load evaluation results
    with open(evaluation_file, "r") as f:
        eval_data = json.load(f)

    model_name = eval_data.get(
        "model_name", os.path.basename(os.path.dirname(evaluation_file))
    )

    # Determine whether to create a new run or use an existing one
    if run_id:
        # Check if the run exists
        try:
            client = MlflowClient()
            client.get_run(run_id)
            new_run = False
        except Exception as e:
            print(f"Error checking run ID {run_id}: {e}")
            # If run ID does not exist, create a new run
            print(f"Run ID {run_id} not found. Creating a new run.")
            new_run = True
    else:
        new_run = True

    if new_run:
        # Start a new MLflow run
        with mlflow.start_run(
            run_name=f"{model_name}_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ) as run:
            run_id = run.info.run_id

            # Log accuracy metrics
            if "accuracy_metrics" in eval_data:
                for k, v in eval_data["accuracy_metrics"].items():
                    if not isinstance(v, (dict, list, np.ndarray)):
                        mlflow.log_metric(f"eval_{k}", v)

            # Log performance metrics
            if "performance_metrics" in eval_data:
                for k, v in eval_data["performance_metrics"].items():
                    if not isinstance(v, (dict, list, np.ndarray)):
                        mlflow.log_metric(k, v)

            # Log the evaluation file itself
            mlflow.log_artifact(evaluation_file, "evaluation")

            # Log additional artifacts if provided
            if artifacts_dir and os.path.exists(artifacts_dir):
                for artifact_file in glob.glob(os.path.join(artifacts_dir, "*")):
                    if os.path.isfile(artifact_file):
                        mlflow.log_artifact(artifact_file, "artifacts")

            # Add tags if provided
            if tags:
                mlflow.set_tags(tags)

            # Add default tags
            mlflow.set_tag("model_name", model_name)
            mlflow.set_tag("stage", "evaluation")
    else:
        # Log to existing run
        with mlflow.start_run(run_id=run_id):
            # Log accuracy metrics
            if "accuracy_metrics" in eval_data:
                for k, v in eval_data["accuracy_metrics"].items():
                    if not isinstance(v, (dict, list, np.ndarray)):
                        mlflow.log_metric(f"eval_{k}", v)

            # Log performance metrics
            if "performance_metrics" in eval_data:
                for k, v in eval_data["performance_metrics"].items():
                    if not isinstance(v, (dict, list, np.ndarray)):
                        mlflow.log_metric(k, v)

            # Log the evaluation file itself
            mlflow.log_artifact(evaluation_file, "evaluation")

            # Log additional artifacts if provided
            if artifacts_dir and os.path.exists(artifacts_dir):
                for artifact_file in glob.glob(os.path.join(artifacts_dir, "*")):
                    if os.path.isfile(artifact_file):
                        mlflow.log_artifact(artifact_file, "artifacts")

            # Add tags if provided
            if tags:
                mlflow.set_tags(tags)

            # Update stage tag
            mlflow.set_tag("stage", "training+evaluation")

    print(f"Evaluation metrics logged to MLflow run: {run_id}")
    return run_id


def log_inference_performance(
    inference_file, run_id=None, artifacts_dir=None, tags=None
):
    """
    Log inference performance metrics to MLflow.

    Args:
        inference_file (str): Path to the inference results JSON file
        run_id (str, optional): Existing MLflow run ID to log to
        artifacts_dir (str, optional): Directory containing additional artifacts
        tags (dict, optional): Tags to add to the run

    Returns:
        str: MLflow run ID
    """
    # Load inference results
    with open(inference_file, "r") as f:
        inference_data = json.load(f)

    model_name = os.path.basename(
        inference_data.get("model_path", os.path.dirname(inference_file))
    )

    # Determine whether to create a new run or use an existing one
    if run_id:
        # Check if the run exists
        try:
            client = MlflowClient()
            client.get_run(run_id)
            new_run = False
        except Exception as e:
            print(f"Error checking run ID {run_id}: {e}")
            # If run ID does not exist, create a new run
            print(f"Run ID {run_id} not found. Creating a new run.")
            new_run = True
    else:
        new_run = True

    if new_run:
        # Start a new MLflow run
        with mlflow.start_run(
            run_name=f"{model_name}_inference_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ) as run:
            run_id = run.info.run_id

            # Log model size
            if "model_size_mb" in inference_data:
                mlflow.log_metric("model_size_mb", inference_data["model_size_mb"])

            # Log batch size = 1, seq_length = 128 metrics as standard benchmarks
            key = "batch_1_seq_128"
            if "benchmarks" in inference_data and key in inference_data["benchmarks"]:
                timing = inference_data["benchmarks"][key]["timing"]
                mlflow.log_metric("inference_latency_ms", timing["avg_time_ms"])
                mlflow.log_metric("inference_throughput", timing["samples_per_second"])

                memory = inference_data["benchmarks"][key]["memory"]
                mlflow.log_metric("inference_memory_mb", memory["memory_usage_mb"])

            # Log the inference file itself
            mlflow.log_artifact(inference_file, "inference")

            # Log additional artifacts if provided
            if artifacts_dir and os.path.exists(artifacts_dir):
                for artifact_file in glob.glob(os.path.join(artifacts_dir, "*")):
                    if os.path.isfile(artifact_file):
                        mlflow.log_artifact(artifact_file, "artifacts")

            # Add tags if provided
            if tags:
                mlflow.set_tags(tags)

            # Add default tags
            mlflow.set_tag("model_name", model_name)
            mlflow.set_tag("stage", "inference")
    else:
        # Log to existing run
        with mlflow.start_run(run_id=run_id):
            # Log model size
            if "model_size_mb" in inference_data:
                mlflow.log_metric("model_size_mb", inference_data["model_size_mb"])

            # Log batch size = 1, seq_length = 128 metrics as standard benchmarks
            key = "batch_1_seq_128"
            if "benchmarks" in inference_data and key in inference_data["benchmarks"]:
                timing = inference_data["benchmarks"][key]["timing"]
                mlflow.log_metric("inference_latency_ms", timing["avg_time_ms"])
                mlflow.log_metric("inference_throughput", timing["samples_per_second"])

                memory = inference_data["benchmarks"][key]["memory"]
                mlflow.log_metric("inference_memory_mb", memory["memory_usage_mb"])

            # Log the inference file itself
            mlflow.log_artifact(inference_file, "inference")

            # Log additional artifacts if provided
            if artifacts_dir and os.path.exists(artifacts_dir):
                for artifact_file in glob.glob(os.path.join(artifacts_dir, "*")):
                    if os.path.isfile(artifact_file):
                        mlflow.log_artifact(artifact_file, "artifacts")

            # Add tags if provided
            if tags:
                mlflow.set_tags(tags)

            # Update stage tag to indicate this run includes all stages
            mlflow.set_tag("stage", "training+evaluation+inference")

    print(f"Inference metrics logged to MLflow run: {run_id}")
    return run_id


def create_comparison_artifacts(experiment_id, output_dir, model_types=None):
    """
    Create and log comparison artifacts for multiple models in an experiment.

    Args:
        experiment_id (str): MLflow experiment ID
        output_dir (str): Directory to save artifacts
        model_types (list, optional): List of model types to compare
    """
    os.makedirs(output_dir, exist_ok=True)

    # Get all runs for the experiment
    client = MlflowClient()
    runs = client.search_runs(experiment_ids=[experiment_id])

    # Filter runs if model_types is provided
    if model_types:
        filtered_runs = []
        for run in runs:
            if (
                "model_type" in run.data.tags
                and run.data.tags["model_type"] in model_types
            ):
                filtered_runs.append(run)
        runs = filtered_runs

    if not runs:
        print("No runs found for comparison")
        return

    # Extract metrics for comparison
    comparison_data = []

    for run in runs:
        run_data = {
            "run_id": run.info.run_id,
            "model_type": run.data.tags.get("model_type", "unknown"),
            "stage": run.data.tags.get("stage", "unknown"),
        }

        # Add all metrics
        for key, value in run.data.metrics.items():
            run_data[key] = value

        comparison_data.append(run_data)

    # Convert to DataFrame
    comparison_df = pd.DataFrame(comparison_data)

    # Save comparison data
    comparison_csv = os.path.join(output_dir, "model_comparison.csv")
    comparison_df.to_csv(comparison_csv, index=False)

    # Create comparison plots
    metrics_to_compare = [
        "test_accuracy",
        "test_f1",
        "test_precision",
        "test_recall",
        "avg_inference_time_seconds",
        "inference_latency_ms",
        "inference_throughput",
        "model_size_mb",
        "training_time_seconds",
    ]

    for metric in metrics_to_compare:
        if metric in comparison_df.columns:
            plt.figure(figsize=(10, 6))

            # Filter rows that have this metric
            metric_df = comparison_df[comparison_df[metric].notna()]

            if len(metric_df) > 0:
                # Create plot
                ax = sns.barplot(x="model_type", y=metric, data=metric_df)

                # Add value labels on top of each bar
                for i, v in enumerate(metric_df[metric]):
                    ax.text(i, v, f"{v:.4f}", ha="center", va="bottom")

                plt.title(f"Comparison of {metric}")
                plt.tight_layout()

                # Save plot
                plot_path = os.path.join(output_dir, f"compare_{metric}.png")
                plt.savefig(plot_path)
                plt.close()

    # Create radar chart for model comparison if we have at least 2 models
    model_groups = comparison_df.groupby("model_type")
    if len(model_groups) >= 2:
        # Select metrics for radar chart
        radar_metrics = [
            m
            for m in ["test_accuracy", "test_f1", "test_precision", "test_recall"]
            if m in comparison_df.columns
        ]

        if radar_metrics:
            # Get mean values for each model type and metric
            radar_data = model_groups[radar_metrics].mean()

            # Create radar chart
            create_radar_chart(
                radar_data, os.path.join(output_dir, "model_radar_comparison.png")
            )

    # Create a summary markdown document
    create_comparison_markdown(comparison_df, output_dir)

    # Log artifacts to MLflow
    with mlflow.start_run():
        for file in glob.glob(os.path.join(output_dir, "*")):
            mlflow.log_artifact(file)

        mlflow.set_tag("artifact_type", "model_comparison")


def create_radar_chart(data, output_path):
    """
    Create a radar chart for model comparison.

    Args:
        data (DataFrame): DataFrame with models as rows and metrics as columns
        output_path (str): Path to save the radar chart
    """
    # Number of metrics
    metrics = data.columns.tolist()
    num_metrics = len(metrics)

    # Number of models
    models = data.index.tolist()

    # Create angles for each metric
    angles = np.linspace(0, 2 * np.pi, num_metrics, endpoint=False).tolist()
    angles += angles[:1]  # Close the polygon

    # Create figure
    _, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(polar=True))

    # Add each model to the chart
    for i, model in enumerate(models):
        values = data.loc[model].tolist()
        values += values[:1]  # Close the polygon

        # Plot values
        ax.plot(angles, values, linewidth=2, label=model)
        ax.fill(angles, values, alpha=0.1)

    # Add metric labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metrics)

    # Add legend and title
    ax.legend(loc="upper right")
    plt.title("Model Comparison Radar Chart")

    # Save the chart
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def create_comparison_markdown(comparison_df, output_dir):
    """
    Create a markdown document summarizing model comparisons.

    Args:
        comparison_df (DataFrame): DataFrame with model comparison data
        output_dir (str): Directory to save the markdown file
    """
    # Filter to get the most complete runs for each model type
    best_runs = []
    for model_type, group in comparison_df.groupby("model_type"):
        # Find the run with the most metrics
        metric_counts = group.notna().sum(axis=1)
        best_run_idx = metric_counts.idxmax()
        best_runs.append(group.loc[best_run_idx])

    if not best_runs:
        return

    best_runs_df = pd.DataFrame(best_runs)

    # Create markdown content
    md_content = "# Model Comparison Summary\n\n"
    md_content += "## Performance Metrics\n\n"

    # Create table header
    md_content += "| Model |"

    accuracy_metrics = [
        col
        for col in best_runs_df.columns
        if col.startswith("test_") and col != "test_metrics"
    ]
    for metric in accuracy_metrics:
        md_content += f" {metric} |"

    md_content += "\n|" + " --- |" * (len(accuracy_metrics) + 1) + "\n"

    # Add rows for each model
    for _, row in best_runs_df.iterrows():
        md_content += f"| {row['model_type']} |"

        for metric in accuracy_metrics:
            if pd.notna(row.get(metric)):
                md_content += f" {row[metric]:.4f} |"
            else:
                md_content += " - |"

        md_content += "\n"

    # Add inference performance section
    md_content += "\n## Inference Performance\n\n"

    # Create table header
    md_content += "| Model |"

    inference_metrics = [
        "inference_latency_ms",
        "inference_throughput",
        "model_size_mb",
    ]
    for metric in inference_metrics:
        if metric in best_runs_df.columns:
            md_content += f" {metric} |"

    md_content += (
        "\n|"
        + " --- |"
        * (len([m for m in inference_metrics if m in best_runs_df.columns]) + 1)
        + "\n"
    )

    # Add rows for each model
    for _, row in best_runs_df.iterrows():
        md_content += f"| {row['model_type']} |"

        for metric in inference_metrics:
            if metric in best_runs_df.columns and pd.notna(row.get(metric)):
                if metric == "inference_latency_ms":
                    md_content += f" {row[metric]:.2f} ms |"
                elif metric == "inference_throughput":
                    md_content += f" {row[metric]:.2f} samples/s |"
                elif metric == "model_size_mb":
                    md_content += f" {row[metric]:.2f} MB |"
                else:
                    md_content += f" {row[metric]:.4f} |"
            else:
                md_content += " - |"

        md_content += "\n"

    # Add training information section if available
    if "training_time_seconds" in best_runs_df.columns:
        md_content += "\n## Training Information\n\n"

        # Create table header
        md_content += "| Model | Training Time |\n"
        md_content += "| --- | --- |\n"

        # Add rows for each model
        for _, row in best_runs_df.iterrows():
            md_content += f"| {row['model_type']} |"

            if pd.notna(row.get("training_time_seconds")):
                # Convert seconds to a readable format
                seconds = row["training_time_seconds"]
                if seconds < 60:
                    time_str = f"{seconds:.2f} seconds"
                elif seconds < 3600:
                    minutes = seconds / 60
                    time_str = f"{minutes:.2f} minutes"
                else:
                    hours = seconds / 3600
                    time_str = f"{hours:.2f} hours"

                md_content += f" {time_str} |\n"
            else:
                md_content += " - |\n"

    # Write markdown file
    md_path = os.path.join(output_dir, "model_comparison_summary.md")
    with open(md_path, "w") as f:
        f.write(md_content)


def main():
    parser = argparse.ArgumentParser(description="Log model experiments to MLflow")

    # MLflow setup
    parser.add_argument(
        "--tracking_uri", type=str, default="mlruns", help="MLflow tracking URI"
    )
    parser.add_argument(
        "--experiment_name",
        type=str,
        default="text_classification",
        help="MLflow experiment name",
    )

    # Subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Training parser
    train_parser = subparsers.add_parser("train", help="Log training metrics")
    train_parser.add_argument(
        "--model_dir",
        type=str,
        required=True,
        help="Directory containing the model files",
    )
    train_parser.add_argument(
        "--metrics_file", type=str, required=True, help="Path to the metrics JSON file"
    )
    train_parser.add_argument(
        "--artifacts_dir", type=str, help="Directory containing additional artifacts"
    )

    # Evaluation parser
    eval_parser = subparsers.add_parser("evaluate", help="Log evaluation metrics")
    eval_parser.add_argument(
        "--evaluation_file",
        type=str,
        required=True,
        help="Path to the evaluation results JSON file",
    )
    eval_parser.add_argument(
        "--run_id", type=str, help="Existing MLflow run ID to log to"
    )
    eval_parser.add_argument(
        "--artifacts_dir", type=str, help="Directory containing additional artifacts"
    )

    # Inference parser
    inference_parser = subparsers.add_parser("inference", help="Log inference metrics")
    inference_parser.add_argument(
        "--inference_file",
        type=str,
        required=True,
        help="Path to the inference results JSON file",
    )
    inference_parser.add_argument(
        "--run_id", type=str, help="Existing MLflow run ID to log to"
    )
    inference_parser.add_argument(
        "--artifacts_dir", type=str, help="Directory containing additional artifacts"
    )

    # Compare parser
    compare_parser = subparsers.add_parser(
        "compare", help="Create model comparison artifacts"
    )
    compare_parser.add_argument(
        "--output_dir",
        type=str,
        required=True,
        help="Directory to save comparison artifacts",
    )
    compare_parser.add_argument(
        "--model_types", type=str, nargs="+", help="List of model types to compare"
    )

    # Log complete run parser (training + evaluation + inference)
    complete_parser = subparsers.add_parser(
        "complete", help="Log a complete run with all metrics"
    )
    complete_parser.add_argument(
        "--model_dir",
        type=str,
        required=True,
        help="Directory containing the model files",
    )
    complete_parser.add_argument(
        "--training_metrics",
        type=str,
        required=True,
        help="Path to the training metrics JSON file",
    )
    complete_parser.add_argument(
        "--evaluation_file",
        type=str,
        required=True,
        help="Path to the evaluation results JSON file",
    )
    complete_parser.add_argument(
        "--inference_file",
        type=str,
        required=True,
        help="Path to the inference results JSON file",
    )
    complete_parser.add_argument(
        "--artifacts_dir", type=str, help="Directory containing additional artifacts"
    )

    args = parser.parse_args()

    # Setup MLflow
    experiment_id = setup_mlflow(args.tracking_uri, args.experiment_name)

    if args.command == "train":
        log_model_training(args.model_dir, args.metrics_file, args.artifacts_dir)

    elif args.command == "evaluate":
        log_model_evaluation(args.evaluation_file, args.run_id, args.artifacts_dir)

    elif args.command == "inference":
        log_inference_performance(args.inference_file, args.run_id, args.artifacts_dir)

    elif args.command == "compare":
        create_comparison_artifacts(experiment_id, args.output_dir, args.model_types)

    elif args.command == "complete":
        # Start with training
        run_id = log_model_training(args.model_dir, args.training_metrics)

        # Add evaluation metrics to the same run
        log_model_evaluation(args.evaluation_file, run_id)

        # Add inference metrics to the same run
        log_inference_performance(args.inference_file, run_id, args.artifacts_dir)

        print(f"Complete run logged with ID: {run_id}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
