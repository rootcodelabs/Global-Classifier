"""
Automatic refresh of a living model from a newer dataset version: a new
version row is built next to the serving one and takes its place only if the
gate passes and it loads; the group can be switched back with the rollback.
"""

import json
import os
import time
import warnings

import pandas as pd
import pytest

import builder.refresh as refresh
import builder.rollback as rollback
from builder.index_build import GateConfig, build_index
from builder.publishing import current_prefix, publish
from builder.retention import by_model, old_versions
from embedding_classifier.artifact import QUALITY_REPORT, SNAPSHOT, write_build_files
from embedding_classifier.vector_store import QdrantIndexStore
from tests.conftest import FakeEncoder

PASSING = GateConfig(max_real_wrongly_flagged=1.0)
FAILING = GateConfig(min_top3=1.01)
DATASET = {"id": 2, "major": 1, "minor": 1}


def model_row(
    model_id,
    env="production",
    dataset_id=1,
    major=1,
    status="trained",
    latest=True,
    group="living-group",
    base_models='["fake"]',
):
    return {
        "modelId": model_id,
        "modelName": "living",
        "modelGroupKey": group,
        "major": major,
        "minor": 0,
        "latest": latest,
        "trainingStatus": status,
        "deploymentEnv": env,
        "connectedDsId": dataset_id,
        "baseModels": base_models,
    }


class FakePlatform:
    """data_models and model_training_jobs as dicts, S3 as a dict."""

    def __init__(self, *rows):
        self.rows = {r["modelId"]: dict(r) for r in rows}
        self.jobs: dict[int, tuple[int, str]] = {}
        self.connected: dict[int, list[int]] = {}
        self.s3: dict[str, bytes] = {}
        self.progress_of: dict[int, str] = {}
        # A training job from the GUI is in progress
        self.gui_training = False

    def progress(self, session_id, status, percentage, complete):
        self.progress_of[session_id] = status[0]

    def create_progress_session(self, model_id, model_name, major, minor, latest):
        return 100 + model_id

    def download(self, s3_path, local):
        if s3_path not in self.s3:
            raise FileNotFoundError(s3_path)
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(self.s3[s3_path])

    def try_download(self, s3_path, local):
        try:
            self.download(s3_path, local)
            return True
        except FileNotFoundError:
            return False

    def upload(self, local, s3_path):
        self.s3[s3_path] = local.read_bytes()

    def report_training(self, model_id, results, location):
        self.rows[model_id].update(
            trainingStatus="trained", trainingResults=results, modelS3Location=location
        )

    def report_failed_training(self, model_id, results, location):
        self.rows[model_id].update(
            trainingStatus="training_failed",
            trainingResults=results,
            modelS3Location=location,
        )

    def mark_training_failed(self, model_id):
        self.rows[model_id]["trainingStatus"] = "training_failed"

    def model_row(self, model_id):
        return dict(self.rows[model_id]) if model_id in self.rows else None

    def create_model_version(self, source_model_id, major, dataset):
        source = self.rows[source_model_id]
        new_id = max(self.rows) + 1
        self.rows[new_id] = {
            **model_row(
                new_id,
                env="undeployed",
                dataset_id=int(dataset["id"]),
                major=major,
                status="initiating_training",
                latest=False,
                group=source["modelGroupKey"],
                base_models=source["baseModels"],
            ),
            "modelName": source["modelName"],
        }
        return new_id

    def delete_model(self, model_id):
        del self.rows[model_id]
        self.jobs = {j: v for j, v in self.jobs.items() if v[0] != model_id}

    def training_in_progress(self):
        return self.gui_training or any(
            status == "training-in-progress" for _, status in self.jobs.values()
        )

    def start_training_job(self, model_id, model_name, major, environment):
        if self.training_in_progress():
            return None
        job_id = len(self.jobs) + 1
        self.jobs[job_id] = (model_id, "training-in-progress")
        return job_id

    def finish_training_job(self, job_id, status):
        self.jobs[job_id] = (self.jobs[job_id][0], status)

    def switch_models(self, new_model_id, old_model_id, environment, make_latest):
        if self.rows[old_model_id]["deploymentEnv"] != environment:
            return False
        self.rows[new_model_id]["deploymentEnv"] = environment
        self.rows[old_model_id]["deploymentEnv"] = "undeployed"
        if make_latest:
            group = self.rows[new_model_id]["modelGroupKey"]
            for row in self.rows.values():
                if row["modelGroupKey"] == group:
                    row["latest"] = row["modelId"] == new_model_id
        return True

    def group_models_on_dataset(self, group_key, dataset_id):
        return [
            r
            for r in self.rows.values()
            if r["modelGroupKey"] == group_key and r["connectedDsId"] == int(dataset_id)
        ]

    def connect_model_to_dataset(self, model_id, dataset_id):
        self.connected.setdefault(int(dataset_id), []).append(model_id)

    def resql(self, query, body=None):
        rows = list(self.rows.values())
        if query == "get-production-data-model":
            return [
                {k: v for k, v in r.items() if k != "baseModels"}
                for r in rows
                if r["deploymentEnv"] == "production"
            ][:1]
        if query == "get-data-model-info-by-given-model-id":
            value = self.rows[body["model_id"]]["baseModels"]
            return [{"baseModels": {"type": "jsonb", "value": value}}]
        if query == "get-data-models":
            # Status filtering is left to the refresh, which checks it too
            testing = [r for r in rows if r["deploymentEnv"] == "testing"]
            return sorted(testing, key=lambda r: -r["modelId"])
        if query == "get-highest-major-version":
            majors = [
                r["major"] for r in rows if r["modelGroupKey"] == body["modelGroupKey"]
            ]
            return [{"major": max(majors)}] if majors else []
        raise AssertionError(f"Unexpected query {query}")

    def manifest(self, prefix):
        return json.loads(self.s3[prefix + "manifest.json"])


@pytest.fixture
def qdrant():
    from qdrant_client import QdrantClient

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        yield QdrantIndexStore(QdrantClient(":memory:"))


@pytest.fixture
def living(tmp_path, monkeypatch, qdrant, questions):
    """Model 5 in production, built from dataset 1 the way the GUI build does, and a dataset 2 waiting."""
    platform = FakePlatform(model_row(5))
    first = build_index(
        model_id=5,
        questions=questions,
        model=FakeEncoder.model,
        encoder=FakeEncoder(),
        store=qdrant,
        gate_config=GateConfig(),
        dataset={"id": 1, "major": 1, "minor": 0},
    )
    folder = tmp_path / "first"
    folder.mkdir()
    (folder / SNAPSHOT).write_bytes(b"snapshot of dataset 1")
    write_build_files(folder, first.manifest, first.keywords, first.report)
    publish(platform, folder, current_prefix(5))

    newer = pd.concat(
        [
            questions,
            pd.DataFrame(
                [("ppa", "Politsei- ja Piirivalveamet", "Pass on aegunud, mis nüüd?")],
                columns=questions.columns,
            ),
        ]
    )
    platform.s3["datasets/2/aggregated_dataset.csv"] = (
        newer.rename(columns={"text": "data_item"})[
            ["data_item", "agency_name", "agency_id"]
        ]
        .to_csv(index=False)
        .encode()
    )
    loads, unloads = [], []
    monkeypatch.setattr(refresh, "SHARED_DIR", tmp_path / "shared")
    monkeypatch.setattr(
        refresh, "LOCK_FILE", tmp_path / "shared" / "indexes" / ".refresh.lock"
    )
    monkeypatch.setattr(rollback, "SHARED_DIR", tmp_path / "shared")
    monkeypatch.setattr(refresh, "UNLOAD_DELAY_SECONDS", 0)
    monkeypatch.setattr(refresh, "load_models", lambda: {"fake": FakeEncoder.model})
    monkeypatch.setattr(
        refresh,
        "take_snapshot",
        lambda client, url, key, collection, path: path.write_bytes(
            b"snapshot of " + collection.encode()
        ),
    )
    for module in (refresh, rollback):
        monkeypatch.setattr(
            module,
            "reload_model",
            lambda platform, model_id, env: loads.append((model_id, env)),
        )
        monkeypatch.setattr(
            module,
            "unload_model",
            lambda platform, model_id, env: unloads.append((model_id, env)),
        )
    monkeypatch.setattr(
        refresh.GateConfig, "load", classmethod(lambda cls, path=None: PASSING)
    )
    return platform, loads, unloads


def the_model(platform):
    [model] = refresh.one_per_group(
        refresh.living_models(platform, ("production",), {"fake"})
    )
    return model


def run(platform, qdrant):
    return refresh.refresh_model(
        platform,
        qdrant,
        the_model(platform),
        DATASET,
        refresh.RefreshConfig(),
        None,
        lambda m: FakeEncoder(),
    )


def test_living_models_are_trained_single_key_embedding_models():
    platform = FakePlatform(
        model_row(5),
        model_row(6, env="testing"),
        model_row(7, env="testing", base_models='["estbert"]'),
        model_row(8, env="testing", status="training_failed"),
    )
    models = refresh.living_models(platform, ("production", "testing"), {"fake"})
    assert [(m.model_id, m.environment, m.dataset_id) for m in models] == [
        (5, "production", 1),
        (6, "testing", 1),
    ]


def test_each_group_gets_one_new_version_replacing_production_first():
    platform = FakePlatform(
        model_row(5),
        model_row(6, env="testing"),
        model_row(7, env="testing", group="other"),
        model_row(8, env="testing", group="other"),
    )
    models = refresh.one_per_group(
        refresh.living_models(platform, ("production", "testing"), {"fake"})
    )
    assert [m.model_id for m in models] == [5, 8]


def test_refresh_adds_a_new_version_and_switches_to_it(living, qdrant):
    platform, loads, unloads = living

    assert run(platform, qdrant) == "refreshed"

    new, old = platform.rows[6], platform.rows[5]
    assert (new["major"], new["minor"], new["connectedDsId"]) == (2, 0, 2)
    assert (new["deploymentEnv"], new["latest"], new["trainingStatus"]) == (
        "production",
        True,
        "trained",
    )
    assert new["modelName"] == "living" and new["modelGroupKey"] == "living-group"
    # The old version is kept as it was, only undeployed
    assert (old["major"], old["connectedDsId"], old["trainingStatus"]) == (
        1,
        1,
        "trained",
    )
    assert (old["deploymentEnv"], old["latest"]) == ("undeployed", False)
    assert (
        platform.manifest(current_prefix(6))["vector_store"]["collection"]
        == "gc_index_6"
    )
    assert platform.manifest(current_prefix(6))["dataset"]["id"] == 2
    assert (
        platform.manifest(current_prefix(5))["vector_store"]["collection"]
        == "gc_index_5"
    )
    assert qdrant.collection_exists("gc_index_5") and qdrant.collection_exists(
        "gc_index_6"
    )
    # Loaded before the switch, the old one unloaded after it
    assert loads == [(6, "production")] and unloads == [(5, "production")]
    assert platform.connected == {2: [6]}
    assert platform.jobs == {1: (6, "trained")}
    assert platform.progress_of[106] == "Model Trained And Deployed"
    assert "jobId" not in refresh.read_lock()


def test_the_new_version_is_one_above_the_highest_in_the_group(living, qdrant):
    platform, _, _ = living
    # A version 3.0 was made in the GUI meanwhile
    platform.rows[9] = model_row(9, env="undeployed", major=3, latest=False)

    run(platform, qdrant)

    assert platform.rows[10]["major"] == 4


def test_a_dataset_that_fails_the_gate_keeps_the_old_version_serving(
    living, qdrant, monkeypatch
):
    platform, loads, unloads = living
    monkeypatch.setattr(
        refresh.GateConfig, "load", classmethod(lambda cls, path=None: FAILING)
    )

    assert run(platform, qdrant) == "gate failed"

    new, old = platform.rows[6], platform.rows[5]
    assert (new["trainingStatus"], new["deploymentEnv"], new["latest"]) == (
        "training_failed",
        "undeployed",
        False,
    )
    # Its results are the quality report of the build that failed
    assert new["trainingResults"][0]["index_metrics"]["top3"] is not None
    assert (old["deploymentEnv"], old["latest"]) == ("production", True)
    assert current_prefix(6) + QUALITY_REPORT in platform.s3
    assert current_prefix(6) + "manifest.json" not in platform.s3
    assert not qdrant.collection_exists("gc_index_6")
    assert loads == [] and unloads == []
    assert platform.jobs == {1: (6, "training-failed")}
    assert platform.progress_of[106] == "Training Failed"
    assert platform.connected == {}


def test_a_group_with_a_version_on_the_dataset_is_not_refreshed_from_it_again(
    living, qdrant, monkeypatch
):
    platform, _, _ = living
    assert not refresh.already_built(platform, the_model(platform), 2)
    monkeypatch.setattr(
        refresh.GateConfig, "load", classmethod(lambda cls, path=None: FAILING)
    )

    run(platform, qdrant)

    assert refresh.already_built(platform, the_model(platform), 2)


def test_a_new_version_that_does_not_load_fails_and_the_old_one_serves(
    living, qdrant, monkeypatch
):
    platform, _, unloads = living

    def load_failing(platform, model_id, env):
        raise RuntimeError("smoke test failed")

    monkeypatch.setattr(refresh, "reload_model", load_failing)

    assert run(platform, qdrant) == "load failed"

    assert platform.rows[6]["trainingStatus"] == "training_failed"
    assert platform.rows[6]["deploymentEnv"] == "undeployed"
    assert platform.rows[5]["deploymentEnv"] == "production"
    assert not qdrant.collection_exists("gc_index_6")
    assert unloads == [(6, "production")]
    assert platform.jobs == {1: (6, "training-failed")}


def test_no_switch_when_the_old_version_left_its_environment_meanwhile(
    living, qdrant, monkeypatch
):
    platform, _, unloads = living

    def load_while_an_admin_moves_the_old_version(platform, model_id, env):
        platform.rows[5]["deploymentEnv"] = "testing"

    monkeypatch.setattr(
        refresh, "reload_model", load_while_an_admin_moves_the_old_version
    )

    assert run(platform, qdrant) == "built, not switched"

    assert platform.rows[6]["trainingStatus"] == "trained"
    assert platform.rows[6]["deploymentEnv"] == "undeployed"
    assert platform.rows[5]["latest"] is True
    assert unloads == [(6, "production")]
    assert platform.jobs == {1: (6, "trained")}


def test_a_training_that_started_meanwhile_postpones_the_refresh(living, qdrant):
    platform, _, _ = living
    platform.gui_training = True

    assert run(platform, qdrant) == refresh.POSTPONED

    assert set(platform.rows) == {5} and platform.jobs == {}


def test_an_error_during_the_build_settles_the_job_and_the_new_version(living, qdrant):
    platform, _, _ = living
    del platform.s3["datasets/2/aggregated_dataset.csv"]

    with pytest.raises(FileNotFoundError):
        run(platform, qdrant)

    assert platform.rows[6]["trainingStatus"] == "training_failed"
    assert platform.rows[5]["deploymentEnv"] == "production"
    assert platform.jobs == {1: (6, "training-failed")}
    assert platform.progress_of[106] == "Training Failed"
    assert "jobId" not in refresh.read_lock()


def test_settling_after_the_switch_finishes_the_bookkeeping(living):
    platform, _, unloads = living
    platform.rows[6] = model_row(6, dataset_id=2, major=2)
    platform.rows[5]["deploymentEnv"] = "undeployed"
    platform.jobs[1] = (6, "training-in-progress")

    refresh.settle(
        platform,
        {
            "jobId": 1,
            "modelId": 6,
            "replacing": 5,
            "environment": "production",
            "datasetId": 2,
            "sessionId": 106,
            "stage": refresh.SWITCHED,
        },
    )

    assert platform.jobs == {1: (6, "trained")}
    assert platform.rows[6]["trainingStatus"] == "trained"
    assert platform.progress_of[106] == "Model Trained And Deployed"
    assert unloads == [(5, "production")] and platform.connected == {2: [6]}


@pytest.fixture
def run_main(living, monkeypatch):
    platform, _, _ = living
    monkeypatch.setattr(refresh, "Platform", lambda: platform)
    monkeypatch.setattr(
        refresh.RefreshConfig, "load", classmethod(lambda cls, path=None: cls())
    )
    monkeypatch.setattr(refresh, "latest_successful_dataset", lambda platform: None)
    return platform


def test_main_settles_what_a_crashed_run_left(run_main):
    platform = run_main
    platform.rows[6] = model_row(
        6, env="undeployed", dataset_id=2, major=2, status="initiating_training"
    )
    platform.jobs[1] = (6, "training-in-progress")
    refresh.write_lock(
        jobId=1,
        modelId=6,
        replacing=5,
        environment="production",
        datasetId=2,
        sessionId=106,
        stage=refresh.BUILDING,
    )
    stale = time.time() - refresh.LOCK_MAX_AGE_SECONDS - 60
    os.utime(refresh.LOCK_FILE, (stale, stale))

    refresh.main()

    assert platform.jobs == {1: (6, "training-failed")}
    assert platform.rows[6]["trainingStatus"] == "training_failed"
    assert platform.progress_of[106] == "Training Failed"
    assert not refresh.LOCK_FILE.exists()


def test_main_leaves_a_running_refresh_alone(run_main):
    platform = run_main
    platform.jobs[1] = (6, "training-in-progress")
    refresh.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    refresh.LOCK_FILE.write_text(json.dumps({"pid": os.getppid(), "jobId": 1}))

    refresh.main()

    assert platform.jobs == {1: (6, "training-in-progress")}
    assert refresh.LOCK_FILE.exists()


def test_main_waits_while_a_training_runs(run_main, monkeypatch):
    platform = run_main
    platform.gui_training = True
    monkeypatch.setattr(
        refresh,
        "latest_successful_dataset",
        lambda platform: pytest.fail("refreshed during a training"),
    )

    refresh.main()

    assert set(platform.rows) == {5}


def test_a_lock_written_by_the_earlier_refresh_is_read(living):
    refresh.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    refresh.LOCK_FILE.write_text("1234")

    assert refresh.read_lock() == {"pid": 1234}


def test_rollback_switches_back_to_the_earlier_version(living, qdrant):
    platform, loads, unloads = living
    run(platform, qdrant)

    rollback.rollback(platform, qdrant, 5, 6)

    assert platform.rows[5]["deploymentEnv"] == "production"
    assert platform.rows[6]["deploymentEnv"] == "undeployed"
    # Versions, datasets and latest stay as they are
    assert platform.rows[6]["latest"] is True and platform.rows[5]["connectedDsId"] == 1
    assert loads[-1] == (5, "production") and unloads[-1] == (6, "production")
    # The refresh won't rebuild the version that was rolled back
    assert refresh.already_built(platform, the_model(platform), 2)


def test_rollback_restores_a_deleted_collection(living, qdrant, monkeypatch):
    platform, _, _ = living
    run(platform, qdrant)
    qdrant.delete_collection("gc_index_5")
    restored = []
    monkeypatch.setattr(
        rollback,
        "restore_snapshot",
        lambda url, key, collection, path: restored.append(
            (collection, path.read_bytes())
        ),
    )

    rollback.rollback(platform, qdrant, 5, 6)

    assert restored == [("gc_index_5", b"snapshot of dataset 1")]
    assert platform.rows[5]["deploymentEnv"] == "production"


def test_rollback_needs_two_versions_of_one_model(living, qdrant):
    platform, _, _ = living
    platform.rows[7] = model_row(7, env="undeployed", group="other")
    platform.rows[8] = model_row(8, env="undeployed", latest=False)
    with pytest.raises(RuntimeError, match="different models"):
        rollback.rollback(platform, qdrant, 7, 5)
    with pytest.raises(RuntimeError, match="not serving"):
        rollback.rollback(platform, qdrant, 5, 8)


def test_retention_keeps_the_served_collection_and_the_newest_versions():
    collections = by_model(
        [
            "gc_index_5",
            "gc_index_5_ds2",
            "gc_index_5_ds3",
            "gc_index_5_ds4",
            "gc_index_6",
            "other",
        ]
    )
    assert set(collections) == {"5", "6"}

    # Serving an old version after a rollback: it stays, with the 2 newest others
    assert old_versions(collections["5"], "gc_index_5_ds2", keep_versions=2) == [
        "gc_index_5"
    ]
    assert old_versions(collections["5"], "gc_index_5_ds4", keep_versions=1) == [
        "gc_index_5_ds2",
        "gc_index_5",
    ]


def test_refresh_config_rejects_unknown_environments(tmp_path):
    path = tmp_path / "refresh.json"
    path.write_text(json.dumps({"environments": ["staging"]}))
    with pytest.raises(ValueError, match="staging"):
        refresh.RefreshConfig.load(path)
    # The shipped file loads, whether the refresh is on or off
    refresh.RefreshConfig.load(refresh.CONFIG_FILE)
