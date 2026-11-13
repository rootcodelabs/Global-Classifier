"""Service settings, from environment variables."""

import os
from dataclasses import dataclass, field
from typing import Optional


def _optional_int(name: str) -> Optional[int]:
    value = os.environ.get(name, "").strip()
    return int(value) if value else None


@dataclass(frozen=True)
class Settings:
    # production or testing; names the loaded-set file models/{index_env}/_loaded.json
    index_env: str = field(
        default_factory=lambda: os.environ.get("INDEX_ENV", "testing")
    )
    qdrant_url: str = field(
        default_factory=lambda: os.environ.get("QDRANT_URL", "http://qdrant:6333")
    )
    qdrant_api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("QDRANT_API_KEY") or None
    )
    qdrant_timeout: float = field(
        default_factory=lambda: float(os.environ.get("QDRANT_TIMEOUT", "2"))
    )
    # gRPC (port 6334) carries the 2 requests per agency of each message in about
    # half the time of REST
    qdrant_grpc: bool = field(
        default_factory=lambda: os.environ.get("QDRANT_GRPC", "true").lower() == "true"
    )
    # Build files: from S3 unless a local folder is given (development)
    local_models_dir: Optional[str] = field(
        default_factory=lambda: os.environ.get("LOCAL_MODELS_DIR") or None
    )
    s3_endpoint_url: Optional[str] = field(
        default_factory=lambda: os.environ.get("S3_ENDPOINT_URL")
    )
    s3_access_key_id: Optional[str] = field(
        default_factory=lambda: os.environ.get("S3_ACCESS_KEY_ID")
    )
    s3_secret_access_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("S3_SECRET_ACCESS_KEY")
    )
    s3_region: str = field(
        default_factory=lambda: os.environ.get("S3_REGION", "us-east-1")
    )
    s3_bucket: str = field(
        default_factory=lambda: os.environ.get(
            "S3_DATA_BUCKET_NAME", "global-classifier"
        )
    )
    s3_prefix: str = field(
        default_factory=lambda: os.environ.get("S3_DATA_BUCKET_PATH", "resources")
    )
    # Encoders loaded at startup, by model key; others load with the first index that needs them
    preload_models: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            m.strip()
            for m in os.environ.get(
                "EMBEDDING_MODELS", "multilingual-e5-large-instruct"
            ).split(",")
            if m.strip()
        )
    )
    torch_threads: Optional[int] = field(
        default_factory=lambda: _optional_int("TORCH_THREADS")
    )
    # Production images bake the weights in and set HF_HUB_OFFLINE=1
    offline: bool = field(
        default_factory=lambda: os.environ.get("HF_HUB_OFFLINE") == "1"
    )
    service_name: str = field(
        default_factory=lambda: os.environ.get("SERVICE_NAME", "embedding-classifier")
    )
    # Second opinion from the llm-reranker (docs/ARCHITECTURE.md): off, shadow or on
    second_opinion_mode: str = field(
        default_factory=lambda: (
            os.environ.get("SECOND_OPINION_MODE", "off").strip().lower()
        )
    )
    second_opinion_url: str = field(
        default_factory=lambda: os.environ.get(
            "SECOND_OPINION_URL", "http://llm-reranker:8080"
        )
    )
    second_opinion_timeout_ms: int = field(
        default_factory=lambda: int(os.environ.get("SECOND_OPINION_TIMEOUT_MS", "5000"))
    )
    second_opinion_max_concurrent: int = field(
        default_factory=lambda: int(
            os.environ.get("SECOND_OPINION_MAX_CONCURRENT", "1")
        )
    )
    # How sure the model must be to rescue a message flagged off-topic by a small margin.
    # Measured (layer on): 0.5 rescued 22 test questions and 7 of 48 off-topic messages,
    # 0.9 rescued 12 and 4
    second_opinion_min_probability: float = field(
        default_factory=lambda: float(
            os.environ.get("SECOND_OPINION_MIN_PROBABILITY", "0.9")
        )
    )
    second_opinion_ood_band: float = field(
        default_factory=lambda: float(os.environ.get("SECOND_OPINION_OOD_BAND", "0.03"))
    )
    # How much the model's answer counts against e5's confidences
    second_opinion_weight: float = field(
        default_factory=lambda: float(os.environ.get("SECOND_OPINION_WEIGHT", "0.25"))
    )
    # Which unsure messages are asked about: clarify, ood_band (borderline off-topic) or both.
    # With the classifier layer on, asking about clarify messages broke more answers than it
    # fixed; ood_band alone helped. With the layer off, both helped
    second_opinion_triggers: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            t.strip().lower()
            for t in os.environ.get("SECOND_OPINION_TRIGGERS", "ood_band").split(",")
            if t.strip()
        )
    )
    # The llm-reranker slot this service keeps its catalogue in (production 0, testing 1)
    second_opinion_slot: Optional[int] = field(
        default_factory=lambda: _optional_int("SECOND_OPINION_SLOT")
    )
