"""
Evaluation metrics for OOD detection models.
"""

import numpy as np
from typing import Dict, List, Optional
import sklearn.metrics as skmetrics
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import os
from scipy import interpolate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OODMetrics:
    """
    Evaluation metrics for OOD detection.

    This class provides methods for computing various metrics
    for evaluating OOD detection performance.
    """

    def __init__(self):
        """Initialize OOD metrics calculator."""
        pass

    def compute_metrics(
        self,
        id_uncertainties: np.ndarray,
        ood_uncertainties: np.ndarray,
        id_labels: Optional[np.ndarray] = None,
        id_predictions: Optional[np.ndarray] = None,
        metric_names: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Compute OOD detection metrics.

        Args:
            id_uncertainties: Uncertainty scores for in-distribution examples
            ood_uncertainties: Uncertainty scores for out-of-distribution examples
            id_labels: Ground truth labels for in-distribution examples
            id_predictions: Predicted labels for in-distribution examples
            metric_names: List of metric names to compute

        Returns:
            metrics: Dictionary of metric values
        """
        if metric_names is None:
            metric_names = [
                "auroc",
                "aupr",
                "fpr_at_95_tpr",
                "detection_error",
                "accuracy",
                "f1",
                "precision",
                "recall",
            ]

        metrics = {}

        # Create binary labels for all examples
        # 0 for ID, 1 for OOD
        n_id = len(id_uncertainties)
        n_ood = len(ood_uncertainties)

        y_true = np.concatenate(
            [
                np.zeros(n_id, dtype=np.int32),  # ID examples
                np.ones(n_ood, dtype=np.int32),  # OOD examples
            ]
        )

        # Concatenate uncertainties
        y_score = np.concatenate([id_uncertainties, ood_uncertainties])

        # Compute OOD detection metrics
        if "auroc" in metric_names:
            metrics["auroc"] = self.compute_auroc(y_true, y_score)

        if "aupr" in metric_names:
            metrics["aupr"] = self.compute_aupr(y_true, y_score)

        if "fpr_at_95_tpr" in metric_names:
            metrics["fpr_at_95_tpr"] = self.compute_fpr_at_95_tpr(y_true, y_score)

        if "detection_error" in metric_names:
            metrics["detection_error"] = self.compute_detection_error(y_true, y_score)

        # Compute classification metrics (if labels and predictions provided)
        if id_labels is not None and id_predictions is not None:
            if "accuracy" in metric_names:
                metrics["accuracy"] = skmetrics.accuracy_score(
                    id_labels, id_predictions
                )

            if "f1" in metric_names:
                metrics["f1"] = skmetrics.f1_score(
                    id_labels, id_predictions, average="weighted"
                )

            if "precision" in metric_names:
                metrics["precision"] = skmetrics.precision_score(
                    id_labels, id_predictions, average="weighted"
                )

            if "recall" in metric_names:
                metrics["recall"] = skmetrics.recall_score(
                    id_labels, id_predictions, average="weighted"
                )

            if "confusion_matrix" in metric_names:
                metrics["confusion_matrix"] = skmetrics.confusion_matrix(
                    id_labels, id_predictions
                ).tolist()

        return metrics

    def compute_auroc(self, y_true: np.ndarray, y_score: np.ndarray) -> float:
        """
        Compute Area Under the Receiver Operating Characteristic curve.

        Args:
            y_true: Binary labels (0 for ID, 1 for OOD)
            y_score: Uncertainty scores

        Returns:
            auroc: AUROC score
        """
        return skmetrics.roc_auc_score(y_true, y_score)

    def compute_aupr(self, y_true: np.ndarray, y_score: np.ndarray) -> float:
        """
        Compute Area Under the Precision-Recall curve.

        Args:
            y_true: Binary labels (0 for ID, 1 for OOD)
            y_score: Uncertainty scores

        Returns:
            aupr: AUPR score
        """
        precision, recall, _ = skmetrics.precision_recall_curve(y_true, y_score)
        return skmetrics.auc(recall, precision)

    def compute_fpr_at_95_tpr(self, y_true: np.ndarray, y_score: np.ndarray) -> float:
        """
        Compute False Positive Rate at 95% True Positive Rate.

        Args:
            y_true: Binary labels (0 for ID, 1 for OOD)
            y_score: Uncertainty scores

        Returns:
            fpr_at_95_tpr: FPR at 95% TPR
        """
        fpr, tpr, thresholds = skmetrics.roc_curve(y_true, y_score)

        # Find the threshold that gives TPR closest to 95%
        target_tpr = 0.95
        abs_diff = np.abs(tpr - target_tpr)
        idx = np.argmin(abs_diff)

        # If TPR is exactly 95%, return the corresponding FPR
        if abs_diff[idx] < 1e-10:
            return fpr[idx]

        # Otherwise, interpolate to get the exact FPR at 95% TPR
        interp_function = interpolate.interp1d(tpr, fpr)
        try:
            return float(interp_function(target_tpr))
        except (ValueError, TypeError):
            # If interpolation fails, return the closest value
            return fpr[idx]

    def compute_detection_error(self, y_true: np.ndarray, y_score: np.ndarray) -> float:
        """
        Compute minimum detection error.

        This is defined as the minimum average of the false positive rate
        and the false negative rate.

        Args:
            y_true: Binary labels (0 for ID, 1 for OOD)
            y_score: Uncertainty scores

        Returns:
            detection_error: Minimum detection error
        """
        fpr, tpr, thresholds = skmetrics.roc_curve(y_true, y_score)

        # Detection error = 0.5 * (FPR + FNR) = 0.5 * (FPR + (1 - TPR))
        detection_error = 0.5 * (fpr + (1 - tpr))

        # Return the minimum detection error
        return min(detection_error)

    def get_threshold_for_fpr(
        self,
        id_uncertainties: np.ndarray,
        ood_uncertainties: np.ndarray,
        target_fpr: float = 0.05,
    ) -> float:
        """
        Get the threshold for a target false positive rate.

        Args:
            id_uncertainties: Uncertainty scores for ID examples
            ood_uncertainties: Uncertainty scores for OOD examples
            target_fpr: Target false positive rate

        Returns:
            threshold: Threshold for the target FPR
        """
        # Create binary labels for all examples
        n_id = len(id_uncertainties)
        n_ood = len(ood_uncertainties)

        y_true = np.concatenate(
            [
                np.zeros(n_id, dtype=np.int32),  # ID examples
                np.ones(n_ood, dtype=np.int32),  # OOD examples
            ]
        )

        # Concatenate uncertainties
        y_score = np.concatenate([id_uncertainties, ood_uncertainties])

        # Compute ROC curve
        fpr, tpr, thresholds = skmetrics.roc_curve(y_true, y_score)

        # Find the threshold that gives FPR closest to target
        abs_diff = np.abs(fpr - target_fpr)
        idx = np.argmin(abs_diff)

        return thresholds[idx]

    def plot_roc_curve(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
        title: str = "ROC Curve",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """
        Plot the ROC curve.

        Args:
            y_true: Binary labels (0 for ID, 1 for OOD)
            y_score: Uncertainty scores
            title: Plot title
            save_path: Path to save the plot

        Returns:
            fig: The figure object
        """
        fpr, tpr, _ = skmetrics.roc_curve(y_true, y_score)
        auroc = skmetrics.roc_auc_score(y_true, y_score)

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

        if save_path is not None:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)

        return fig

    def plot_pr_curve(
        self,
        y_true: np.ndarray,
        y_score: np.ndarray,
        title: str = "Precision-Recall Curve",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """
        Plot the Precision-Recall curve.

        Args:
            y_true: Binary labels (0 for ID, 1 for OOD)
            y_score: Uncertainty scores
            title: Plot title
            save_path: Path to save the plot

        Returns:
            fig: The figure object
        """
        precision, recall, _ = skmetrics.precision_recall_curve(y_true, y_score)
        aupr = skmetrics.auc(recall, precision)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.plot(recall, precision, lw=2, label=f"AUPR = {aupr:.3f}")
        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title(title)
        ax.legend(loc="lower left")
        ax.grid(True, alpha=0.3)

        if save_path is not None:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)

        return fig

    def plot_score_distributions(
        self,
        id_uncertainties: np.ndarray,
        ood_uncertainties: np.ndarray,
        title: str = "Uncertainty Score Distributions",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """
        Plot the distributions of uncertainty scores for ID and OOD examples.

        Args:
            id_uncertainties: Uncertainty scores for ID examples
            ood_uncertainties: Uncertainty scores for OOD examples
            title: Plot title
            save_path: Path to save the plot

        Returns:
            fig: The figure object
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot ID and OOD distributions
        sns.histplot(
            id_uncertainties,
            color="blue",
            alpha=0.6,
            label="In-Distribution",
            kde=True,
            stat="density",
            ax=ax,
        )
        sns.histplot(
            ood_uncertainties,
            color="red",
            alpha=0.6,
            label="Out-of-Distribution",
            kde=True,
            stat="density",
            ax=ax,
        )

        # Compute the threshold for 95% TPR
        n_id = len(id_uncertainties)
        n_ood = len(ood_uncertainties)

        y_true = np.concatenate(
            [np.zeros(n_id, dtype=np.int32), np.ones(n_ood, dtype=np.int32)]
        )

        y_score = np.concatenate([id_uncertainties, ood_uncertainties])

        fpr, tpr, thresholds = skmetrics.roc_curve(y_true, y_score)

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

        if save_path is not None:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)

        return fig

    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        labels: Optional[List[str]] = None,
        title: str = "Confusion Matrix",
        save_path: Optional[str] = None,
    ) -> plt.Figure:
        """
        Plot the confusion matrix.

        Args:
            y_true: Ground truth labels
            y_pred: Predicted labels
            labels: Class labels
            title: Plot title
            save_path: Path to save the plot

        Returns:
            fig: The figure object
        """
        cm = skmetrics.confusion_matrix(y_true, y_pred)

        fig, ax = plt.subplots(figsize=(10, 8))

        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=labels if labels else "auto",
            yticklabels=labels if labels else "auto",
            ax=ax,
        )

        ax.set_xlabel("Predicted Labels")
        ax.set_ylabel("True Labels")
        ax.set_title(title)

        if save_path is not None:
            plt.savefig(save_path, bbox_inches="tight", dpi=300)

        return fig

    def generate_summary_report(
        self, metrics: Dict[str, float], model_name: str, output_dir: str
    ) -> str:
        """
        Generate a summary report of the metrics.

        Args:
            metrics: Dictionary of metric values
            model_name: Name of the model
            output_dir: Directory to save the report

        Returns:
            report_path: Path to the generated report
        """
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, f"{model_name}_summary.txt")

        with open(report_path, "w") as f:
            f.write(f"Summary Report for {model_name}\n")
            f.write("=" * 50 + "\n\n")

            f.write("OOD Detection Metrics:\n")
            f.write("-" * 30 + "\n")

            ood_metrics = ["auroc", "aupr", "fpr_at_95_tpr", "detection_error"]
            for metric in ood_metrics:
                if metric in metrics:
                    f.write(f"{metric.upper()}: {metrics[metric]:.4f}\n")

            f.write("\nClassification Metrics:\n")
            f.write("-" * 30 + "\n")

            cls_metrics = ["accuracy", "f1", "precision", "recall"]
            for metric in cls_metrics:
                if metric in metrics:
                    f.write(f"{metric.capitalize()}: {metrics[metric]:.4f}\n")

        logger.info(f"Summary report saved to {report_path}")
        return report_path
