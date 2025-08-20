"""
Base model architecture for conversation classification with OOD detection.
"""

import tensorflow as tf
from transformers import TFAutoModel, AutoConfig
from typing import Dict, Tuple, List, Union, Any
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseModel(tf.keras.Model):
    """Base model for conversation classification."""

    def __init__(
        self,
        pretrained_model: str = "xlm-roberta-base",
        num_labels: int = 2,
        hidden_dims: List[int] = None,
        dropout_rate: float = 0.1,
    ):
        """
        Initialize the base model.

        Args:
            pretrained_model: Name or path of the pre-trained model
            num_labels: Number of classification labels
            hidden_dims: Dimensions of hidden layers after the transformer
            dropout_rate: Dropout rate for regularization
            **kwargs: Additional arguments
        """
        super().__init__()

        self.num_labels = num_labels
        self.dropout_rate = dropout_rate

        # Initialize the transformer model
        self.config = AutoConfig.from_pretrained(pretrained_model)
        self.transformer = TFAutoModel.from_pretrained(pretrained_model)

        # Initialize hidden layers
        self.hidden_layers = []
        if hidden_dims:
            for dim in hidden_dims:
                self.hidden_layers.append(tf.keras.layers.Dense(dim, activation="relu"))
                self.hidden_layers.append(tf.keras.layers.Dropout(dropout_rate))

        # Initialize the classification layer
        self.classifier = tf.keras.layers.Dense(num_labels, name="classifier")

        # For inference time tracking
        self.inference_times = []

    def call(
        self,
        inputs: Dict[str, tf.Tensor],
        training: bool = None,
        return_features: bool = False,
        measure_inference_time: bool = False,
    ) -> Union[tf.Tensor, Tuple[tf.Tensor, tf.Tensor]]:
        """
        Forward pass of the model.

        Args:
            inputs: Input tensors containing 'input_ids' and 'attention_mask'
            training: Whether we are training or not
            return_features: Whether to return the features before classification
            measure_inference_time: Whether to measure inference time
            **kwargs: Additional arguments

        Returns:
            logits: Classification logits
            features: (Optional) Features before the classification layer
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
            else transformer_outputs.pooler_output
        )

        # Apply hidden layers
        features = pooled_output
        for layer in self.hidden_layers:
            features = layer(features, training=training)

        # Apply classification layer
        logits = self.classifier(features)

        if measure_inference_time:
            end_time = time.time()
            self.inference_times.append(end_time - start_time)

        if return_features:
            return logits, features

        return logits

    def get_config(self) -> Dict[str, Any]:
        """
        Get model configuration.

        Returns:
            config: Model configuration dictionary
        """
        config = super().get_config()
        config.update(
            {
                "num_labels": self.num_labels,
                "dropout_rate": self.dropout_rate,
            }
        )
        return config

    def get_average_inference_time(self) -> float:
        """
        Get the average inference time.

        Returns:
            average_time: Average inference time in seconds
        """
        if not self.inference_times:
            return 0.0
        return sum(self.inference_times) / len(self.inference_times)

    def predict_with_uncertainty(
        self, inputs: Dict[str, tf.Tensor], **kwargs
    ) -> Tuple[tf.Tensor, tf.Tensor]:
        """
        Base method for prediction with uncertainty.
        Subclasses should override this method to provide OOD detection.

        Args:
            inputs: Input tensors
            **kwargs: Additional arguments

        Returns:
            predictions: Class predictions
            uncertainty: Uncertainty scores
        """
        logits = self(inputs, training=False, measure_inference_time=True)
        probabilities = tf.nn.softmax(logits, axis=-1)
        predictions = tf.argmax(probabilities, axis=-1)

        # Default uncertainty is just 1 - max probability
        max_probs = tf.reduce_max(probabilities, axis=-1)
        uncertainty = 1.0 - max_probs

        return predictions, uncertainty
