"""
Visualization utilities for OOD detection results.
"""

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from typing import Dict, List
import os
import logging
from sklearn.metrics import roc_curve, precision_recall_curve, confusion_matrix
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Visualizer:
    """
    Visualization utilities for OOD detection results.
    """

    def __init__(self, output_dir: str = "visualizations"):
        """
        Initialize visualizer.

        Args:
            output_dir: Directory to save visualizations
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_roc_curve(
        self,
        id_uncertainties: np.ndarray,
        ood_uncertainties: np.ndarray,
        model_name: str = "Model",
        title: str = "ROC Curve",
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot ROC curve for OOD detection.

        Args:
            id_uncertainties: Uncertainty scores for ID examples
            ood_uncertainties: Uncertainty scores for OOD examples
            model_name: Name of the model
            title: Title of the plot
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Create binary labels
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
        fpr, tpr, _ = roc_curve(y_true, y_score)

        # Compute AUROC
        auroc = self._calculate_auroc(fpr, tpr)

        # Create figure
        fig, ax = plt.subplots(figsize=(8, 6))

        ax.plot(fpr, tpr, lw=2, label=f"AUROC = {auroc:.3f}")
        ax.plot([0, 1], [0, 1], "k--", lw=2)

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title(f"{title} - {model_name}")
        ax.legend(loc="lower right")
        ax.grid(True, alpha=0.3)

        if save:
            save_path = os.path.join(
                self.output_dir, f"{model_name.lower().replace(' ', '_')}_roc_curve.png"
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved ROC curve to {save_path}")

        return fig

    def plot_pr_curve(
        self,
        id_uncertainties: np.ndarray,
        ood_uncertainties: np.ndarray,
        model_name: str = "Model",
        title: str = "Precision-Recall Curve",
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot Precision-Recall curve for OOD detection.

        Args:
            id_uncertainties: Uncertainty scores for ID examples
            ood_uncertainties: Uncertainty scores for OOD examples
            model_name: Name of the model
            title: Title of the plot
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Create binary labels
        n_id = len(id_uncertainties)
        n_ood = len(ood_uncertainties)

        y_true = np.concatenate(
            [np.zeros(n_id, dtype=np.int32), np.ones(n_ood, dtype=np.int32)]
        )

        # Concatenate uncertainties
        y_score = np.concatenate([id_uncertainties, ood_uncertainties])

        # Compute PR curve
        precision, recall, _ = precision_recall_curve(y_true, y_score)

        # Compute AUPR
        aupr = self._calculate_aupr(precision, recall)

        # Create figure
        fig, ax = plt.subplots(figsize=(8, 6))

        ax.plot(recall, precision, lw=2, label=f"AUPR = {aupr:.3f}")

        ax.set_xlim([0.0, 1.0])
        ax.set_ylim([0.0, 1.05])
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title(f"{title} - {model_name}")
        ax.legend(loc="lower left")
        ax.grid(True, alpha=0.3)

        if save:
            save_path = os.path.join(
                self.output_dir, f"{model_name.lower().replace(' ', '_')}_pr_curve.png"
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved PR curve to {save_path}")

        return fig

    def plot_score_distributions(
        self,
        id_uncertainties: np.ndarray,
        ood_uncertainties: np.ndarray,
        model_name: str = "Model",
        title: str = "Uncertainty Score Distributions",
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot distributions of uncertainty scores.

        Args:
            id_uncertainties: Uncertainty scores for ID examples
            ood_uncertainties: Uncertainty scores for OOD examples
            model_name: Name of the model
            title: Title of the plot
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Create figure
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

        fpr, tpr, thresholds = roc_curve(y_true, y_score)

        # Find the threshold for 95% TPR
        target_tpr = 0.95
        idx = np.argmin(np.abs(tpr - target_tpr))
        threshold = thresholds[idx]

        # Calculate FPR at this threshold
        fpr_at_threshold = fpr[idx]

        # Add threshold line
        ax.axvline(
            threshold,
            color="green",
            linestyle="--",
            label=f"Threshold at 95% TPR (FPR={fpr_at_threshold:.3f})",
        )

        ax.set_xlabel("Uncertainty Score")
        ax.set_ylabel("Density")
        ax.set_title(f"{title} - {model_name}")
        ax.legend()

        if save:
            save_path = os.path.join(
                self.output_dir,
                f"{model_name.lower().replace(' ', '_')}_score_distributions.png",
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved score distributions to {save_path}")

        return fig

    def plot_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        class_names: List[str],
        model_name: str = "Model",
        title: str = "Confusion Matrix",
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot confusion matrix.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            class_names: Names of classes
            model_name: Name of the model
            title: Title of the plot
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Compute confusion matrix
        cm = confusion_matrix(y_true, y_pred)

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))

        # Plot confusion matrix
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=class_names,
            yticklabels=class_names,
            ax=ax,
        )

        ax.set_xlabel("Predicted Labels")
        ax.set_ylabel("True Labels")
        ax.set_title(f"{title} - {model_name}")

        if save:
            save_path = os.path.join(
                self.output_dir,
                f"{model_name.lower().replace(' ', '_')}_confusion_matrix.png",
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved confusion matrix to {save_path}")

        return fig

    def plot_feature_embeddings(
        self,
        id_features: np.ndarray,
        ood_features: np.ndarray,
        method: str = "tsne",
        perplexity: int = 30,
        n_components: int = 2,
        model_name: str = "Model",
        title: str = "Feature Embeddings",
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot feature embeddings using dimensionality reduction.

        Args:
            id_features: Features for ID examples
            ood_features: Features for OOD examples
            method: Dimensionality reduction method ('tsne' or 'pca')
            perplexity: Perplexity parameter for t-SNE
            n_components: Number of components for dimensionality reduction
            model_name: Name of the model
            title: Title of the plot
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Combine features
        all_features = np.vstack([id_features, ood_features])

        # Create labels (0 for ID, 1 for OOD)
        labels = np.concatenate(
            [
                np.zeros(len(id_features), dtype=np.int32),
                np.ones(len(ood_features), dtype=np.int32),
            ]
        )

        # Apply dimensionality reduction
        if method.lower() == "tsne":
            reducer = TSNE(
                n_components=n_components, perplexity=perplexity, random_state=42
            )
            reduced_features = reducer.fit_transform(all_features)
            method_name = f"t-SNE (perplexity={perplexity})"
        elif method.lower() == "pca":
            reducer = PCA(n_components=n_components, random_state=42)
            reduced_features = reducer.fit_transform(all_features)
            method_name = f"PCA (n_components={n_components})"
        else:
            raise ValueError(f"Unsupported method: {method}")

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 8))

        # Scatter plot
        scatter = ax.scatter(
            reduced_features[:, 0],
            reduced_features[:, 1],
            c=labels,
            cmap="coolwarm",
            alpha=0.7,
            s=30,
        )

        # Add legend
        ax.legend(
            handles=scatter.legend_elements()[0],
            labels=["In-Distribution", "Out-of-Distribution"],
            loc="upper right",
        )

        ax.set_xlabel("Component 1")
        ax.set_ylabel("Component 2")
        ax.set_title(f"{title} - {model_name}\n({method_name})")
        ax.grid(True, alpha=0.3)

        if save:
            save_path = os.path.join(
                self.output_dir,
                f"{model_name.lower().replace(' ', '_')}_{method.lower()}_embeddings.png",
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved feature embeddings to {save_path}")

        return fig

    def plot_model_comparison(
        self,
        model_metrics: Dict[str, Dict[str, float]],
        metric_name: str = "auroc",
        title: str = "Model Comparison",
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot comparison of different models based on a metric.

        Args:
            model_metrics: Dictionary of metrics for different models
            metric_name: Name of the metric to compare
            title: Title of the plot
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Extract model names and metric values
        models = list(model_metrics.keys())
        values = [model_metrics[model].get(metric_name, 0) for model in models]

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))

        # Bar plot
        bars = ax.bar(models, values, color="skyblue", alpha=0.7)

        # Add value labels on top of bars
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + 0.01,
                f"{height:.3f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

        ax.set_xlabel("Model")
        ax.set_ylabel(metric_name.upper())
        ax.set_title(f"{title} - {metric_name.upper()}")
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3, axis="y")

        # Add line at y=0.5 for reference (random classifier)
        if metric_name.lower() in [
            "auroc",
            "aupr",
            "accuracy",
            "f1",
            "precision",
            "recall",
        ]:
            ax.axhline(
                0.5, color="red", linestyle="--", alpha=0.5, label="Random Classifier"
            )
            ax.legend()

        if save:
            save_path = os.path.join(
                self.output_dir, f"model_comparison_{metric_name.lower()}.png"
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved model comparison to {save_path}")

        return fig

    def plot_multi_metric_comparison(
        self,
        model_metrics: Dict[str, Dict[str, float]],
        metrics: List[str] = ["auroc", "aupr", "fpr_at_95_tpr", "accuracy"],
        title: str = "Multi-Metric Model Comparison",
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot comparison of different models based on multiple metrics.

        Args:
            model_metrics: Dictionary of metrics for different models
            metrics: List of metrics to compare
            title: Title of the plot
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Extract model names
        models = list(model_metrics.keys())

        # Create a DataFrame for easier plotting
        data = []
        for model in models:
            for metric in metrics:
                value = model_metrics[model].get(metric, 0)
                data.append({"Model": model, "Metric": metric.upper(), "Value": value})

        df = pd.DataFrame(data)

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))

        # Bar plot
        sns.barplot(x="Model", y="Value", hue="Metric", data=df, ax=ax)

        ax.set_xlabel("Model")
        ax.set_ylabel("Value")
        ax.set_title(title)
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3, axis="y")

        # Adjust legend
        ax.legend(title="Metric", bbox_to_anchor=(1.05, 1), loc="upper left")

        plt.tight_layout()

        if save:
            save_path = os.path.join(
                self.output_dir, "multi_metric_model_comparison.png"
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved multi-metric model comparison to {save_path}")

        return fig

    def plot_uncertainty_threshold_impact(
        self,
        id_uncertainties: np.ndarray,
        ood_uncertainties: np.ndarray,
        model_name: str = "Model",
        title: str = "Impact of Uncertainty Threshold",
        num_thresholds: int = 100,
        save: bool = True,
    ) -> plt.Figure:
        """
        Plot the impact of different uncertainty thresholds.

        Args:
            id_uncertainties: Uncertainty scores for ID examples
            ood_uncertainties: Uncertainty scores for OOD examples
            model_name: Name of the model
            title: Title of the plot
            num_thresholds: Number of thresholds to evaluate
            save: Whether to save the plot

        Returns:
            fig: Figure object
        """
        # Create binary labels
        n_id = len(id_uncertainties)
        n_ood = len(ood_uncertainties)

        y_true = np.concatenate(
            [np.zeros(n_id, dtype=np.int32), np.ones(n_ood, dtype=np.int32)]
        )

        # Concatenate uncertainties
        y_score = np.concatenate([id_uncertainties, ood_uncertainties])

        # Compute ROC curve
        fpr, tpr, thresholds = roc_curve(y_true, y_score)

        # Calculate Detection Error = 0.5 * (1 - TPR + FPR)
        detection_error = 0.5 * (1 - tpr + fpr)

        # Find minimum detection error
        min_idx = np.argmin(detection_error)
        min_threshold = thresholds[min_idx]
        min_error = detection_error[min_idx]

        # Find threshold for 95% TPR
        target_tpr = 0.95
        tpr95_idx = np.argmin(np.abs(tpr - target_tpr))
        tpr95_threshold = thresholds[tpr95_idx]
        tpr95_fpr = fpr[tpr95_idx]

        # Create figure
        fig, ax1 = plt.subplots(figsize=(12, 8))

        # Plot TPR and FPR
        ax1.plot(thresholds, tpr, "b-", label="TPR")
        ax1.plot(thresholds, fpr, "r-", label="FPR")
        ax1.set_xlabel("Uncertainty Threshold")
        ax1.set_ylabel("Rate")
        ax1.set_title(f"{title} - {model_name}")

        # Add detection error on secondary y-axis
        ax2 = ax1.twinx()
        ax2.plot(thresholds, detection_error, "g-", label="Detection Error")
        ax2.set_ylabel("Detection Error", color="g")

        # Mark minimum detection error
        ax1.axvline(min_threshold, color="black", linestyle="--")
        ax1.text(
            min_threshold,
            0.5,
            f"Min Error: {min_error:.3f}\nThreshold: {min_threshold:.3f}",
            ha="right",
            va="center",
            bbox=dict(facecolor="white", alpha=0.8),
        )

        # Mark 95% TPR threshold
        ax1.axvline(tpr95_threshold, color="purple", linestyle=":")
        ax1.text(
            tpr95_threshold,
            0.3,
            f"95% TPR\nFPR: {tpr95_fpr:.3f}\nThreshold: {tpr95_threshold:.3f}",
            ha="left",
            va="center",
            bbox=dict(facecolor="white", alpha=0.8),
        )

        # Combine legends
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

        if save:
            save_path = os.path.join(
                self.output_dir,
                f"{model_name.lower().replace(' ', '_')}_threshold_impact.png",
            )
            plt.savefig(save_path, bbox_inches="tight", dpi=300)
            logger.info(f"Saved threshold impact plot to {save_path}")

        return fig

    def _calculate_auroc(self, fpr: np.ndarray, tpr: np.ndarray) -> float:
        """
        Calculate AUROC from FPR and TPR.

        Args:
            fpr: False positive rates
            tpr: True positive rates

        Returns:
            auroc: Area under ROC curve
        """
        # Sort by increasing FPR
        idx = np.argsort(fpr)
        fpr_sorted = fpr[idx]
        tpr_sorted = tpr[idx]

        # Calculate AUROC using trapezoidal rule
        auroc = np.trapz(tpr_sorted, fpr_sorted)

        return auroc

    def _calculate_aupr(self, precision: np.ndarray, recall: np.ndarray) -> float:
        """
        Calculate AUPR from precision and recall.

        Args:
            precision: Precision values
            recall: Recall values

        Returns:
            aupr: Area under PR curve
        """
        # Sort by increasing recall
        idx = np.argsort(recall)
        recall_sorted = recall[idx]
        precision_sorted = precision[idx]

        # Calculate AUPR using trapezoidal rule
        aupr = np.trapz(precision_sorted, recall_sorted)

        return aupr
