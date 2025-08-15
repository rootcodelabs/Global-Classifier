"""
SNGP (Spectral-normalized Neural Gaussian Process) model for OOD detection.
"""

import time
import tensorflow as tf
from typing import Dict, Tuple, List
import numpy as np
import logging
from models.base_model import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpectralNormalization(tf.keras.layers.Wrapper):
    """
    Spectral Normalization layer wrapper.

    This wrapper normalizes the kernel matrix by constraining
    its spectral norm (the largest singular value) to be less than
    or equal to the specified norm_multiplier.
    """

    def __init__(
        self,
        layer: tf.keras.layers.Layer,
        norm_multiplier: float = 0.9,
        n_power_iterations: int = 1,
    ):
        """
        Initialize the wrapper.

        Args:
            layer: The layer to wrap
            norm_multiplier: Target spectral norm
            n_power_iterations: Number of power iterations for spectral norm estimation
            **kwargs: Additional arguments
        """
        super().__init__(layer)
        self.norm_multiplier = norm_multiplier
        self.n_power_iterations = n_power_iterations

        if not isinstance(layer, tf.keras.layers.Dense):
            raise ValueError(
                "SpectralNormalization can only wrap Dense layers. "
                f"Received: {layer.__class__.__name__}"
            )

    def build(self, input_shape):
        """Build the wrapper."""
        if not self.layer.built:
            self.layer.build(input_shape)

        self.w = self.layer.kernel
        self.w_shape = self.w.shape.as_list()

        # Initialize u and v vectors for power iteration
        # u should match the input dimension, v should match the output dimension
        self.u = self.add_weight(
            name="u",
            shape=(1, self.w_shape[0]),  # Input dimension
            initializer=tf.initializers.TruncatedNormal(stddev=0.1),
            trainable=False,
        )

        self.v = self.add_weight(
            name="v",
            shape=(1, self.w_shape[1]),  # Output dimension
            initializer=tf.initializers.TruncatedNormal(stddev=0.1),
            trainable=False,
        )

        super().build(input_shape)

    def call(self, inputs, training=None):
        """Forward pass with spectral normalization."""
        # Only perform power iterations during training
        if training:
            self._update_weights()

        return self.layer(inputs)

    def _update_weights(self):
        """Update weights using power iteration method."""
        w_reshaped = tf.reshape(self.w, [self.w_shape[0], self.w_shape[1]])

        # Power iteration to find largest singular value
        for _ in range(self.n_power_iterations):
            # v = W^T u / ||W^T u||
            v_new = tf.matmul(self.u, w_reshaped)
            self.v.assign(tf.nn.l2_normalize(v_new, axis=1))

            # u = W v / ||W v||
            u_new = tf.matmul(self.v, w_reshaped, transpose_b=True)
            self.u.assign(tf.nn.l2_normalize(u_new, axis=1))

        # Estimate spectral norm: sigma = u^T W v
        sigma = tf.matmul(tf.matmul(self.u, w_reshaped), self.v, transpose_b=True)
        sigma = tf.reshape(sigma, [])  # Make it a scalar

        # Normalize weights
        self.layer.kernel.assign(self.w / tf.maximum(sigma / self.norm_multiplier, 1.0))

    def get_config(self):
        """Get configuration."""
        config = {
            "norm_multiplier": self.norm_multiplier,
            "n_power_iterations": self.n_power_iterations,
        }
        base_config = super().get_config()
        return {**base_config, **config}


class RandomFeatureGaussianProcess(tf.keras.layers.Layer):
    """
    Random Feature Gaussian Process layer.

    This layer implements a random feature-based approximation to a
    Gaussian process model that is end-to-end trainable with a deep neural network.
    """

    def __init__(
        self,
        units: int,
        num_inducing: int = 1024,
        normalize_input: bool = True,
        scale_random_features: bool = True,
        gp_cov_momentum: float = -1.0,
        gp_cov_ridge_penalty: float = 1.0,
        **kwargs,
    ):
        """
        Initialize the layer.

        Args:
            units: Number of output units (classes)
            num_inducing: Number of random features for GP approximation
            normalize_input: Whether to normalize inputs
            scale_random_features: Whether to scale random features
            gp_cov_momentum: Momentum for covariance update (-1.0 for no momentum)
            gp_cov_ridge_penalty: Ridge penalty for covariance matrix
            **kwargs: Additional arguments
        """
        super().__init__(**kwargs)
        self.units = units
        self.num_inducing = num_inducing
        self.normalize_input = normalize_input
        self.scale_random_features = scale_random_features
        self.gp_cov_momentum = gp_cov_momentum
        self.gp_cov_ridge_penalty = gp_cov_ridge_penalty

        # Set to True when cov_matrix needs resetting
        self._reset_covariance = False

    def build(self, input_shape):
        """Build the layer."""
        input_dim = input_shape[-1]

        # Layer normalization for input
        if self.normalize_input:
            self.layer_norm = tf.keras.layers.LayerNormalization(
                epsilon=1e-12, name="LayerNorm"
            )

        # Random Fourier feature parameters
        stddev = 1.0 / tf.math.sqrt(tf.cast(input_dim, tf.float32))
        self.random_features = self.add_weight(
            name="random_features",
            shape=[input_dim, self.num_inducing],
            initializer=tf.keras.initializers.RandomNormal(stddev=stddev),
            trainable=False,
        )

        # Gaussian process parameters
        self.kernel = self.add_weight(
            name="kernel",
            shape=[self.num_inducing * 2, self.units],  # *2 for cos and sin
            initializer="glorot_uniform",
            trainable=True,
        )

        # Initialize precision matrix
        self.precision_matrix = self.add_weight(
            name="precision_matrix",
            shape=[self.num_inducing * 2, self.num_inducing * 2],  # *2 for cos and sin
            initializer=tf.keras.initializers.Identity(gain=self.gp_cov_ridge_penalty),
            trainable=False,
        )

        # Covariance matrix
        self.covariance_matrix = self.add_weight(
            name="covariance_matrix",
            shape=[self.num_inducing * 2, self.num_inducing * 2],  # *2 for cos and sin
            initializer="zeros",
            trainable=False,
        )

        # Counter for covariance updates
        self.counter = self.add_weight(
            name="counter",
            shape=[],
            initializer="zeros",
            trainable=False,
            dtype=tf.float32,
        )

        super().build(input_shape)

    def reset_covariance_matrix(self):
        """Reset the covariance matrix at the beginning of each epoch."""
        self._reset_covariance = True

    def call(self, inputs, training=None):
        """Forward pass."""
        # Apply layer normalization if needed
        if self.normalize_input:
            inputs = self.layer_norm(inputs)

        # Reset covariance if needed and in training
        if training and self._reset_covariance:
            logger.info("Resetting GP covariance matrix")
            self.covariance_matrix.assign(tf.zeros_like(self.covariance_matrix))
            self.counter.assign(0.0)
            self._reset_covariance = False

        # Project inputs to random features
        gp_features = tf.matmul(inputs, self.random_features)

        # Apply cos and sin functions
        gp_features = tf.concat(
            [tf.math.cos(gp_features), tf.math.sin(gp_features)], axis=-1
        )

        # Scale features if needed
        if self.scale_random_features:
            gp_features = gp_features * tf.math.sqrt(
                2.0 / tf.cast(self.random_features.shape[1], tf.float32)
            )

        # Update covariance matrix during training
        if training:
            self._update_covariance(gp_features)

        # Compute logits
        logits = tf.matmul(gp_features, self.kernel)

        # Return logits and also compute posterior covariance if not training
        if not training:
            # Compute posterior covariance
            feature_cov = self._compute_predictive_covariance(gp_features)

            return logits, feature_cov

        return logits, tf.zeros([1, 1])  # Dummy covariance during training

    def _update_covariance(self, features):
        """Update GP covariance matrix during training."""
        batch_size = tf.cast(tf.shape(features)[0], tf.float32)
        self.counter.assign_add(batch_size)

        # Compute batch covariance
        features_t = tf.transpose(features)
        batch_cov = tf.matmul(features_t, features)

        if self.gp_cov_momentum > 0:
            # Momentum-based update
            self.covariance_matrix.assign(
                self.gp_cov_momentum * self.covariance_matrix
                + (1 - self.gp_cov_momentum) * batch_cov
            )
        else:
            # Running average update
            self.covariance_matrix.assign_add(batch_cov)

    def _compute_predictive_covariance(self, features):
        """Compute predictive covariance for uncertainty estimation."""
        # Normalize the covariance matrix by total count
        cov_matrix = self.covariance_matrix / tf.maximum(self.counter, 1.0)

        # Add ridge penalty - FIXED: use correct dimension
        feature_dim = self.num_inducing * 2
        cov_matrix = cov_matrix + self.gp_cov_ridge_penalty * tf.eye(
            feature_dim, batch_shape=[], dtype=cov_matrix.dtype
        )

        # Compute posterior covariance
        # K_* = k(x, X) = features
        # K = k(X, X) + λI = cov_matrix
        # Posterior covariance = K_* K^-1 K_*^T

        # We use Cholesky decomposition for numerical stability
        try:
            chol = tf.linalg.cholesky(cov_matrix)
        except tf.errors.InvalidArgumentError:
            # If Cholesky fails, add more regularization
            cov_matrix = cov_matrix + 1e-6 * tf.eye(
                feature_dim, batch_shape=[], dtype=cov_matrix.dtype
            )
            chol = tf.linalg.cholesky(cov_matrix)

        # Solve the system: K^-1 K_*^T
        kern_prod = tf.linalg.triangular_solve(chol, tf.transpose(features), lower=True)

        # Compute the predictive covariance
        predictive_cov = tf.matmul(kern_prod, kern_prod, transpose_a=True)

        return predictive_cov

    def get_config(self):
        """Get configuration."""
        config = {
            "units": self.units,
            "num_inducing": self.num_inducing,
            "normalize_input": self.normalize_input,
            "scale_random_features": self.scale_random_features,
            "gp_cov_momentum": self.gp_cov_momentum,
            "gp_cov_ridge_penalty": self.gp_cov_ridge_penalty,
        }
        base_config = super().get_config()
        return {**base_config, **config}


class SNGPModel(BaseModel):
    """
    SNGP model for OOD detection in conversation classification.

    This model applies spectral normalization to hidden layers
    and uses a Gaussian process layer for output to enable
    uncertainty estimation.
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
        **kwargs,
    ):
        """
        Initialize the SNGP model.

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
            **kwargs: Additional arguments
        """
        # Don't pass num_labels to parent class as we'll handle the classifier differently
        super().__init__(
            pretrained_model=pretrained_model,
            num_labels=0,  # No classifier layer in parent
            hidden_dims=None,  # We'll build our own hidden layers
            dropout_rate=dropout_rate,
            **kwargs,
        )

        self.num_labels = num_labels
        self.spec_norm_bound = spec_norm_bound

        # Build hidden layers with spectral normalization
        if hidden_dims is None:
            hidden_dims = [768]

        self.hidden_layers = []
        for dim in hidden_dims:
            dense_layer = tf.keras.layers.Dense(dim, activation="relu")
            spectral_layer = SpectralNormalization(
                dense_layer, norm_multiplier=spec_norm_bound
            )
            self.hidden_layers.append(spectral_layer)
            self.hidden_layers.append(tf.keras.layers.Dropout(dropout_rate))

        # Replace classifier with GP layer
        self.classifier = RandomFeatureGaussianProcess(
            units=num_labels,
            num_inducing=gp_hidden_dim,
            normalize_input=gp_normalize_input,
            scale_random_features=gp_scale_random_features,
            gp_cov_momentum=gp_cov_momentum,
            gp_cov_ridge_penalty=gp_cov_ridge_penalty,
            name="gp_classifier",
        )

    def build(self, input_shape):
        """Build the model."""
        # Build parent first
        super().build(input_shape)

        # Build hidden layers with proper input shapes
        current_shape = (None, 768)  # Shape after transformer
        for layer in self.hidden_layers:
            if hasattr(layer, "build"):
                layer.build(current_shape)
                if isinstance(layer, SpectralNormalization):
                    current_shape = (None, layer.layer.units)

        # Build classifier
        self.classifier.build(current_shape)

    def call(
        self,
        inputs: Dict[str, tf.Tensor],
        training: bool = None,
        return_features: bool = False,
        return_covmat: bool = False,
        measure_inference_time: bool = False,
        **kwargs,
    ):
        """
        Forward pass of the SNGP model.

        Args:
            inputs: Input tensors
            training: Whether in training mode
            return_features: Whether to return features
            return_covmat: Whether to return covariance matrix
            measure_inference_time: Whether to measure inference time
            **kwargs: Additional arguments

        Returns:
            logits: Output logits
            features: (Optional) Features before classification
            covmat: (Optional) Covariance matrix
        """
        start_time = time.time() if measure_inference_time else None

        # Extract inputs
        input_ids = inputs["input_ids"]
        attention_mask = inputs["attention_mask"]

        # Pass through transformer
        transformer_outputs = self.transformer(
            input_ids=input_ids, attention_mask=attention_mask, training=training
        )

        # Use the [CLS] token representation
        pooled_output = (
            transformer_outputs[1]
            if hasattr(transformer_outputs, "__getitem__")
            and len(transformer_outputs) > 1
            else transformer_outputs.last_hidden_state[:, 0, :]  # Use CLS token
        )

        # Apply hidden layers with spectral normalization
        features = pooled_output
        for layer in self.hidden_layers:
            features = layer(features, training=training)

        # Apply GP layer
        logits, covmat = self.classifier(features, training=training)

        if measure_inference_time:
            end_time = time.time()
            if not hasattr(self, "inference_times"):
                self.inference_times = []
            self.inference_times.append(end_time - start_time)

        if return_features and return_covmat:
            return logits, features, covmat
        elif return_features:
            return logits, features
        elif return_covmat:
            return logits, covmat

        return logits

    def reset_covmat(self):
        """Reset the covariance matrix of the GP layer."""
        self.classifier.reset_covariance_matrix()

    def predict_with_uncertainty(
        self, inputs: Dict[str, tf.Tensor], **kwargs
    ) -> Tuple[tf.Tensor, tf.Tensor]:
        """
        Predict with uncertainty estimation using SNGP.

        Args:
            inputs: Input tensors
            **kwargs: Additional arguments

        Returns:
            predictions: Class predictions
            uncertainty: Uncertainty scores based on predictive variance
        """
        # Get logits and covariance matrix
        logits, covmat = self(
            inputs, training=False, return_covmat=True, measure_inference_time=True
        )

        # Extract variance from the diagonal of the covariance matrix
        # covmat shape: [batch_size, batch_size] - diagonal gives per-sample variance
        variance = tf.linalg.diag_part(covmat)

        # Ensure variance is always a vector (batch_size,)
        if len(variance.shape) == 0:  # scalar case
            batch_size = tf.shape(logits)[0]
            variance = tf.fill([batch_size], variance)
        elif len(variance.shape) > 1:  # multi-dimensional case
            variance = tf.reduce_mean(variance, axis=-1)

        # Mean-field approximation to get uncertainty-adjusted logits
        mean_field_factor = np.pi / 8.0
        variance_expanded = tf.expand_dims(variance, -1)  # [batch_size, 1]
        logits_adjusted = logits / tf.sqrt(1.0 + mean_field_factor * variance_expanded)

        # Get predictions from adjusted logits
        probabilities = tf.nn.softmax(logits_adjusted, axis=-1)
        predictions = tf.argmax(probabilities, axis=-1)

        # Return variance as uncertainty measure
        uncertainty = variance

        return predictions, uncertainty

    def get_config(self):
        """Get model configuration."""
        config = super().get_config()
        config.update(
            {
                "num_labels": self.num_labels,
                "spec_norm_bound": self.spec_norm_bound,
            }
        )
        return config


# Callback for resetting covariance matrix at the beginning of each epoch
class ResetCovarianceCallback(tf.keras.callbacks.Callback):
    """Callback to reset GP covariance matrix at the beginning of each epoch."""

    def on_epoch_begin(self, epoch, logs=None):
        """Reset covariance matrix when a new epoch begins."""
        if epoch > 0:  # Skip the first epoch
            if hasattr(self.model, "reset_covmat"):
                self.model.reset_covmat()
            elif hasattr(self.model, "classifier") and hasattr(
                self.model.classifier, "reset_covariance_matrix"
            ):
                self.model.classifier.reset_covariance_matrix()
