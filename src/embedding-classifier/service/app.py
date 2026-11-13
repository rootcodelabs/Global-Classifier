"""
FastAPI app that answers the Triton v2 calls the DSL makes today
(classify.yml, and the test page's load, unload and classify), so switching
the model server URLs in constants.ini is the only DSL change.

Run (one worker per container):
    uvicorn service.app:create_app --factory --host 0.0.0.0 --port 8000
"""

import re
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Body, FastAPI
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from embedding_classifier.output import infer_outputs
from service.registry import IndexRegistry, LoadError

ENSEMBLE = "classifier-ensemble"
# Triton's helper models: the test page loads and unloads them; here they are no-ops
HELPER_MODELS = ("pre-processing", "text-classifier", "post-processing")
MODEL_NAME = re.compile(
    r"^(?P<id>.+)-(?P<part>classifier-ensemble|pre-processing|text-classifier|post-processing)$"
)


class InferInput(BaseModel):
    name: str
    datatype: str = "BYTES"
    shape: list[int] = []
    data: list[Any]


class InferRequest(BaseModel):
    inputs: list[InferInput]


def error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


def parse_name(name: str) -> tuple[Optional[str], Optional[str]]:
    match = MODEL_NAME.match(name)
    return (match["id"], match["part"]) if match else (None, None)


def create_app(
    registry: Optional[IndexRegistry] = None, start_in_background: bool = True
) -> FastAPI:
    """
    Args:
        registry: The index registry; built from environment settings if None
        start_in_background: Start the registry after the server is up, so
            /v2/health/live answers while encoders and indexes load
    """
    if registry is None:
        registry = registry_from_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if start_in_background:
            threading.Thread(target=registry.start, name="startup", daemon=True).start()
        else:
            registry.start()
        yield

    app = FastAPI(title="Global Classifier embedding classifier", lifespan=lifespan)
    app.state.registry = registry

    @app.get("/v2/health/live")
    def live():
        return {"live": True}

    @app.get("/v2/health/ready")
    def ready():
        if not registry.started:
            return error(503, "Starting")
        if not registry.ready():
            return error(503, "Qdrant is not reachable")
        return {"ready": True, "models": registry.loaded()}

    @app.post("/v2/repository/index")
    def repository_index(body: dict = Body(default={})):
        return [
            {"name": f"{m}-{ENSEMBLE}", "version": "1", "state": "READY"}
            for m in registry.loaded()
        ]

    @app.post("/v2/repository/models/{name}/load")
    def load(name: str, body: dict = Body(default={})):
        model_id, part = parse_name(name)
        if model_id is None:
            return error(400, f"Unknown model name {name}")
        if part in HELPER_MODELS:
            return {}
        try:
            registry.load(model_id)
        except LoadError as exc:
            logger.warning(f"Load of model {model_id} refused: {exc}")
            return error(400, str(exc))
        return {}

    @app.post("/v2/repository/models/{name}/unload")
    def unload(name: str, body: dict = Body(default={})):
        model_id, part = parse_name(name)
        if model_id is None:
            return error(400, f"Unknown model name {name}")
        if part == ENSEMBLE:
            registry.unload(model_id)
        return {}

    @app.get("/v2/models/{name}/ready")
    def model_ready(name: str):
        model_id, part = parse_name(name)
        if part == ENSEMBLE and registry.is_loaded(model_id):
            return {}
        return error(400, f"Request for unknown model: '{name}' is not ready")

    @app.post("/v2/models/{name}/infer")
    def infer(name: str, request: InferRequest):
        start = time.perf_counter()
        model_id, part = parse_name(name)
        if part != ENSEMBLE or not registry.is_loaded(model_id):
            return error(400, f"Request for unknown model: '{name}' is not found")
        text_input = next((i for i in request.inputs if i.name == "TEXT"), None)
        if text_input is None:
            return error(400, "Missing input TEXT")
        texts = [str(item) for item in flatten(text_input.data)]
        if not texts:
            return error(400, "Input TEXT is empty")
        top_k_input = next((i for i in request.inputs if i.name == "top_k"), None)
        top_k = (
            int(flatten(top_k_input.data)[0])
            if top_k_input and top_k_input.data
            else None
        )

        try:
            prediction_lists, decisions = registry.classify(model_id, texts, top_k)
        except KeyError:
            return error(400, f"Request for unknown model: '{name}' is not found")
        except Exception as exc:
            logger.error(
                f"Inference with model {model_id} failed: {type(exc).__name__}: {exc}"
            )
            return error(503, f"Inference failed: {type(exc).__name__}")

        ms = (time.perf_counter() - start) * 1000
        for d in decisions:
            logger.info(
                f"model={model_id} decision={d['decision']} margin={d['margin']:.3f} "
                f"top_similarity={d['top_similarity']:.3f} latency_ms={ms:.0f}"
            )
        return {
            "model_name": name,
            "model_version": "1",
            "outputs": infer_outputs(prediction_lists, decisions),
        }

    return app


def flatten(items: list) -> list:
    """Triton sends shape [n, 1] inputs as nested lists."""
    flat = []
    for item in items:
        if isinstance(item, list):
            flat.extend(flatten(item))
        else:
            flat.append(item)
    return flat


def registry_from_settings() -> IndexRegistry:
    from embedding_classifier.encoder import Encoder
    from embedding_classifier.vector_store import QdrantIndexStore
    from service import build_files, logs
    from service.second_opinion import SecondOpinion, SecondOpinionSettings
    from service.settings import Settings

    settings = Settings()
    logs.configure(settings.service_name)
    second_opinion = SecondOpinion(
        SecondOpinionSettings(
            mode=settings.second_opinion_mode,
            url=settings.second_opinion_url,
            timeout_ms=settings.second_opinion_timeout_ms,
            max_concurrent=settings.second_opinion_max_concurrent,
            min_probability=settings.second_opinion_min_probability,
            ood_band=settings.second_opinion_ood_band,
            weight=settings.second_opinion_weight,
            triggers=settings.second_opinion_triggers,
            slot=settings.second_opinion_slot,
        )
    )
    logger.info(f"Second opinion mode {settings.second_opinion_mode}")
    store = QdrantIndexStore.connect(
        settings.qdrant_url,
        settings.qdrant_api_key,
        timeout=settings.qdrant_timeout,
        prefer_grpc=settings.qdrant_grpc,
    )

    def encoder_factory(model):
        return Encoder(
            model, threads=settings.torch_threads, local_files_only=settings.offline
        )

    return IndexRegistry(
        store=store,
        files=build_files.from_settings(settings),
        index_env=settings.index_env,
        encoder_factory=encoder_factory,
        preload_models=settings.preload_models,
        second_opinion=second_opinion,
    )
