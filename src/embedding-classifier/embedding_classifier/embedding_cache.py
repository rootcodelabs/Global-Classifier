"""
Embedding cache on disk, keyed by (model, revision, max_seq_length,
sha256(text)), so a rebuild only embeds texts it has not seen.
"""

import hashlib
import logging
import os
import time
from pathlib import Path

import numpy as np

from embedding_classifier.encoder import MAX_SEQ_LENGTH

logger = logging.getLogger(__name__)


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """One .npz file per model, revision and token limit, in a folder."""

    def __init__(self, folder: str):
        self.folder = Path(folder)
        self._loaded: dict[Path, dict[str, np.ndarray]] = {}

    def encode(self, encoder, texts: list[str], length: str) -> np.ndarray:
        """
        Vectors for texts, embedding only the ones not cached yet.

        Args:
            encoder: Encoder with .model (EmbeddingModel), .dim and .encode()
            texts: Texts to embed
            length: "short" or "long"

        Returns:
            Array of shape (len(texts), encoder.dim)
        """
        if not texts:
            return np.zeros((0, encoder.dim), dtype=np.float32)
        path = self._path(encoder.model, length)
        cached = self._load(path, _model_tag(encoder.model))
        keys = [text_key(text) for text in texts]
        missing = {key: text for key, text in zip(keys, texts) if key not in cached}
        if missing:
            start = time.perf_counter()
            vectors = encoder.encode(list(missing.values()), length)
            logger.info(
                f"Embedded {len(missing)} new {length} texts in "
                f"{time.perf_counter() - start:.0f}s"
            )
            cached.update(zip(missing, vectors))
            self._save(path, cached, _model_tag(encoder.model))
        return np.stack([cached[key] for key in keys]).astype(np.float32)

    def _path(self, model, length: str) -> Path:
        # A short name keeps paths within Windows' limit; the file itself
        # records the full model id and revision
        name = model.hf_id.split("/")[-1]
        return (
            self.folder / f"{name}@{model.revision[:12]}_{MAX_SEQ_LENGTH[length]}.npz"
        )

    def _load(self, path: Path, model_tag: str) -> dict[str, np.ndarray]:
        if path not in self._loaded:
            entries = {}
            if path.exists():
                with np.load(path) as data:
                    if str(data["model"]) != model_tag:
                        raise ValueError(
                            f"{path} holds {data['model']}, not {model_tag}"
                        )
                    entries = dict(zip(data["keys"].tolist(), data["vectors"]))
            self._loaded[path] = entries
        return self._loaded[path]

    def _save(self, path: Path, entries: dict[str, np.ndarray], model_tag: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write next to the target and rename, so a crash never leaves half a file
        partial = path.with_suffix(".partial.npz")
        np.savez(
            partial,
            model=np.array(model_tag),
            keys=np.array(list(entries), dtype="<U64"),
            vectors=np.stack(list(entries.values())).astype(np.float32),
        )
        os.replace(partial, path)


def _model_tag(model) -> str:
    return f"{model.hf_id}@{model.revision}"
