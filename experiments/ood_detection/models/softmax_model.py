"""
Softmax threshold model for OOD detection.
"""

import tensorflow as tf
from typing import Dict, Tuple, List
import logging
from models.base_model import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SoftmaxModel(BaseModel):
    """
    Softmax threshold model for OOD detection.

    This model uses the maximum softmax probability (MSP) or
    entropy of the softmax distribution as an uncertainty measure.
    It may also use temperature scaling for improved calibration.
    """

    def __init__(
        self,
        pretrained_model: str = "xlm-roberta-base",
        num_labels: int = 2,
        hidden_dims: List[int] = None,
        dropout_rate: float = 0.1,
        temperature: float = 1.0,
        use_entropy: bool = False,  # Whether to use entropy instead of MSP
        **kwargs,
    ):
        """
        Initialize the softmax threshold model.

        Args:
            pretrained_model: Pre-trained model name
            num_labels: Number of classes
            hidden_dims: Hidden layer dimensions
            dropout_rate: Dropout rate
            temperature: Temperature scaling parameter
            use_entropy: Whether to use entropy instead of MSP
            **kwargs: Additional arguments
        """
        super().__init__(
            pretrained_model=pretrained_model,
            num_labels=num_labels,
            hidden_dims=hidden_dims,
            dropout_rate=dropout_rate,
            **kwargs,
        )

        self.temperature = temperature
        self.use_entropy = use_entropy

    def compute_entropy(self, probabilities: tf.Tensor) -> tf.Tensor:
        """
        Compute entropy of probability distribution.

        Args:
            probabilities: Softmax probabilities

        Returns:
            entropy: Entropy values
        """
        # Add small epsilon to avoid log(0)
        probabilities = tf.clip_by_value(probabilities, 1e-10, 1.0)

        # Compute entropy: -sum(p_i * log(p_i))
        entropy = -tf.reduce_sum(probabilities * tf.math.log(probabilities), axis=-1)

        return entropy

    def predict_with_uncertainty(
        self, inputs: Dict[str, tf.Tensor], **kwargs
    ) -> Tuple[tf.Tensor, tf.Tensor]:
        """
        Predict with uncertainty estimation using softmax threshold.

        Args:
            inputs: Input tensors
            **kwargs: Additional arguments

        Returns:
            predictions: Class predictions
            uncertainty: Uncertainty scores based on softmax
        """
        logits = self(inputs, training=False, measure_inference_time=True)

        # Apply temperature scaling
        logits_scaled = logits / self.temperature
        probabilities = tf.nn.softmax(logits_scaled, axis=-1)
        predictions = tf.argmax(probabilities, axis=-1)

        if self.use_entropy:
            # Compute entropy as uncertainty
            uncertainty = self.compute_entropy(probabilities)
        else:
            # 1 - max softmax probability as uncertainty
            max_probs = tf.reduce_max(probabilities, axis=-1)
            uncertainty = 1.0 - max_probs

        return predictions, uncertainty

    def get_config(self):
        """Get model configuration."""
        config = super().get_config()
        config.update(
            {
                "temperature": self.temperature,
                "use_entropy": self.use_entropy,
            }
        )
        return config


class TemperatureScaling(tf.keras.layers.Layer):
    """
    Temperature scaling layer for model calibration.

    This layer learns a single temperature parameter to scale
    the logits, which can improve the calibration of the model.
    """

    def __init__(self, temperature: float = 1.0, **kwargs):
        """
        Initialize temperature scaling layer.

        Args:
            temperature: Initial temperature value
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        self.temperature = temperature

    def build(self, input_shape):
        """Build the layer."""
        # Temperature parameter (learned during calibration)
        self.temp = self.add_weight(
            name="temperature",
            shape=[],
            initializer=tf.keras.initializers.Constant(self.temperature),
            trainable=True,
        )

        super().build(input_shape)

    def call(self, inputs, training=None):
        """Forward pass."""
        # Scale logits by temperature
        return inputs / self.temp

    def get_config(self):
        """Get configuration."""
        config = {"temperature": self.temperature}
        base_config = super().get_config()
        return {**base_config, **config}


class CalibrationCallback(tf.keras.callbacks.Callback):
    """
    Callback for temperature scaling calibration.

    This callback performs post-training calibration using
    temperature scaling on a validation dataset.
    """

    def __init__(
        self,
        calibration_data: tf.data.Dataset,
        patience: int = 5,
        min_delta: float = 1e-4,
        verbose: int = 1,
    ):
        """
        Initialize calibration callback.

        Args:
            calibration_data: Dataset for calibration
            patience: Patience for early stopping
            min_delta: Minimum delta for improvement
            verbose: Verbosity level
        """
        super().__init__()
        self.calibration_data = calibration_data
        self.patience = patience
        self.min_delta = min_delta
        self.verbose = verbose

        self.best_nll = float("inf")
        self.wait = 0

    def on_train_end(self, logs=None):
        """Perform calibration when training ends."""
        if not hasattr(self.model, "temperature_layer"):
            logger.warning(
                "Model does not have a temperature_layer attribute. Skipping calibration."
            )
            return

        if self.verbose > 0:
            logger.info("Starting temperature calibration...")

        # Create optimizer and loss for calibration
        optimizer = tf.keras.optimizers.legacy.Adam(learning_rate=0.01)
        loss_fn = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)

        # Initial evaluation
        initial_nll = self._evaluate_nll(loss_fn)
        if self.verbose > 0:
            logger.info(
                f"Initial NLL: {initial_nll:.4f}, Initial temperature: {self.model.temperature_layer.temp.numpy():.4f}"
            )

        # Calibration loop
        for epoch in range(50):  # Max 50 epochs for calibration
            self._calibration_step(optimizer, loss_fn)

            # Evaluate current NLL
            current_nll = self._evaluate_nll(loss_fn)

            if self.verbose > 0:
                logger.info(
                    f"Epoch {epoch + 1}, NLL: {current_nll:.4f}, Temperature: {self.model.temperature_layer.temp.numpy():.4f}"
                )

            # Check for improvement
            if current_nll < self.best_nll - self.min_delta:
                self.best_nll = current_nll
                self.wait = 0
            else:
                self.wait += 1
                if self.wait >= self.patience:
                    if self.verbose > 0:
                        logger.info(f"Early stopping at epoch {epoch + 1}")
                    break

        if self.verbose > 0:
            final_temp = self.model.temperature_layer.temp.numpy()
            logger.info(f"Calibration complete. Final temperature: {final_temp:.4f}")
            improvement = (initial_nll - self.best_nll) / initial_nll * 100
            logger.info(
                f"NLL improved from {initial_nll:.4f} to {self.best_nll:.4f} ({improvement:.2f}%)"
            )

    def _calibration_step(self, optimizer, loss_fn):
        """Perform one step of calibration."""
        for x, y in self.calibration_data:
            with tf.GradientTape() as tape:
                # Forward pass through the model
                logits = self.model(x, training=False)

                # Apply temperature scaling (only temperature is trainable)
                scaled_logits = self.model.temperature_layer(logits, training=True)

                # Compute loss
                loss = loss_fn(y, scaled_logits)

            # Compute gradients
            grads = tape.gradient(loss, [self.model.temperature_layer.temp])

            # Apply gradients
            optimizer.apply_gradients(zip(grads, [self.model.temperature_layer.temp]))

            # Ensure temperature is positive
            self.model.temperature_layer.temp.assign(
                tf.maximum(self.model.temperature_layer.temp, 0.01)
            )

    def _evaluate_nll(self, loss_fn):
        """Evaluate negative log-likelihood on calibration data."""
        total_loss = 0.0
        total_samples = 0

        for x, y in self.calibration_data:
            # Forward pass
            logits = self.model(x, training=False)
            scaled_logits = self.model.temperature_layer(logits, training=False)

            # Compute NLL
            loss = loss_fn(y, scaled_logits)

            # Accumulate weighted loss
            batch_size = tf.shape(y)[0]
            total_loss += loss * tf.cast(batch_size, tf.float32)
            total_samples += batch_size

        # Compute average NLL
        avg_nll = total_loss / tf.cast(total_samples, tf.float32)

        return avg_nll.numpy()
