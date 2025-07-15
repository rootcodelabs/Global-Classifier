import json
from sklearn.model_selection import train_test_split
from pathlib import Path
from typing import Dict, List, Tuple, Iterator
import gc
import argparse
import sys
import os

from loguru import logger
from scripts.constants import (
    LOG_DIRECTORY,
    LOG_FORMAT,
    LOG_FILE_NAME,
    ROTATION_SIZE,
    RETENTION_PERIOD,
    LOG_FILE_HANDLER_FORMAT,
)

os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Remove default handler and add custom ones
logger.remove()

# Add console handler for immediate feedback
logger.add(
    sys.stderr,
    level="DEBUG",
    format=LOG_FORMAT,
    colorize=True,
)

# Add file handler
logger.add(
    sink=os.path.join(LOG_DIRECTORY, LOG_FILE_NAME),
    level="DEBUG",
    rotation=ROTATION_SIZE,
    retention=RETENTION_PERIOD,
    backtrace=True,
    diagnose=True,
    format=LOG_FILE_HANDLER_FORMAT,
)


class ScalableDatasetProcessor:
    """Scalable processor for large aggregated datasets."""

    def __init__(self, dataset_path: str, output_dir: str, chunk_size: int = 10000):
        self.dataset_path = dataset_path
        self.dataset_id = Path(dataset_path).stem

        # Create dataset-specific output directory
        self.base_output_dir = Path(output_dir)
        self.output_dir = self.base_output_dir / f"dataset_{self.dataset_id}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.chunk_size = chunk_size

        logger.info(f"Dataset ID: {self.dataset_id}")
        logger.info(f"Output directory: {self.output_dir}")

    def estimate_dataset_size(self) -> int:
        """Estimate dataset size without loading full data."""
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            # Try to read just metadata first
            try:
                for line_num, line in enumerate(f):
                    if '"total_items"' in line:
                        # Extract total_items value
                        import re

                        match = re.search(r'"total_items":\s*(\d+)', line)
                        if match:
                            return int(match.group(1))
                    if line_num > 10:  # Don't read too far
                        break
            except Exception:
                pass

        # Fallback: count items by streaming
        return self._count_items_streaming()

    def _count_items_streaming(self) -> int:
        """Count items by streaming through the file."""
        count = 0
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            for line in f:
                count += line.count('"question"')
        return count

    def load_data_chunked(
        self, chunk_size: int = None
    ) -> Iterator[Tuple[List[str], List[str]]]:
        """Load data in chunks for memory efficiency."""
        if chunk_size is None:
            chunk_size = self.chunk_size

        logger.info(f"Loading data in chunks of {chunk_size}")

        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        aggregated_data = data.get("aggregated_data", [])

        # Process in chunks
        for i in range(0, len(aggregated_data), chunk_size):
            chunk = aggregated_data[i : i + chunk_size]

            texts = []
            labels = []

            for item in chunk:
                question = item.get("question", "").strip()
                agency_name = item.get("agency_name", "").strip()

                if question and agency_name:
                    texts.append(question)
                    labels.append(agency_name)

            logger.info(f"Processed chunk {i // chunk_size + 1}, {len(texts)} samples")
            yield texts, labels

    def load_data_memory_optimized(self) -> Tuple[List[str], List[str], Dict]:
        """Load data with memory optimization for large datasets."""
        estimated_size = self.estimate_dataset_size()
        logger.info(f"Estimated dataset size: {estimated_size} items")

        # Adjust chunk size based on dataset size
        if estimated_size > 100000:  # 100K+ items
            self.chunk_size = 5000
            logger.info("Large dataset detected, using smaller chunks")
        elif estimated_size > 1000000:  # 1M+ items
            self.chunk_size = 1000
            logger.info("Very large dataset detected, using minimal chunks")

        # Pre-allocate lists for better performance
        texts = []
        labels = []

        # Process in chunks and merge
        for chunk_texts, chunk_labels in self.load_data_chunked():
            texts.extend(chunk_texts)
            labels.extend(chunk_labels)

            # Periodic garbage collection for very large datasets
            if len(texts) % 50000 == 0:
                gc.collect()
                logger.info(f"Processed {len(texts)} samples so far...")

        # Load metadata separately to save memory
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            metadata = data.get("metadata", {})

        logger.info(f"Total loaded: {len(texts)} samples")
        logger.info(f"Found {len(set(labels))} unique agencies")

        return texts, labels, metadata

    def create_label_mapping_optimized(
        self, labels: List[str]
    ) -> Tuple[Dict[str, int], Dict[int, str]]:
        """Memory-optimized label mapping creation."""
        # Use set for O(1) uniqueness check, then sort
        unique_labels = sorted(set(labels))

        label_to_id = {label: idx for idx, label in enumerate(unique_labels)}
        id_to_label = {idx: label for label, idx in label_to_id.items()}

        logger.info(f"Created label mapping for {len(unique_labels)} classes")

        # Clear intermediate variables
        del unique_labels
        gc.collect()

        return label_to_id, id_to_label

    def split_dataset_large(
        self,
        texts: List[str],
        labels: List[str],
        test_size: float = 0.2,
        val_size: float = 0.1,
        random_state: int = 42,
    ) -> Dict[str, List]:
        """Memory-efficient dataset splitting for large datasets."""
        logger.info(f"Splitting large dataset: {len(texts)} samples")

        # For very large datasets, use indices instead of copying data
        if len(texts) > 100000:
            return self._split_by_indices(
                texts, labels, test_size, val_size, random_state
            )
        else:
            return self._split_direct(texts, labels, test_size, val_size, random_state)

    def _split_by_indices(
        self,
        texts: List[str],
        labels: List[str],
        test_size: float,
        val_size: float,
        random_state: int,
    ) -> Dict[str, List]:
        """Split using indices to save memory."""
        indices = list(range(len(texts)))

        # Split indices instead of data
        temp_indices, test_indices = train_test_split(
            indices,
            test_size=test_size,
            random_state=random_state,
            stratify=[labels[i] for i in indices],
        )

        val_ratio = val_size / (1 - test_size)
        train_indices, val_indices = train_test_split(
            temp_indices,
            test_size=val_ratio,
            random_state=random_state,
            stratify=[labels[i] for i in temp_indices],
        )

        # Create splits using indices
        splits = {
            "train": {
                "texts": [texts[i] for i in train_indices],
                "labels": [labels[i] for i in train_indices],
            },
            "val": {
                "texts": [texts[i] for i in val_indices],
                "labels": [labels[i] for i in val_indices],
            },
            "test": {
                "texts": [texts[i] for i in test_indices],
                "labels": [labels[i] for i in test_indices],
            },
        }

        logger.info(
            f"Split sizes: Train={len(train_indices)}, Val={len(val_indices)}, Test={len(test_indices)}"
        )
        return splits

    def _split_direct(
        self,
        texts: List[str],
        labels: List[str],
        test_size: float,
        val_size: float,
        random_state: int,
    ) -> Dict[str, List]:
        """Direct splitting for smaller datasets."""
        X_temp, X_test, y_temp, y_test = train_test_split(
            texts,
            labels,
            test_size=test_size,
            random_state=random_state,
            stratify=labels,
        )

        val_ratio = val_size / (1 - test_size)
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp,
            y_temp,
            test_size=val_ratio,
            random_state=random_state,
            stratify=y_temp,
        )

        return {
            "train": {"texts": X_train, "labels": y_train},
            "val": {"texts": X_val, "labels": y_val},
            "test": {"texts": X_test, "labels": y_test},
        }

    def save_splits_chunked(
        self,
        splits: Dict,
        label_to_id: Dict[str, int],
        id_to_label: Dict[int, str],
        metadata: Dict,
    ):
        """Save splits in chunks for large datasets."""

        for split_name, split_data in splits.items():
            # Save files directly in dataset-specific folder
            split_file = self.output_dir / f"{split_name}.json"

            # For large splits, process in chunks
            if len(split_data["texts"]) > 50000:
                self._save_large_split(split_file, split_data, label_to_id)
            else:
                self._save_small_split(split_file, split_data, label_to_id)

            logger.info(f"Saved {split_name} split to {split_file}")

        # Save mappings and stats
        self._save_metadata(label_to_id, id_to_label, metadata, splits)

    def _save_large_split(
        self, file_path: Path, split_data: Dict, label_to_id: Dict[str, int]
    ):
        """Save large split using streaming JSON."""
        texts = split_data["texts"]
        labels = split_data["labels"]
        label_ids = [label_to_id[label] for label in labels]

        output = {
            "texts": texts,
            "labels": labels,
            "label_ids": label_ids,
            "num_samples": len(texts),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    def _save_small_split(
        self, file_path: Path, split_data: Dict, label_to_id: Dict[str, int]
    ):
        """Save small split normally."""
        label_ids = [label_to_id[label] for label in split_data["labels"]]

        output = {
            "texts": split_data["texts"],
            "labels": split_data["labels"],
            "label_ids": label_ids,
            "num_samples": len(split_data["texts"]),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    def _save_metadata(
        self, label_to_id: Dict, id_to_label: Dict, metadata: Dict, splits: Dict
    ):
        """Save metadata files."""
        # Label mappings
        mappings_file = self.output_dir / "label_mappings.json"
        mappings = {
            "label_to_id": label_to_id,
            "id_to_label": id_to_label,
            "num_classes": len(label_to_id),
            "dataset_id": self.dataset_id,
            "original_metadata": metadata,
        }

        with open(mappings_file, "w", encoding="utf-8") as f:
            json.dump(mappings, f, ensure_ascii=False, indent=2)

        # Statistics
        stats_file = self.output_dir / "stats.json"
        total_samples = sum(len(split["texts"]) for split in splits.values())

        stats = {
            "dataset_id": self.dataset_id,
            "total_samples": total_samples,
            "num_classes": len(label_to_id),
            "classes": list(label_to_id.keys()),
            "splits": {
                split_name: {
                    "num_samples": len(split_data["texts"]),
                    "percentage": len(split_data["texts"]) / total_samples * 100,
                }
                for split_name, split_data in splits.items()
            },
        }

        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved label mappings to {mappings_file}")
        logger.info(f"Saved dataset statistics to {stats_file}")

    def process_dataset(
        self, test_size: float = 0.2, val_size: float = 0.1, random_state: int = 42
    ):
        """Main processing pipeline optimized for large datasets."""
        logger.info(
            f"Starting scalable dataset processing for dataset ID: {self.dataset_id}"
        )

        # Load data with memory optimization
        texts, labels, metadata = self.load_data_memory_optimized()

        # Create label mappings efficiently
        label_to_id, id_to_label = self.create_label_mapping_optimized(labels)

        # Split dataset efficiently
        splits = self.split_dataset_large(
            texts, labels, test_size, val_size, random_state
        )

        # Save with chunking for large datasets
        self.save_splits_chunked(splits, label_to_id, id_to_label, metadata)

        # Cleanup
        del texts, labels
        gc.collect()

        logger.info("Scalable dataset processing completed successfully!")

        return {
            "dataset_id": self.dataset_id,
            "output_dir": str(self.output_dir),
            "num_classes": len(label_to_id),
            "splits": {k: len(v["texts"]) for k, v in splits.items()},
        }


def main():
    parser = argparse.ArgumentParser(
        description="Process large aggregated datasets for training"
    )
    parser.add_argument("--dataset_path", type=str, required=True)
    parser.add_argument("--output_dir", type=str, default="data/processed")
    parser.add_argument("--chunk_size", type=int, default=10000)
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--val_size", type=float, default=0.1)
    parser.add_argument("--random_state", type=int, default=42)

    args = parser.parse_args()

    processor = ScalableDatasetProcessor(
        args.dataset_path, args.output_dir, args.chunk_size
    )

    result = processor.process_dataset(
        test_size=args.test_size, val_size=args.val_size, random_state=args.random_state
    )

    logger.info("\nDataset processing completed!")
    logger.info(f"Dataset ID: {result['dataset_id']}")
    logger.info(f"Number of classes: {result['num_classes']}")
    logger.info(f"Output directory: {result['output_dir']}")


if __name__ == "__main__":
    main()
