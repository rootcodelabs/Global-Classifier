"""
MLflow logging utilities for OOD detection experiments.
"""

import mlflow
import os
import json
import logging
from typing import Dict, List, Any, Optional
import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MLflowLogger:
    """
    MLflow logger for OOD detection experiments.

    This class provides methods for logging metrics, parameters,
    artifacts, and model information to MLflow.
    """

    def __init__(
        self,
        experiment_name: str,
        tracking_uri: Optional[str] = None,
        model_dir: str = "models",
        artifact_dir: str = "artifacts",
        create_dirs: bool = True,
    ):
        """
        Initialize MLflow logger.

        Args:
            experiment_name: Name of the MLflow experiment
            tracking_uri: MLflow tracking URI (None for local)
            model_dir: Directory to save models
            artifact_dir: Directory to save artifacts
            create_dirs: Whether to create directories
        """
        self.experiment_name = experiment_name

        # Set tracking URI if provided
        if tracking_uri:
            mlflow.set_tracking_uri(tracking_uri)

        # Set up directories
        self.model_dir = model_dir
        self.artifact_dir = artifact_dir

        if create_dirs:
            os.makedirs(model_dir, exist_ok=True)
            os.makedirs(artifact_dir, exist_ok=True)

        # Get or create experiment
        try:
            self.experiment_id = mlflow.create_experiment(experiment_name)
            logger.info(f"Created new experiment: {experiment_name}")
        except Exception as e:
            # If experiment already exists, get its ID
            logger.warning(f"Experiment '{experiment_name}' already exists: {e}")
            self.experiment_id = mlflow.get_experiment_by_name(
                experiment_name
            ).experiment_id
            logger.info(f"Using existing experiment: {experiment_name}")

    def start_run(
        self, run_name: Optional[str] = None, tags: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Start a new MLflow run.

        Args:
            run_name: Name of the run
            tags: Additional tags for the run

        Returns:
            run_id: The ID of the run
        """
        # End any existing active run first
        if mlflow.active_run() is not None:
            logger.warning("Ending existing active MLflow run")
            mlflow.end_run()

        mlflow.start_run(experiment_id=self.experiment_id, run_name=run_name, tags=tags)

        run_id = mlflow.active_run().info.run_id
        logger.info(f"Started MLflow run: {run_id}")

        return run_id

    def end_run(self):
        """End the current MLflow run."""
        try:
            if mlflow.active_run() is not None:
                mlflow.end_run()
                logger.info("Ended MLflow run")
            else:
                logger.info("No active MLflow run to end")
        except Exception as e:
            logger.warning(f"Error ending MLflow run: {e}")

    def log_params(self, params: Dict[str, Any]):
        """
        Log parameters to MLflow.

        Args:
            params: Dictionary of parameters
        """
        # Convert non-string parameters to strings
        params_str = {}
        for k, v in params.items():
            if isinstance(v, (dict, list, tuple)):
                params_str[k] = json.dumps(v)
            else:
                params_str[k] = str(v)

        mlflow.log_params(params_str)
        logger.info(f"Logged {len(params)} parameters")

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """
        Log metrics to MLflow.

        Args:
            metrics: Dictionary of metrics
            step: Step number
        """
        mlflow.log_metrics(metrics, step=step)
        logger.info(f"Logged {len(metrics)} metrics")

    def log_model(
        self,
        model: tf.keras.Model,
        model_name: str,
        signature: Optional[Any] = None,
        conda_env: Optional[Dict[str, Any]] = None,
        save_format: str = "tf",
    ):
        """
        Log model to MLflow.

        Args:
            model: TensorFlow model
            model_name: Name of the model
            signature: MLflow model signature
            conda_env: Conda environment specification
            save_format: Format to save the model
        """
        # Save model locally first
        model_path = os.path.join(self.model_dir, model_name)

        if save_format == "tf":
            # Save as TensorFlow SavedModel
            model.save(model_path, save_format="tf")

            # Log model to MLflow
            mlflow.tensorflow.log_model(
                tf_saved_model_dir=model_path,
                tf_meta_graph_tags=None,
                tf_signature_def_key="serving_default",
                artifact_path=model_name,
                signature=signature,
                conda_env=conda_env,
            )
        elif save_format == "h5":
            # Save as Keras H5 model
            model.save(model_path + ".h5", save_format="h5")

            # Log model to MLflow
            mlflow.keras.log_model(
                keras_model=model,
                artifact_path=model_name,
                signature=signature,
                conda_env=conda_env,
            )
        else:
            raise ValueError(f"Unsupported save format: {save_format}")

        logger.info(f"Logged model: {model_name}")

    def log_figure(self, figure: plt.Figure, artifact_path: str):
        """
        Log a matplotlib figure to MLflow.

        Args:
            figure: Matplotlib figure
            artifact_path: Path where the figure will be saved
        """
        # Save figure to a buffer
        buf = io.BytesIO()
        figure.savefig(buf, format="png", dpi=300, bbox_inches="tight")
        buf.seek(0)

        # Convert to PIL Image
        img = Image.open(buf)

        # Save temporarily
        tmp_path = os.path.join(self.artifact_dir, os.path.basename(artifact_path))
        img.save(tmp_path)

        # Log to MLflow
        mlflow.log_artifact(tmp_path, os.path.dirname(artifact_path))

        # Clean up
        plt.close(figure)
        os.remove(tmp_path)

        logger.info(f"Logged figure: {artifact_path}")

    def log_artifact(self, local_path: str, artifact_path: Optional[str] = None):
        """
        Log an artifact to MLflow.

        Args:
            local_path: Local path to the artifact
            artifact_path: Path within MLflow where the artifact will be saved
        """
        mlflow.log_artifact(local_path, artifact_path)
        logger.info(f"Logged artifact: {local_path}")

    def log_dict(self, dictionary: Dict[str, Any], artifact_path: str):
        """
        Log a dictionary to MLflow as a JSON file.

        Args:
            dictionary: Dictionary to log
            artifact_path: Path where the JSON will be saved
        """
        mlflow.log_dict(dictionary, artifact_path)
        logger.info(f"Logged dictionary: {artifact_path}")

    def log_confusion_matrix(
        self,
        confusion_matrix: np.ndarray,
        class_names: List[str],
        title: str = "Confusion Matrix",
        artifact_path: str = "confusion_matrix.png",
    ):
        """
        Log a confusion matrix to MLflow.

        Args:
            confusion_matrix: Numpy array of confusion matrix
            class_names: List of class names
            title: Title of the plot
            artifact_path: Path where the figure will be saved
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))

        import seaborn as sns

        sns.heatmap(
            confusion_matrix,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=class_names,
            yticklabels=class_names,
            ax=ax,
        )

        ax.set_xlabel("Predicted Labels")
        ax.set_ylabel("True Labels")
        ax.set_title(title)

        # Log the figure
        self.log_figure(fig, artifact_path)

    def log_roc_curve(
        self,
        fpr: np.ndarray,
        tpr: np.ndarray,
        auroc: float,
        title: str = "ROC Curve",
        artifact_path: str = "roc_curve.png",
    ):
        """
        Log a ROC curve to MLflow.

        Args:
            fpr: False positive rates
            tpr: True positive rates
            auroc: Area under ROC curve
            title: Title of the plot
            artifact_path: Path where the figure will be saved
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(8, 6))

        ax.plot(fpr, tpr, lw=2, label=f"AUROC = {auroc:.3f}")
        ax.plot([0, 1], [0, 1], "k--", lw=2)

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title(title)
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3)

        # Log the figure
        self.log_figure(fig, artifact_path)

    def log_pr_curve(
        self,
        precision: np.ndarray,
        recall: np.ndarray,
        aupr: float,
        title: str = "Precision-Recall Curve",
        artifact_path: str = "pr_curve.png",
    ):
        """
        Log a Precision-Recall curve to MLflow.

        Args:
            precision: Precision values
            recall: Recall values
            aupr: Area under PR curve
            title: Title of the plot
            artifact_path: Path where the figure will be saved
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(8, 6))

        ax.plot(recall, precision, lw=2, label=f"AUPR = {aupr:.3f}")

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title(title)
        ax.legend(loc="lower left")
        ax.grid(True, alpha=0.3)

        # Log the figure
        self.log_figure(fig, artifact_path)

    def log_score_distributions(
        self,
        id_scores: np.ndarray,
        ood_scores: np.ndarray,
        title: str = "Uncertainty Score Distributions",
        artifact_path: str = "score_distributions.png",
    ):
        """
        Log distributions of uncertainty scores for ID and OOD examples.

        Args:
            id_scores: Uncertainty scores for ID examples
            ood_scores: Uncertainty scores for OOD examples
            title: Title of the plot
            artifact_path: Path where the figure will be saved
        """
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        import seaborn as sns

        sns.histplot(
            id_scores,
            color="blue",
            alpha=0.6,
            label="In-Distribution",
            kde=True,
            stat="density",
            ax=ax,
        )
        sns.histplot(
            ood_scores,
            color="red",
            alpha=0.6,
            label="Out-of-Distribution",
            kde=True,
            stat="density",
            ax=ax,
        )

        # Compute the threshold for 95% TPR
        n_id = len(id_scores)
        n_ood = len(ood_scores)

        y_true = np.concatenate(
            [np.zeros(n_id, dtype=np.int32), np.ones(n_ood, dtype=np.int32)]
        )

        y_score = np.concatenate([id_scores, ood_scores])

        from sklearn.metrics import roc_curve

        fpr, tpr, thresholds = roc_curve(y_true, y_score)

        # Find the threshold for 95% TPR
        target_tpr = 0.95
        idx = np.argmin(np.abs(tpr - target_tpr))
        threshold = thresholds[idx]

        # Add threshold line
        ax.axvline(
            threshold, color="green", linestyle="--", label="Threshold at 95% TPR"
        )

        ax.set_xlabel("Uncertainty Score")
        ax.set_ylabel("Density")
        ax.set_title(title)
        ax.legend()

        # Log the figure
        self.log_figure(fig, artifact_path)

    def log_training_history(
        self,
        history: Dict[str, List[float]],
        metrics: List[str] = None,
        title: str = "Training History",
        artifact_path: str = "training_history.png",
    ):
        """
        Log training history to MLflow.

        Args:
            history: Dictionary of training history
            metrics: List of metrics to plot
            title: Title of the plot
            artifact_path: Path where the figure will be saved
        """
        if metrics is None:
            # Use all metrics except validation metrics
            metrics = [m for m in history.keys() if not m.startswith("val_")]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        epochs = range(1, len(history[metrics[0]]) + 1)

        for metric in metrics:
            ax.plot(epochs, history[metric], label=f"Training {metric}")

            # Plot validation metrics if available
            val_metric = f"val_{metric}"
            if val_metric in history:
                ax.plot(
                    epochs,
                    history[val_metric],
                    linestyle="--",
                    label=f"Validation {metric}",
                )

        ax.set_xlabel("Epoch")
        ax.set_ylabel("Value")
        ax.set_title(title)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Log the figure
        self.log_figure(fig, artifact_path)

    def log_model_summary(
        self, model: tf.keras.Model, artifact_path: str = "model_summary.txt"
    ):
        """
        Log model summary to MLflow.

        Args:
            model: TensorFlow model
            artifact_path: Path where the summary will be saved
        """
        # Create a string IO to capture the summary
        import io

        summary_io = io.StringIO()

        # Write model summary
        model.summary(print_fn=lambda x: summary_io.write(x + "\n"))

        # Save to a temp file
        tmp_path = os.path.join(self.artifact_dir, os.path.basename(artifact_path))
        with open(tmp_path, "w") as f:
            f.write(summary_io.getvalue())

        # Log to MLflow
        mlflow.log_artifact(tmp_path, os.path.dirname(artifact_path))

        # Clean up
        os.remove(tmp_path)

        logger.info(f"Logged model summary: {artifact_path}")

    def log_experiment_summary(
        self,
        experiment_results: Dict[str, Dict[str, float]],
        artifact_path: str = "experiment_summary.json",
    ):
        """
        Log experiment summary to MLflow.

        Args:
            experiment_results: Dictionary of results for different models
            artifact_path: Path where the summary will be saved
        """
        mlflow.log_dict(experiment_results, artifact_path)
        logger.info(f"Logged experiment summary: {artifact_path}")
