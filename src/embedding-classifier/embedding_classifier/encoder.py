"""
Embedding model wrapper: pinned weights, the model's prompt, float32 on CPU,
unit-length vectors.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

TASK = (
    "Classify the given citizen message by the Estonian government agency "
    "that should answer it"
)

# Prefix each model expects on every text, stored and incoming alike. The
# benchmarks ran this way; changing a prompt needs a new measurement.
PROMPTS = {
    "BAAI/bge-m3": "",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2": "",
    "intfloat/multilingual-e5-large-instruct": "Instruct: {task}\nQuery: ",
}

# Token limits: "short" for questions, titles and incoming messages,
# "long" for passages and answers
MAX_SEQ_LENGTH = {"short": 128, "long": 256}

MODELS_FILE = Path(__file__).with_name("embedding_models.json")


@dataclass(frozen=True)
class EmbeddingModel:
    """An embedding model key, its Hugging Face id and the pinned commit."""

    key: str
    hf_id: str
    revision: str

    @property
    def prompt(self) -> str:
        if self.hf_id not in PROMPTS:
            raise ValueError(f"No prompt is defined for {self.hf_id}")
        return PROMPTS[self.hf_id].format(task=TASK)


def load_models(path: Path = MODELS_FILE) -> dict[str, EmbeddingModel]:
    """Read the model keys the builder accepts in --model_types."""
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {
        key: EmbeddingModel(key, entry["hf_id"], entry["revision"])
        for key, entry in entries.items()
    }


def get_model(key: str, path: Path = MODELS_FILE) -> EmbeddingModel:
    models = load_models(path)
    if key not in models:
        raise KeyError(f"Unknown embedding model {key!r}; known: {sorted(models)}")
    return models[key]


class Encoder:
    """Turns texts into unit-length float32 vectors on CPU."""

    def __init__(
        self,
        model: EmbeddingModel,
        threads: Optional[int] = None,
        cache_folder: Optional[str] = None,
        local_files_only: bool = False,
    ):
        """
        Load the pinned model weights.

        Args:
            model: Model and revision to load
            threads: Torch CPU threads; None keeps torch's default
            cache_folder: Hugging Face cache; None uses HF_HOME
            local_files_only: Never download (production images set HF_HUB_OFFLINE)
        """
        # Imported here so the rest of the library and its tests need no torch
        import torch
        from sentence_transformers import SentenceTransformer

        if threads:
            torch.set_num_threads(threads)
        logger.info(f"Loading {model.hf_id} at revision {model.revision}")
        self.model = model
        # Some models ship float16 weights, which run several times slower on CPU
        self._model = SentenceTransformer(
            model.hf_id,
            revision=model.revision,
            device="cpu",
            cache_folder=cache_folder,
            local_files_only=local_files_only,
            model_kwargs={"dtype": torch.float32},
        )
        self.dim = self._model.get_embedding_dimension()

    def encode(
        self, texts: list[str], length: str = "short", batch_size: int = 32
    ) -> np.ndarray:
        """
        Embed texts with the model's prompt.

        Args:
            texts: Texts to embed
            length: "short" or "long", see MAX_SEQ_LENGTH
            batch_size: Texts per forward pass

        Returns:
            Array of shape (len(texts), dim) with unit-length rows
        """
        if length not in MAX_SEQ_LENGTH:
            raise ValueError(f"Unknown length {length!r}")
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        # Not thread-safe: callers serialise encoding (the service holds a lock)
        self._model.max_seq_length = MAX_SEQ_LENGTH[length]
        vectors = self._model.encode(
            texts,
            prompt=self.model.prompt or None,
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.astype(np.float32)
