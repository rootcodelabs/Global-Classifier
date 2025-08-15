"""
Energy-based OOD detection model for conversation classification.
"""

import tensorflow as tf
from typing import Dict, Tuple, List
import logging
from models.base_model import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnergyModel(BaseModel):
    """
    Energy-based model for OOD detection.

    This model uses the energy score as an uncertainty measure, which
    is computed as -log(sum(exp(logits))). Lower energy indicates
    higher likelihood of in-distribution data.
    """

    def __init__(
        self,
        pretrained_model: str = "xlm-roberta-base",
        num_labels: int = 2,
        hidden_dims: List[int] = None,
        dropout_rate: float = 0.1,
        energy_temp: float = 1.0,
    ):
        """
        Initialize the energy-based model.

        Args:
            pretrained_model: Pre-trained model name
            num_labels: Number of classes
            hidden_dims: Hidden layer dimensions
            dropout_rate: Dropout rate
            energy_temp: Temperature parameter for energy score
            **kwargs: Additional arguments
        """
        super().__init__(
            pretrained_model=pretrained_model,
            num_labels=num_labels,
            hidden_dims=hidden_dims,
            dropout_rate=dropout_rate,
        )

        self.energy_temp = energy_temp

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
        self, inputs: Dict[str, tf.Tensor], **kwargs
    ) -> Tuple[tf.Tensor, tf.Tensor]:
        """
        Predict with uncertainty estimation using energy scores.

        Args:
            inputs: Input tensors
            **kwargs: Additional arguments

        Returns:
            predictions: Class predictions
            uncertainty: Uncertainty scores based on energy
        """
        logits = self(inputs, training=False, measure_inference_time=True)
        probabilities = tf.nn.softmax(logits, axis=-1)
        predictions = tf.argmax(probabilities, axis=-1)

        # Compute energy scores for uncertainty
        energy = self.compute_energy(logits)

        # Higher energy means higher uncertainty
        uncertainty = energy

        return predictions, uncertainty

    def get_config(self):
        """Get model configuration."""
        config = super().get_config()
        config.update(
            {
                "energy_temp": self.energy_temp,
            }
        )
        return config


class EnergyLoss(tf.keras.losses.Loss):
    """
    Energy-based loss function for OOD detection.

    This loss adds an additional term to the standard cross-entropy
    loss that encourages high energy (low likelihood) for OOD examples
    and low energy (high likelihood) for in-distribution examples.
    """

    def __init__(
        self,
        ood_label: int = -1,
        energy_margin: float = 10.0,
        energy_weight: float = 0.1,
    ):
        """
        Initialize the energy loss.

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

    def call(self, y_true: tf.Tensor, y_pred: tf.Tensor) -> tf.Tensor:
        """
        Compute the energy-based loss.

        Args:
            y_true: Ground truth labels
            y_pred: Predicted logits

        Returns:
            loss: Combined loss value
        """
        # Compute standard cross-entropy loss
        ce_loss = self.base_loss(y_true, y_pred)

        # Separate in-distribution and OOD examples
        is_ood = tf.cast(tf.equal(y_true, self.ood_label), tf.float32)
        is_id = 1.0 - is_ood

        # Compute energy scores
        energy = -tf.math.log(tf.reduce_sum(tf.exp(y_pred), axis=-1))

        # Energy loss: encourage high energy for OOD, low energy for ID
        energy_loss = (
            tf.maximum(0.0, self.energy_margin - energy) * is_ood + energy * is_id
        )

        # Mask ce_loss for OOD examples (they don't have a valid class)
        ce_loss = ce_loss * is_id

        # Combine losses
        combined_loss = ce_loss + self.energy_weight * energy_loss

        return combined_loss
