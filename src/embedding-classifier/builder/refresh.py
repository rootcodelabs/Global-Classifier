"""
Automatic refresh of embedding classifier models. When a newer dataset version
reaches Generation_Success, each model group with an e5 data model in the
configured environments (refresh.json) gets a new version built from it, as an
admin's major update in the GUI would make one: a new data model row (the
group's next major version, on the new dataset version, undeployed) and a
training job that keeps the GUI's own trainings waiting meanwhile. The quality
gate runs in enforce mode. If the build passes and loads, one statement moves
the environment from the old version to the new one, and the old one is
unloaded a few seconds later; until then the old version serves. If the build
fails, the new version stays as a failed row and the old one serves on. A
group that already has a version on the dataset version (failed, rolled back
or made by hand) isn't refreshed from it again.

CronManager runs it on the schedule in DSL/CronManager/DSL/embedding_index_refresh.yml:
    python -m builder.refresh
"""

import json
import logging
import os
import shutil
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

import requests

from builder.deploy import smoke_test
from builder.index_build import GateConfig, ScoringConfig, build_index
from builder.platform import (
    DEPLOYED,
    DEPLOYING,
    FAILED,
    IN_PROGRESS,
    SHARED_DIR,
    Platform,
    latest_successful_dataset,
    next_major_version,
)
from builder.publishing import current_prefix, publish
from builder.snapshots import take_snapshot
from builder.training_results import training_results
from embedding_classifier.artifact import QUALITY_REPORT, SNAPSHOT, write_build_files
from embedding_classifier.content import read_aggregated_dataset
from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import Encoder, load_models
from embedding_classifier.vector_store import QdrantIndexStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("index-refresh")

CONFIG_FILE = Path(__file__).with_name("refresh.json")
LOCK_FILE = SHARED_DIR / "indexes" / ".refresh.lock"
# A lock older than this is from a crashed run
LOCK_MAX_AGE_SECONDS = 3 * 3600
ENVIRONMENTS = ("production", "testing")
# Messages that read the old model's id just before the switch still reach it
UNLOAD_DELAY_SECONDS = 10

# Training job statuses, as train_script_starter.sh sets them
JOB_TRAINED = "trained"
JOB_FAILED = "training-failed"

# How far a refresh got, kept in the lock so an interrupted one can be settled
BUILDING = "building"
BUILT = "built"
SWITCHED = "switched"

POSTPONED = "postponed"


@dataclass(frozen=True)
class RefreshConfig:
    enabled: bool = True
    environments: tuple[str, ...] = ENVIRONMENTS
    gate_mode: str = "enforce"
    # Read by the clean-up job, for the collections of earlier refreshes
    keep_versions: int = 3

    @classmethod
    def load(cls, path: Path = CONFIG_FILE) -> "RefreshConfig":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        config = cls(
            **{**data, "environments": tuple(data.get("environments", ENVIRONMENTS))}
        )
        unknown = set(config.environments) - set(ENVIRONMENTS)
        if unknown:
            raise ValueError(f"Unknown environments in {path}: {sorted(unknown)}")
        return config


@dataclass(frozen=True)
class LivingModel:
    """A trained e5 data model that keeps itself up to date."""

    model_id: int
    name: str
    group_key: str
    major: int
    minor: int
    environment: str
    model_key: str
    dataset_id: int


def base_models(value) -> list[str]:
    """data_models.base_models as Resql returns it (a JSONB wrapper or a list)."""
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    if isinstance(value, str):
        value = json.loads(value)
    return list(value or [])


def living_models(platform: Platform, environments, model_keys) -> list[LivingModel]:
    """
    Trained data models in the given environments built with one embedding
    model key: the production one first, then testing ones, newest first.
    """
    rows = []
    if "production" in environments:
        production = platform.resql("get-production-data-model")
        for row in production or []:
            info = platform.resql(
                "get-data-model-info-by-given-model-id", {"model_id": row["modelId"]}
            )
            rows.append({**row, "baseModels": (info or [{}])[0].get("baseModels")})
    if "testing" in environments:
        rows += (
            platform.resql(
                "get-data-models",
                {
                    "training_status": "trained",
                    "model_status": "all",
                    "deployment_env": "testing",
                    "sort_by": "createdAt",
                    "sort_type": "desc",
                    "page": 1,
                    "page_size": 500,
                },
            )
            or []
        )

    models = []
    for row in rows:
        keys = base_models(row.get("baseModels"))
        if (
            row.get("trainingStatus") != "trained"
            or len(keys) != 1
            or keys[0] not in model_keys
        ):
            continue
        if row.get("connectedDsId") is None:
            continue
        models.append(
            LivingModel(
                model_id=int(row["modelId"]),
                name=row.get("modelName", ""),
                group_key=row["modelGroupKey"],
                major=int(row.get("major") or 1),
                minor=int(row.get("minor") or 0),
                environment=row.get("deploymentEnv"),
                model_key=keys[0],
                dataset_id=int(row["connectedDsId"]),
            )
        )
    return models


def one_per_group(models: list[LivingModel]) -> list[LivingModel]:
    """
    The model each group's new version replaces: its production model, or
    else its newest testing one (living_models lists them in that order).
    """
    chosen = {}
    for model in models:
        chosen.setdefault(model.group_key, model)
    return list(chosen.values())


def already_built(platform: Platform, model: LivingModel, dataset_id: int) -> bool:
    """Whether the model's group has a version on the dataset version, whatever its status."""
    versions = platform.group_models_on_dataset(model.group_key, dataset_id)
    if versions:
        listed = ", ".join(
            f"model {v['modelId']} ({v.get('trainingStatus')}, {v.get('deploymentEnv')})"
            for v in versions
        )
        logger.info(
            f"Model {model.model_id}: its group already has a version on dataset {dataset_id} "
            f"({listed}); waiting for a newer dataset version"
        )
    return bool(versions)


def reload_model(platform: Platform, model_id: int, environment: str) -> None:
    """
    Load the model's current files on its environment's classifier, and on the
    other one if it has the model loaded (the test page may load production
    models), then smoke-test each.
    """
    name = f"{model_id}-classifier-ensemble"
    for env in ENVIRONMENTS:
        server = platform.model_server(env)
        if env != environment:
            try:
                ready = requests.get(f"{server}/v2/models/{name}/ready", timeout=10)
            except requests.RequestException:
                continue
            if ready.status_code != 200:
                continue
        response = requests.post(
            f"{server}/v2/repository/models/{name}/load", json={}, timeout=600
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Reloading {name} on {server} failed: {response.status_code} {response.text}"
            )
        smoke_test(server, name)


def unload_model(platform: Platform, model_id: int, environment: str) -> None:
    """Unload a model from an environment's classifier; a failure is only logged."""
    name = f"{model_id}-classifier-ensemble"
    try:
        response = requests.post(
            f"{platform.model_server(environment)}/v2/repository/models/{name}/unload",
            json={},
            timeout=60,
        )
        if response.status_code != 200:
            logger.warning(
                f"Unloading {name} from {environment}: {response.status_code} {response.text}"
            )
    except requests.RequestException as error:
        logger.warning(f"Could not unload {name} from {environment}: {error}")


def settle(platform: Platform, state: dict) -> None:
    """
    Finish what an interrupted refresh left in progress (its state as kept in
    the lock), so the GUI's trainings aren't blocked and its pages show what
    happened. Each step is tried on its own.
    """
    stage = state.get("stage")
    new_id, old_id = state.get("modelId"), state.get("replacing")
    environment = state.get("environment")
    steps = []
    if state.get("jobId"):
        status = JOB_TRAINED if stage in (BUILT, SWITCHED) else JOB_FAILED
        steps.append(
            (
                "training job",
                lambda: platform.finish_training_job(state["jobId"], status),
            )
        )
    if stage == BUILDING and new_id:
        steps.append(("model status", lambda: platform.mark_training_failed(new_id)))
    if state.get("sessionId"):
        progress = DEPLOYED if stage == SWITCHED else FAILED
        steps.append(
            (
                "progress",
                lambda: platform.progress(
                    state["sessionId"], progress, 100, stage == SWITCHED
                ),
            )
        )
    if stage == SWITCHED:
        steps.append(("unload", lambda: unload_model(platform, old_id, environment)))
        steps.append(
            (
                "connected models",
                lambda: platform.connect_model_to_dataset(new_id, state["datasetId"]),
            )
        )
    if stage == BUILT:
        logger.warning(
            f"Model {new_id} was built but may not have replaced model {old_id} in {environment}. "
            f"To switch: python -m builder.rollback --model-id {new_id} --replacing {old_id}"
        )
    for name, step in steps:
        try:
            step()
        except Exception:
            logger.exception(f"Settling the refresh of model {new_id}: {name} failed")


def refresh_model(
    platform: Platform,
    store,
    model: LivingModel,
    dataset: dict,
    config: RefreshConfig,
    cache,
    encoder_factory,
) -> str:
    """Build a new version of a model from a dataset version and switch to it if it passes; returns what happened."""
    dataset_id = int(dataset["id"])
    major = next_major_version(platform, model.group_key)
    new_id = platform.create_model_version(model.model_id, major, dataset)
    job_id = platform.start_training_job(new_id, model.name, major, model.environment)
    if job_id is None:
        # A GUI training started since the check; the next run tries again
        platform.delete_model(new_id)
        return POSTPONED
    logger.info(
        f"Model {model.model_id} ({model.environment}, version {model.major}.{model.minor}, "
        f"dataset {model.dataset_id}): building version {major}.0 as model {new_id} from dataset {dataset_id}"
    )
    state = {
        "jobId": job_id,
        "modelId": new_id,
        "replacing": model.model_id,
        "environment": model.environment,
        "datasetId": dataset_id,
        "stage": BUILDING,
    }
    write_lock(**state)
    work = SHARED_DIR / "indexes" / f"{new_id}-refresh"
    shutil.rmtree(work, ignore_errors=True)
    try:
        state["sessionId"] = platform.create_progress_session(
            new_id, model.name, major, 0, True
        )
        write_lock(**state)
        session = state["sessionId"]
        platform.progress(session, IN_PROGRESS, 30, False)
        csv_path = SHARED_DIR / "datasets" / f"dataset_{dataset_id}.csv"
        platform.download(f"datasets/{dataset_id}/aggregated_dataset.csv", csv_path)
        platform.progress(session, IN_PROGRESS, 40, False)
        embedding_model = load_models()[model.model_key]
        result = build_index(
            model_id=new_id,
            questions=read_aggregated_dataset(str(csv_path)),
            model=embedding_model,
            encoder=encoder_factory(embedding_model),
            store=store,
            gate_config=replace(GateConfig.load(), mode=config.gate_mode),
            dataset={
                "id": dataset_id,
                "major": dataset.get("major"),
                "minor": dataset.get("minor"),
            },
            cache=cache,
            builder_commit=os.environ.get("BUILDER_COMMIT", ""),
            layer_params=ScoringConfig.load().layer_params(),
        )
        prefix = current_prefix(new_id)
        results = training_results(
            [(model.model_key, embedding_model.hf_id, result.report)], prefix
        )
        new = work / "new"
        new.mkdir(parents=True)
        if not result.passed:
            (new / QUALITY_REPORT).write_text(
                json.dumps(result.report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            platform.upload(new / QUALITY_REPORT, prefix + QUALITY_REPORT)
            platform.report_failed_training(new_id, results, prefix)
            failed = [
                c["check"]
                for c in result.report["gate"]["checks"]
                if c["status"] == "failed"
            ]
            logger.warning(
                f"Model {new_id}: dataset {dataset_id} failed the quality gate {failed}; "
                f"model {model.model_id} keeps serving"
            )
            platform.finish_training_job(job_id, JOB_FAILED)
            platform.progress(session, FAILED, 100, False)
            return "gate failed"

        take_snapshot(
            store.client, store_url(), api_key(), result.collection, new / SNAPSHOT
        )
        write_build_files(
            new, result.manifest, result.keywords, result.report, result.layer
        )
        publish(platform, new, prefix)
        platform.progress(session, DEPLOYING, 100, True)
        try:
            reload_model(platform, new_id, model.environment)
        except Exception:
            logger.exception(
                f"Model {new_id} didn't load; model {model.model_id} keeps serving"
            )
            unload_model(platform, new_id, model.environment)
            store.delete_collection(result.collection)
            platform.report_failed_training(new_id, results, prefix)
            platform.finish_training_job(job_id, JOB_FAILED)
            platform.progress(session, FAILED, 100, False)
            return "load failed"

        platform.report_training(new_id, results, prefix)
        state["stage"] = BUILT
        write_lock(**state)
        switched = platform.switch_models(
            new_id, model.model_id, model.environment, make_latest=True
        )
        if switched:
            state["stage"] = SWITCHED
            write_lock(**state)
            logger.info(
                f"Model {new_id} (version {major}.0, dataset {dataset_id}) now serves "
                f"{model.environment} in place of model {model.model_id}"
            )
            time.sleep(UNLOAD_DELAY_SECONDS)
            unload_model(platform, model.model_id, model.environment)
        else:
            logger.warning(
                f"Model {model.model_id} left {model.environment} during the build; "
                f"model {new_id} is built but stays undeployed"
            )
            unload_model(platform, new_id, model.environment)
        try:
            platform.connect_model_to_dataset(new_id, dataset_id)
        except Exception:
            # The GUI's dataset page lags; serving isn't affected
            logger.exception(
                f"Listing model {new_id} among dataset {dataset_id}'s connected models failed"
            )
        platform.finish_training_job(job_id, JOB_TRAINED)
        platform.progress(session, DEPLOYED, 100, True)
        return "refreshed" if switched else "built, not switched"
    except Exception:
        settle(platform, state)
        raise
    finally:
        shutil.rmtree(work, ignore_errors=True)
        write_lock()


def store_url() -> str:
    return os.environ.get("QDRANT_URL", "http://qdrant:6333")


def api_key():
    return os.environ.get("QDRANT_API_KEY") or None


def read_lock() -> dict:
    try:
        value = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    # Earlier versions wrote only the process id
    return value if isinstance(value, dict) else {"pid": value}


def write_lock(**state) -> None:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), **state}), encoding="utf-8")


def holder_running(lock: dict) -> bool:
    """Whether the run holding the lock is alive; where that can't be told, the lock's age decides."""
    pid = lock.get("pid")
    if pid == os.getpid():
        return False
    if not pid or not Path("/proc").is_dir():
        return True
    return Path(f"/proc/{pid}").exists()


def acquire_lock() -> Optional[dict]:
    """
    Take the lock: None if another run holds it, otherwise what an earlier run
    that stopped without finishing left in it ({} if nothing).
    """
    left = {}
    if LOCK_FILE.exists():
        left = read_lock()
        fresh = time.time() - LOCK_FILE.stat().st_mtime < LOCK_MAX_AGE_SECONDS
        if fresh and holder_running(left):
            return None
    write_lock()
    return left


def main() -> None:
    config = RefreshConfig.load()
    if not config.enabled:
        logger.info("Automatic refresh is off (builder/refresh.json)")
        return
    platform = Platform()
    left = acquire_lock()
    if left is None:
        logger.info("Another refresh is running")
        return
    try:
        if left.get("jobId"):
            logger.warning(
                f"An earlier refresh stopped while building model {left.get('modelId')} "
                f"(training job {left['jobId']}, {left.get('stage')}); settling it"
            )
            settle(platform, left)
        if platform.training_in_progress():
            logger.info("A training is running; refreshing next time")
            return
        dataset = latest_successful_dataset(platform)
        if not dataset:
            logger.info("No successful dataset version yet")
            return
        dataset_id = int(dataset["id"])
        stale = [
            m
            for m in one_per_group(
                living_models(platform, config.environments, set(load_models()))
            )
            if m.dataset_id < dataset_id
        ]
        if not stale:
            logger.info(f"Every model is up to date with dataset {dataset_id}")
            return
        models = [m for m in stale if not already_built(platform, m, dataset_id)]
        if not models:
            return
        store = QdrantIndexStore.connect(store_url(), api_key(), timeout=120)
        cache = EmbeddingCache(
            os.environ.get("EMBEDDING_CACHE_DIR", "/app/embedding_cache")
        )
        threads = (
            int(os.environ["TORCH_THREADS"])
            if os.environ.get("TORCH_THREADS")
            else None
        )
        encoders = {}

        def encoder_factory(model):
            if model.key not in encoders:
                encoders[model.key] = Encoder(model, threads=threads)
            return encoders[model.key]

        failures = 0
        for model in models:
            try:
                outcome = refresh_model(
                    platform, store, model, dataset, config, cache, encoder_factory
                )
            except Exception:
                failures += 1
                logger.exception(
                    f"Refreshing model {model.model_id} failed; it keeps serving"
                )
                continue
            logger.info(f"Model {model.model_id}: {outcome}")
            if outcome == POSTPONED:
                logger.info("A training started meanwhile; refreshing next time")
                break
        if failures:
            sys.exit(1)
    finally:
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
