"""
Data loading and preprocessing for the OOD detection models.
"""

import pandas as pd
import tensorflow as tf
import numpy as np
from typing import Tuple, List, Dict
from transformers import AutoTokenizer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataLoader:
    """Data loader for conversation classification with OOD detection."""

    def __init__(
        self,
        tokenizer_name: str = "xlm-roberta-base",
        max_seq_length: int = 512,
        batch_size: int = 32,
        seed: int = 42,
    ):
        """
        Initialize the data loader.

        Args:
            tokenizer_name: Name or path of the tokenizer to use
            max_seq_length: Maximum sequence length for tokenization
            batch_size: Batch size for training and evaluation
            seed: Random seed for reproducibility
        """
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.max_seq_length = max_seq_length
        self.batch_size = batch_size
        self.seed = seed

        # Set random seed for reproducibility
        tf.random.set_seed(seed)
        np.random.seed(seed)

    def load_data(
        self, data_path: str, is_training: bool = True, add_ood_class: bool = False
    ) -> Tuple[tf.data.Dataset, Dict[str, int], int]:
        """
        Load data from a CSV file.

        Args:
            data_path: Path to the CSV file
            is_training: Whether this is training data
            add_ood_class: Whether to add an OOD class to the label mapping

        Returns:
            dataset: TensorFlow dataset
            label_map: Mapping from label names to IDs
            num_examples: Number of examples in the dataset
        """
        logger.info(f"Loading data from {data_path}")

        # Load data
        df = pd.read_csv(data_path)

        # Check required columns
        required_cols = ["conversation", "agency"]
        if not all(col in df.columns for col in required_cols):
            raise ValueError(f"Data file must contain columns: {required_cols}")

        # Create label mapping
        unique_labels = sorted(df["agency"].unique())
        logger.info(f"Found {len(unique_labels)} unique labels: {unique_labels}")

        label_map = {label: i for i, label in enumerate(unique_labels)}

        # Add OOD class if specified
        if add_ood_class:
            label_map["OOD"] = len(label_map)

        # Convert labels to IDs
        label_ids = df["agency"].map(label_map).values

        # Tokenize conversations - ensure they are strings
        conversations = df["conversation"].astype(str).values
        tokenized_inputs = self._tokenize_text(conversations)

        # Create dataset
        dataset = tf.data.Dataset.from_tensor_slices(
            (
                {
                    "input_ids": tokenized_inputs["input_ids"],
                    "attention_mask": tokenized_inputs["attention_mask"],
                },
                label_ids,
            )
        )

        # Prepare dataset for training or evaluation
        if is_training:
            dataset = dataset.shuffle(buffer_size=len(df), seed=self.seed)

        dataset = dataset.batch(self.batch_size)
        dataset = dataset.prefetch(tf.data.AUTOTUNE)

        return dataset, label_map, len(df)

    def load_ood_data(
        self, data_path: str, label_map: Dict[str, int]
    ) -> tf.data.Dataset:
        """
        Load OOD data for evaluation.

        Args:
            data_path: Path to the OOD data CSV file
            label_map: Mapping from label names to IDs

        Returns:
            dataset: TensorFlow dataset
        """
        logger.info(f"Loading OOD data from {data_path}")

        # Load data
        df = pd.read_csv(data_path)

        # Check required columns
        if "conversation" not in df.columns:
            raise ValueError("Data file must contain a 'conversation' column")

        # Assign OOD label if present in label map, otherwise use -1
        ood_label = label_map.get("OOD", -1)
        labels = np.full(len(df), ood_label)

        # Tokenize conversations - ensure they are strings
        conversations = df["conversation"].astype(str).values
        tokenized_inputs = self._tokenize_text(conversations)

        # Create dataset
        dataset = tf.data.Dataset.from_tensor_slices(
            (
                {
                    "input_ids": tokenized_inputs["input_ids"],
                    "attention_mask": tokenized_inputs["attention_mask"],
                },
                labels,
            )
        )

        dataset = dataset.batch(self.batch_size)
        dataset = dataset.prefetch(tf.data.AUTOTUNE)

        return dataset

    def create_synthetic_ood(
        self,
        train_dataset: tf.data.Dataset,
        label_map: Dict[str:int],
        ratio: float = 0.2,
    ) -> tf.data.Dataset:
        """
        Create synthetic OOD examples for training.

        Args:
            train_dataset: The original training dataset
            ratio: The ratio of synthetic OOD examples to add

        Returns:
            dataset: The combined dataset with synthetic OOD examples
        """
        logger.info(f"Creating synthetic OOD examples with ratio {ratio}")

        # Convert dataset to numpy arrays
        all_data = []
        for features, labels in train_dataset:
            for i in range(len(labels)):
                input_ids = features["input_ids"][i].numpy()
                attention_mask = features["attention_mask"][i].numpy()
                label = labels[i].numpy()
                all_data.append((input_ids, attention_mask, label))

        # Calculate number of synthetic examples
        num_orig = len(all_data)
        num_synth = int(num_orig * ratio)

        # Create synthetic examples by shuffling tokens
        synthetic_data = []
        for _ in range(num_synth):
            # Randomly select an example
            idx = np.random.randint(0, num_orig)
            input_ids, attention_mask, _ = all_data[idx]

            # Shuffle the tokens (excluding special tokens)
            special_tokens = [
                self.tokenizer.cls_token_id,
                self.tokenizer.sep_token_id,
                self.tokenizer.pad_token_id,
            ]
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
                shuffled_input_ids[mask] = np.random.permutation(original_tokens)

                # Add to synthetic data with OOD label (-1 or the OOD class index)
                synthetic_data.append(
                    (shuffled_input_ids, attention_mask, label_map.get("OOD", -1))
                )

        # Combine original and synthetic data
        combined_data = all_data + synthetic_data
        np.random.shuffle(combined_data)

        # Convert back to TensorFlow dataset
        def gen():
            for input_ids, attention_mask, label in combined_data:
                yield {"input_ids": input_ids, "attention_mask": attention_mask}, label

        # Create dataset with the appropriate shapes and types
        input_shape = all_data[0][0].shape
        output_dataset = tf.data.Dataset.from_generator(
            gen,
            output_types=(
                {"input_ids": tf.int32, "attention_mask": tf.int32},
                tf.int32,
            ),
            output_shapes=(
                {
                    "input_ids": tf.TensorShape(input_shape),
                    "attention_mask": tf.TensorShape(input_shape),
                },
                tf.TensorShape([]),
            ),
        )

        return output_dataset.batch(self.batch_size).prefetch(tf.data.AUTOTUNE)

    def _tokenize_text(self, texts: List[str]) -> Dict[str, np.ndarray]:
        """
        Tokenize a list of texts.

        Args:
            texts: List of text strings to tokenize

        Returns:
            Dictionary with 'input_ids' and 'attention_mask'
        """
        # Ensure all texts are strings and handle any NaN/None values
        clean_texts = []
        for text in texts:
            if pd.isna(text) or text is None:
                clean_texts.append("")
            else:
                clean_texts.append(str(text))

        return self.tokenizer(
            clean_texts,
            padding="max_length",
            truncation=True,
            max_length=self.max_seq_length,
            return_tensors="np",
        )
