"""
Implementation of SNGP + Energy model for enhanced OOD detection.
"""

import tensorflow as tf
from typing import Dict, Tuple, List
import numpy as np
import logging
from models.sngp_model import SNGPModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SNGPEnergyModel(SNGPModel):
    """
    Combined SNGP and Energy-based model for OOD detection.

    This model leverages both the distance-awareness of SNGP through
    Gaussian process posterior variance and the energy-based scoring
    to provide more robust OOD detection.
    """

    def __init__(
        self,
        pretrained_model: str = "xlm-roberta-base",
        num_labels: int = 2,
        hidden_dims: List[int] = None,
        dropout_rate: float = 0.1,
        spec_norm_bound: float = 0.9,
        gp_hidden_dim: int = 1024,
        gp_scale_random_features: bool = True,
        gp_normalize_input: bool = True,
        gp_cov_momentum: float = -1.0,
        gp_cov_ridge_penalty: float = 1.0,
        energy_temp: float = 1.0,
        alpha: float = 0.5,  # Weight for combining SNGP and Energy scores
    ):
        """
        Initialize the SNGP+Energy model.

        Args:
            pretrained_model: Pre-trained model name
            num_labels: Number of classes
            hidden_dims: Hidden layer dimensions
            dropout_rate: Dropout rate
            spec_norm_bound: Spectral normalization bound
            gp_hidden_dim: Dimension of GP random features
            gp_scale_random_features: Whether to scale GP random features
            gp_normalize_input: Whether to normalize GP inputs
            gp_cov_momentum: GP covariance momentum
            gp_cov_ridge_penalty: GP covariance ridge penalty
            energy_temp: Temperature parameter for energy score
            alpha: Weight for combining SNGP and Energy scores (0-1)
            **kwargs: Additional arguments
        """
        super().__init__(
            pretrained_model=pretrained_model,
            num_labels=num_labels,
            hidden_dims=hidden_dims,
            dropout_rate=dropout_rate,
            spec_norm_bound=spec_norm_bound,
            gp_hidden_dim=gp_hidden_dim,
            gp_scale_random_features=gp_scale_random_features,
            gp_normalize_input=gp_normalize_input,
            gp_cov_momentum=gp_cov_momentum,
            gp_cov_ridge_penalty=gp_cov_ridge_penalty,
        )

        self.energy_temp = energy_temp
        self.alpha = alpha

    def compute_energy(self, logits: tf.Tensor, temp: float = None) -> tf.Tensor:
        """
        Compute the energy score.

        Args:
            logits: Model logits
            temp: Temperature parameter (defaults to self.energy_temp)

        Returns:
            energy: Energy scores
        """
        if temp is None:
            temp = self.energy_temp

        # Scale logits by temperature
        logits_scaled = logits / temp

        # Compute energy score: -log(sum(exp(logits)))
        energy = -tf.math.log(tf.reduce_sum(tf.exp(logits_scaled), axis=-1))

        return energy

    def predict_with_uncertainty(
        self, inputs: Dict[str, tf.Tensor], normalize_uncertainty: bool = True, **kwargs
    ) -> Tuple[tf.Tensor, tf.Tensor]:
        """
        Predict with combined uncertainty estimation.

        Args:
            inputs: Input tensors
            normalize_uncertainty: Whether to normalize uncertainty scores
            **kwargs: Additional arguments

        Returns:
            predictions: Class predictions
            uncertainty: Combined uncertainty scores from SNGP and Energy
        """
        # Get logits and covariance matrix from SNGP
        logits, covmat = self(
            inputs, training=False, return_covmat=True, measure_inference_time=True
        )

        # Extract variance from the diagonal of covariance matrix
        sngp_variance = tf.linalg.diag_part(covmat)

        # Mean-field approximation for adjusted logits
        mean_field_factor = np.pi / 8.0
        logits_adjusted = logits / tf.sqrt(
            1.0 + mean_field_factor * sngp_variance[:, tf.newaxis]
        )

        # Get predictions from adjusted logits
        probabilities = tf.nn.softmax(logits_adjusted, axis=-1)
        predictions = tf.argmax(probabilities, axis=-1)

        # Compute energy scores
        energy = self.compute_energy(logits)

        # Normalize SNGP variance and energy if requested
        if normalize_uncertainty:
            # Min-max normalization for variance
            sngp_variance = self._normalize_scores(sngp_variance)

            # Min-max normalization for energy
            energy = self._normalize_scores(energy)

        # Combine SNGP variance and energy scores
        combined_uncertainty = self.alpha * sngp_variance + (1.0 - self.alpha) * energy

        return predictions, combined_uncertainty

    def _normalize_scores(self, scores: tf.Tensor) -> tf.Tensor:
        """
        Normalize scores to [0, 1] range using min-max normalization.

        Args:
            scores: Input scores

        Returns:
            normalized_scores: Normalized scores between 0 and 1
        """
        min_val = tf.reduce_min(scores)
        max_val = tf.reduce_max(scores)

        # Prevent division by zero
        range_val = tf.maximum(max_val - min_val, 1e-10)

        return (scores - min_val) / range_val

    def get_config(self):
        """Get model configuration."""
        config = super().get_config()
        config.update(
            {
                "energy_temp": self.energy_temp,
                "alpha": self.alpha,
            }
        )
        return config


class SNGPEnergyLoss(tf.keras.losses.Loss):
    """
    Loss function for the SNGP+Energy model.

    This loss combines cross-entropy with energy-based regularization
    for improved OOD detection.
    """

    def __init__(
        self,
        ood_label: int = -1,
        energy_margin: float = 10.0,
        energy_weight: float = 0.1,
    ):
        """
        Initialize the SNGP+Energy loss.

        Args:
            ood_label: Label used for OOD examples
            energy_margin: Margin for energy difference between ID and OOD
            energy_weight: Weight for energy loss term
            **kwargs: Additional arguments
        """
        super().__init__()
        self.ood_label = ood_label
        self.energy_margin = energy_margin
        self.energy_weight = energy_weight
        self.base_loss = tf.keras.losses.SparseCategoricalCrossentropy(
            from_logits=True, reduction=tf.keras.losses.Reduction.NONE
        )

    def call(self, y_true: tf.Tensor, y_pred: Tuple[tf.Tensor, tf.Tensor]) -> tf.Tensor:
        """
        Compute the SNGP+Energy loss.

        Args:
            y_true: Ground truth labels
            y_pred: Tuple of (logits, covmat)

        Returns:
            loss: Combined loss value
        """
        # Unpack predictions (may be just logits during training)
        if isinstance(y_pred, tuple) and len(y_pred) == 2:
            logits, _ = y_pred
        else:
            logits = y_pred

        # Compute standard cross-entropy loss
        ce_loss = self.base_loss(y_true, logits)

        # Separate in-distribution and OOD examples
        is_ood = tf.cast(tf.equal(y_true, self.ood_label), tf.float32)
        is_id = 1.0 - is_ood

        # Compute energy scores
        energy = -tf.math.log(tf.reduce_sum(tf.exp(logits), axis=-1))

        # Energy loss: encourage high energy for OOD, low energy for ID
        energy_loss = (
            tf.maximum(0.0, self.energy_margin - energy) * is_ood + energy * is_id
        )

        # Mask ce_loss for OOD examples (they don't have a valid class)
        ce_loss = ce_loss * is_id

        # If there are no OOD examples in this batch, just return CE loss
        num_ood = tf.reduce_sum(is_ood)
        has_ood = tf.cast(tf.greater(num_ood, 0), tf.float32)

        # Combine losses only if OOD examples are present
        combined_loss = ce_loss + has_ood * self.energy_weight * energy_loss

        return combined_loss
