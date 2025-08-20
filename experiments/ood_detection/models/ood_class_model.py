"""
OOD class model: treats OOD data as an additional class during training.
"""

import tensorflow as tf
from typing import Dict, Tuple, List
import numpy as np
import logging
from models.base_model import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OODClassModel(BaseModel):
    """
    OOD class model for OOD detection.

    This model treats OOD examples as an additional class during training,
    creating a K+1 classifier where K is the number of in-distribution classes
    and the +1 is for the OOD class.
    """

    def __init__(
        self,
        pretrained_model: str = "xlm-roberta-base",
        num_labels: int = 2,
        hidden_dims: List[int] = None,
        dropout_rate: float = 0.1,
        synthetic_ood_ratio: float = 0.2,
    ):
        """
        Initialize the OOD class model.

        Args:
            pretrained_model: Pre-trained model name
            num_labels: Number of in-distribution classes (OOD class will be added)
            hidden_dims: Hidden layer dimensions
            dropout_rate: Dropout rate
            synthetic_ood_ratio: Ratio of synthetic OOD examples to add during training
            **kwargs: Additional arguments
        """
        # Add +1 for the OOD class
        super().__init__(
            pretrained_model=pretrained_model,
            num_labels=num_labels + 1,  # +1 for OOD class
            hidden_dims=hidden_dims,
            dropout_rate=dropout_rate,
        )

        self.num_id_classes = num_labels  # Store original number of classes
        self.synthetic_ood_ratio = synthetic_ood_ratio

    def predict_with_uncertainty(
        self, inputs: Dict[str, tf.Tensor], **kwargs
    ) -> Tuple[tf.Tensor, tf.Tensor]:
        """
        Predict with uncertainty estimation using OOD class probability.

        Args:
            inputs: Input tensors
            **kwargs: Additional arguments

        Returns:
            predictions: Class predictions (excluding OOD class)
            uncertainty: Uncertainty scores based on OOD class probability
        """
        logits = self(inputs, training=False, measure_inference_time=True)
        probabilities = tf.nn.softmax(logits, axis=-1)

        # OOD class is the last class
        id_probs = probabilities[:, : self.num_id_classes]
        ood_probs = probabilities[:, -1]

        # ID class predictions (excluding OOD class)
        predictions = tf.argmax(id_probs, axis=-1)

        # Uncertainty is the probability of the OOD class
        uncertainty = ood_probs

        return predictions, uncertainty

    def get_config(self):
        """Get model configuration."""
        config = super().get_config()
        config.update(
            {
                "num_id_classes": self.num_id_classes,
                "synthetic_ood_ratio": self.synthetic_ood_ratio,
            }
        )
        return config


class OODClassDataGenerator(tf.keras.utils.Sequence):
    """
    Data generator for OOD class model.

    This generator adds synthetic OOD examples to the training data.
    """

    def __init__(
        self,
        dataset: tf.data.Dataset,
        num_classes: int,
        batch_size: int = 32,
        synthetic_ood_ratio: float = 0.2,
        shuffle: bool = True,
        seed: int = 42,
    ):
        """
        Initialize the data generator.

        Args:
            dataset: The original dataset
            num_classes: Number of in-distribution classes
            batch_size: Batch size
            synthetic_ood_ratio: Ratio of synthetic OOD examples
            shuffle: Whether to shuffle the data
            seed: Random seed
        """
        self.dataset = dataset
        self.num_classes = num_classes
        self.batch_size = batch_size
        self.synthetic_ood_ratio = synthetic_ood_ratio
        self.shuffle = shuffle
        self.seed = seed

        # Convert dataset to a list for easier handling
        self.data_list = []
        for features, labels in dataset:
            for i in range(len(labels)):
                input_ids = features["input_ids"][i].numpy()
                attention_mask = features["attention_mask"][i].numpy()
                label = labels[i].numpy()
                self.data_list.append((input_ids, attention_mask, label))

        # Calculate number of synthetic examples
        self.num_orig = len(self.data_list)
        self.num_synth = int(self.num_orig * synthetic_ood_ratio)
        self.num_total = self.num_orig + self.num_synth

        # Generate synthetic OOD examples
        self._generate_synthetic_ood()

        # Initial shuffle
        if self.shuffle:
            np.random.seed(self.seed)
            np.random.shuffle(self.combined_data)

    def _generate_synthetic_ood(self):
        """Generate synthetic OOD examples by token shuffling."""
        synthetic_data = []
        for _ in range(self.num_synth):
            # Randomly select an example
            idx = np.random.randint(0, self.num_orig)
            input_ids, attention_mask, _ = self.data_list[idx]

            # Shuffle the tokens (excluding special tokens)
            special_tokens = [0, 101, 102]  # PAD, CLS, SEP tokens
            mask = np.ones_like(input_ids, dtype=bool)
            for token_id in special_tokens:
                mask = mask & (input_ids != token_id)

            # Get non-special token positions
            token_positions = np.where(mask)[0]

            if len(token_positions) > 0:
                # Shuffle these positions
                np.random.shuffle(token_positions)
                shuffled_input_ids = input_ids.copy()

                # Apply shuffling
                original_tokens = input_ids[mask]
                shuffled_input_ids[mask] = original_tokens[np.argsort(token_positions)]

                # Add to synthetic data with OOD label (num_classes)
                synthetic_data.append(
                    (shuffled_input_ids, attention_mask, self.num_classes)
                )

        # Combine original and synthetic data
        self.combined_data = self.data_list + synthetic_data

    def __len__(self):
        """Get the number of batches per epoch."""
        return int(np.ceil(len(self.combined_data) / self.batch_size))

    def __getitem__(self, idx):
        """Get a batch of data."""
        batch_data = self.combined_data[
            idx * self.batch_size : (idx + 1) * self.batch_size
        ]

        # Prepare batch
        batch_size = len(batch_data)
        input_ids = np.zeros((batch_size, batch_data[0][0].shape[0]), dtype=np.int32)
        attention_mask = np.zeros(
            (batch_size, batch_data[0][1].shape[0]), dtype=np.int32
        )
        labels = np.zeros(batch_size, dtype=np.int32)

        for i, (ids, mask, label) in enumerate(batch_data):
            input_ids[i] = ids
            attention_mask[i] = mask
            labels[i] = label

        return {"input_ids": input_ids, "attention_mask": attention_mask}, labels

    def on_epoch_end(self):
        """Shuffle data at the end of each epoch."""
        if self.shuffle:
            np.random.shuffle(self.combined_data)
