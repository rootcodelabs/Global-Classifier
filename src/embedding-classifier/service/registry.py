"""
The indexes a service has loaded. Loading reads a build's manifest, keyword
vectorizer and classifier layer (if it has one), checks its Qdrant
collection, warms up, then swaps the index in atomically and records it, so a
restart loads it again. With the second opinion on, loading also builds the
catalogue the prompt opens with and sends it to the model server.
"""

import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from embedding_classifier import second_opinion as so
from embedding_classifier.artifact import (
    KEYWORDS_FILE,
    MANIFEST,
    ArtifactError,
    agencies_from_manifest,
    check_model,
    gate_from_manifest,
    has_layer,
    read_build_files,
    read_layer,
    scoring_from_manifest,
)
from embedding_classifier.classifier_layer import LAYER_FILE, ClassifierLayer
from embedding_classifier.encoder import EmbeddingModel, load_models
from embedding_classifier.gate import GateParams, decide
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.output import decision_records, predictions
from embedding_classifier.scoring import ScoringParams, score
from embedding_classifier.store import Agency
from embedding_classifier.vector_store import IndexStore
from service.build_files import BuildFiles, index_key, loaded_set_key
from service.second_opinion import SecondOpinion

WARM_UP_TEXT = "warm-up"


class LoadError(Exception):
    """A build can't be loaded; the message says why."""


@dataclass
class LoadedIndex:
    model_id: str
    collection: str
    agencies: list[Agency]
    agency_keys: list[str]
    keywords: KeywordVectorizer
    scoring: ScoringParams
    gate: GateParams
    encoder: object
    layer: Optional[ClassifierLayer] = None
    # The second opinion's catalogue; None when it is off or the catalogue can't be built
    opening: Optional[str] = None


class IndexRegistry:
    def __init__(
        self,
        store: IndexStore,
        files: BuildFiles,
        index_env: str,
        encoder_factory: Callable[[EmbeddingModel], object],
        preload_models: tuple[str, ...] = (),
        models: Optional[dict[str, EmbeddingModel]] = None,
        second_opinion: Optional[SecondOpinion] = None,
    ):
        """
        Args:
            store: The vector store holding the collections
            files: Where build files and the loaded-set file live
            index_env: production or testing
            encoder_factory: Loads the encoder for a model
            preload_models: Model keys whose encoders load at startup
            models: The models this image provides, by key
            second_opinion: Asks the llm-reranker about unsure messages; None is mode off
        """
        self.store = store
        self.files = files
        self.index_env = index_env
        self.encoder_factory = encoder_factory
        self.preload_models = preload_models
        self.models = models if models is not None else load_models()
        self.second_opinion = second_opinion
        self.started = False
        self._indexes: dict[str, LoadedIndex] = {}
        self._encoders: dict[tuple[str, str], object] = {}
        # Encoding is serialised; Qdrant is queried outside this lock
        self._encode_lock = threading.Lock()
        self._swap_lock = threading.Lock()
        self._load_lock = threading.Lock()
        self._encoder_lock = threading.Lock()

    def start(self, retry_seconds: float = 10) -> None:
        """
        Load the preloaded encoders and every index in the loaded-set file.
        Until the loaded-set file can be read (S3 still starting, say), keep
        retrying; the service isn't ready before then.
        """
        for key in self.preload_models:
            self._encoder(self.models[key])
        while True:
            try:
                loaded = self.files.read_json(loaded_set_key(self.index_env)) or {}
                break
            except Exception as error:
                logger.error(
                    f"Can't read the loaded-set file yet, retrying in {retry_seconds}s: {error}"
                )
                time.sleep(retry_seconds)
        for model_id in loaded.get("models", []):
            try:
                self.load(str(model_id), persist=False)
            except Exception as error:
                logger.error(f"Could not reload model {model_id}: {error}")
        self.started = True
        logger.info(f"Started with models {self.loaded()}")

    def ready(self) -> bool:
        return self.started and self.store.ping()

    def loaded(self) -> list[str]:
        return sorted(self._indexes)

    def is_loaded(self, model_id: str) -> bool:
        return model_id in self._indexes

    def load(self, model_id: str, persist: bool = True) -> None:
        """Load (or reload) a build; raises LoadError with the reason."""
        start = time.perf_counter()
        with self._load_lock:
            with tempfile.TemporaryDirectory() as folder:
                try:
                    for name in (MANIFEST, KEYWORDS_FILE):
                        self.files.download(
                            index_key(model_id, name), Path(folder) / name
                        )
                    manifest, keywords = read_build_files(Path(folder))
                    if has_layer(manifest):
                        self.files.download(
                            index_key(model_id, LAYER_FILE), Path(folder) / LAYER_FILE
                        )
                    layer = read_layer(Path(folder), manifest)
                except (FileNotFoundError, ArtifactError, ValueError) as error:
                    raise LoadError(
                        f"Build files of model {model_id}: {error}"
                    ) from error

            model = self._model_for(manifest)
            collection = manifest["vector_store"]["collection"]
            self._check_collection(model_id, collection, manifest)
            index = LoadedIndex(
                model_id=model_id,
                collection=collection,
                agencies=agencies_from_manifest(manifest),
                agency_keys=[a.key for a in agencies_from_manifest(manifest)],
                keywords=keywords,
                scoring=scoring_from_manifest(manifest),
                gate=gate_from_manifest(manifest),
                encoder=self._encoder(model),
                layer=layer,
            )
            try:
                self._classify(index, [WARM_UP_TEXT], None, review=False)
            except Exception as error:
                raise LoadError(
                    f"Warm-up of model {model_id} failed: {error}"
                ) from error
            index.opening = self._catalogue(index)
            with self._swap_lock:
                self._indexes[model_id] = index
            if persist:
                self._persist()
            if index.opening is not None:
                self.second_opinion.warm_up(index.opening)
        logger.info(
            f"Loaded model {model_id} ({collection}) in {time.perf_counter() - start:.1f}s"
        )

    def _catalogue(self, index: LoadedIndex) -> Optional[str]:
        """The second opinion's catalogue for a build; None (and no second opinion) if it can't be built."""
        if self.second_opinion is None or not self.second_opinion.enabled:
            return None
        try:
            examples = self.store.typical_texts(
                index.collection, index.agency_keys, so.CATALOGUE_EXAMPLES
            )
            return so.catalogue([a.agency_name for a in index.agencies], examples)
        except Exception as error:
            logger.warning(
                f"No second opinion for model {index.model_id}: its catalogue can't be built "
                f"({type(error).__name__}: {error})"
            )
            return None

    def unload(self, model_id: str) -> None:
        """Drop a model from this service; its collection stays (retention deletes it)."""
        with self._swap_lock:
            removed = self._indexes.pop(model_id, None)
        if removed is not None:
            self._persist()
            logger.info(f"Unloaded model {model_id}")

    def classify(self, model_id: str, texts: list[str], top_k: Optional[int]):
        """Prediction lists and decision records; raises KeyError for an unknown model."""
        return self._classify(self._indexes[model_id], texts, top_k)

    def _classify(
        self,
        index: LoadedIndex,
        texts: list[str],
        top_k: Optional[int],
        review: bool = True,
    ):
        """review: let the second opinion look at unsure messages (not at warm-up)"""
        reviewing = (
            review
            and self.second_opinion is not None
            and self.second_opinion.enabled
            and index.opening is not None
        )
        with self._encode_lock:
            vectors = index.encoder.encode(texts, "short")
        keyword_vectors = index.keywords.transform(texts)
        scores = score(
            self.store,
            index.collection,
            index.agency_keys,
            vectors,
            keyword_vectors,
            index.scoring,
        )
        if index.layer is not None:
            scores = index.layer.apply(scores, keyword_vectors)
        decisions = decide(scores, index.gate)
        prediction_lists = predictions(
            scores, decisions, index.agencies, index.gate, top_k
        )
        records = decision_records(decisions, index.agencies)
        if reviewing:
            # Outside the encoder lock, so a slow answer doesn't hold up other messages
            prediction_lists, records = self.second_opinion.review(
                index.model_id,
                index.agencies,
                index.gate,
                index.opening,
                texts,
                scores,
                decisions,
                prediction_lists,
                records,
            )
        return prediction_lists, records

    def _model_for(self, manifest: dict) -> EmbeddingModel:
        for model in self.models.values():
            if model.hf_id == manifest["embedding_model"]:
                try:
                    check_model(manifest, model)
                except ArtifactError as error:
                    raise LoadError(str(error)) from error
                return model
        raise LoadError(f"This image does not provide {manifest['embedding_model']}")

    def _check_collection(self, model_id: str, collection: str, manifest: dict) -> None:
        if not self.store.collection_exists(collection):
            raise LoadError(
                f"Collection {collection} is missing; restore it from "
                f"models/indexes/{model_id}/collection.snapshot"
            )
        info = self.store.describe(collection)
        expected = (manifest["vector_store"]["points"], manifest["dim"])
        if info.status != "green":
            raise LoadError(f"Collection {collection} is {info.status}, not green")
        if (info.points, info.dim) != expected:
            raise LoadError(
                f"Collection {collection} has {info.points} points of size {info.dim}; "
                f"the manifest says {expected[0]} of size {expected[1]}"
            )

    def _encoder(self, model: EmbeddingModel):
        key = (model.hf_id, model.revision)
        with self._encoder_lock:
            if key not in self._encoders:
                self._encoders[key] = self.encoder_factory(model)
            return self._encoders[key]

    def _persist(self) -> None:
        self.files.write_json(loaded_set_key(self.index_env), {"models": self.loaded()})
