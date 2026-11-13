"""
The index builder end to end with the fake encoder and Qdrant's local mode:
split, calibration, the gate in report and enforce mode, the report and
training results, the job's progress, deploy and switch calls, and retention.
"""

import json
import warnings
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

import builder.cli as cli
from builder.index_build import (
    ENFORCE,
    GateConfig,
    ScoringConfig,
    build_index,
    split_questions,
)
from builder.retention import to_keep
from builder.training_results import training_results
from embedding_classifier.artifact import (
    MANIFEST,
    read_build_files,
    read_layer,
    write_build_files,
)
from embedding_classifier.classifier_layer import LAYER_FILE, LayerParams
from embedding_classifier.vector_store import QdrantIndexStore
from tests.conftest import FakeEncoder

IMPOSSIBLE = GateConfig(min_top3=1.01)


@pytest.fixture
def qdrant():
    from qdrant_client import QdrantClient

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        yield QdrantIndexStore(QdrantClient(":memory:"))


def build(store, questions, gate=GateConfig(), model_id=5, layer_params=None):
    encoder = FakeEncoder()
    return build_index(
        model_id=model_id,
        questions=questions,
        model=encoder.model,
        encoder=encoder,
        store=store,
        gate_config=gate,
        dataset={"id": 3, "major": 1, "minor": 2},
        layer_params=layer_params,
    )


def test_split_holds_out_at_least_one_question_per_agency(questions):
    split = split_questions(questions)
    for agency, group in questions.groupby("agency_id"):
        rows = set(group.index)
        assert len(rows & set(split["test"])) >= 1
        assert len(rows & set(split["calibration"])) >= 1
    assert sorted(np.concatenate(list(split.values()))) == list(questions.index)


def test_build_creates_the_collection_and_a_complete_report(qdrant, questions):
    result = build(qdrant, questions)

    assert result.passed and result.collection == "gc_index_5"
    names = [c.name for c in qdrant.client.get_collections().collections]
    assert names == ["gc_index_5"]  # the evaluation collection is gone
    # Stored and test questions are in the final index; calibration is held out
    assert result.manifest["vector_store"]["points"] == len(questions) - 3
    assert (
        qdrant.describe("gc_index_5").points
        == result.manifest["vector_store"]["points"]
    )
    assert [a["agency_id"] for a in result.manifest["agencies"]] == [
        "idee",
        "ppa",
        "ttja",
    ]
    assert result.manifest["dataset"] == {"id": 3, "major": 1, "minor": 2}
    report = result.report
    assert report["gate"]["mode"] == "report"
    assert {c["check"] for c in report["gate"]["checks"]} == {
        "top3",
        "real_wrongly_flagged",
        "top1_regression",
        "routed_regression",
    }
    assert report["metrics"]["test_questions"] == 3
    assert any("fewer than 300" in w for w in report["warnings"])


def test_a_build_without_the_layer_is_as_before(qdrant, questions):
    result = build(qdrant, questions)

    assert result.layer is None
    assert result.manifest["format_version"] == 1
    assert result.manifest["scoring"]["method"] == "knn_keywords"
    assert "classifier_layer" not in result.manifest["scoring"]
    assert result.report["scoring"] == {"method": "knn_keywords"}


def test_a_build_with_the_classifier_layer(qdrant, questions, tmp_path):
    result = build(qdrant, questions, layer_params=LayerParams())

    assert result.passed and result.layer is not None
    manifest = result.manifest
    assert manifest["format_version"] == 2
    assert manifest["scoring"]["method"] == "knn_keywords_classifier"
    assert manifest["scoring"]["classifier_layer"] == result.layer.describe()
    scoring = result.report["scoring"]
    assert scoring["method"] == "knn_keywords_classifier"
    assert set(scoring["calibration_top1"]) == {"knn", "keywords", "combined"}
    # Trained on the final index's rows: every agency has coefficients
    assert result.layer.coef.shape[0] == 3

    written = write_build_files(
        tmp_path, manifest, result.keywords, result.report, result.layer
    )
    assert LAYER_FILE in written["files"]
    read_manifest, _ = read_build_files(tmp_path)
    loaded = read_layer(tmp_path, read_manifest)
    assert loaded.weights == result.layer.weights


def test_one_agency_builds_without_the_layer(qdrant, questions):
    only_ppa = questions[questions["agency_id"] == "ppa"].reset_index(drop=True)
    result = build(qdrant, only_ppa, layer_params=LayerParams())

    assert result.passed and result.layer is None
    assert result.manifest["scoring"]["method"] == "knn_keywords"
    assert any("needs at least two agencies" in w for w in result.report["warnings"])


def test_report_mode_deploys_a_build_that_misses_a_threshold(qdrant, questions):
    result = build(qdrant, questions, gate=IMPOSSIBLE)
    assert result.passed
    assert result.report["gate"]["passed"] is False
    assert qdrant.collection_exists("gc_index_5")


def test_enforce_mode_stops_a_failing_build_and_leaves_no_collection(qdrant, questions):
    result = build(qdrant, questions, gate=replace(IMPOSSIBLE, mode=ENFORCE))
    assert not result.passed and result.manifest is None
    assert qdrant.client.get_collections().collections == []


def test_evaluation_collection_is_deleted_when_the_build_fails(
    qdrant, questions, monkeypatch
):
    def broken(*args, **kwargs):
        raise RuntimeError("Qdrant went away")

    monkeypatch.setattr(qdrant, "agency_scores", broken)
    with pytest.raises(RuntimeError):
        build(qdrant, questions)
    assert qdrant.client.get_collections().collections == []


def test_training_results_keep_the_trainers_meanings(qdrant, questions):
    report = build(qdrant, questions).report
    [entry] = training_results(
        [
            (
                "multilingual-e5-large-instruct",
                "intfloat/multilingual-e5-large-instruct",
                report,
            )
        ],
        "models/indexes/5/",
    )

    names, precision, f1 = entry["metrics"]
    assert names == [
        "ID.ee",
        "Politsei- ja Piirivalveamet",
        "Tarbijakaitse ja Tehnilise Järelevalve Amet",
    ]
    assert entry["avg_accuracy"] == pytest.approx(np.mean(precision))
    assert entry["avg_f1"] == pytest.approx(np.mean(f1))
    assert entry["combined_score"] == pytest.approx(
        0.7 * entry["avg_accuracy"] + 0.3 * entry["avg_f1"]
    )
    assert set(entry["variant"]) == {
        "name",
        "base_model",
        "full_model_name",
        "ood_method",
        "type",
        "uncertainty_strategy",
        "human_handoff_threshold",
        "confidence_scaling",
    }
    assert entry["variant"]["name"] == "multilingual-e5-large-instruct"
    assert "top3" in entry["index_metrics"]
    with pytest.raises(ValueError):
        training_results([], "x")


class FakePlatform:
    """Records the job's calls; S3 is a dict and the shared volume a temporary folder."""

    def __init__(self, csv_text):
        self.s3 = {"datasets/3/aggregated_dataset.csv": csv_text.encode("utf-8")}
        self.calls = []
        # The data model serving production while the job runs
        self.serving = None
        self.load_fails = False

    def progress(self, session_id, status, percentage, complete):
        self.calls.append(("progress", status[0], percentage, complete))

    def download(self, s3_path, local):
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(self.s3[s3_path])

    def upload(self, local, s3_path):
        self.s3[s3_path] = local.read_bytes()

    def resql(self, query, body=None):
        return [
            {"id": 3, "major": 1, "minor": 2, "generationStatus": "Generation_Success"}
        ]

    def report_training(self, model_id, results, location):
        self.calls.append(("report", model_id, location, len(results)))

    def report_failed_training(self, model_id, results, location):
        self.calls.append(("failed", model_id, location, len(results)))

    def production_model_id(self):
        return self.serving

    def switch_models(self, new, old, environment, make_latest):
        self.calls.append(("switch", new, old, environment, make_latest))
        return True

    def set_environment(self, model_id, environment):
        self.calls.append(("environment", model_id, environment))


@pytest.fixture
def job(tmp_path, monkeypatch, qdrant, questions):
    csv = questions.rename(columns={"text": "data_item"})[
        ["data_item", "agency_name", "agency_id"]
    ].to_csv(index=False)
    platform = FakePlatform(csv)
    monkeypatch.setattr(cli, "SHARED_DIR", tmp_path)
    monkeypatch.setattr(cli, "Encoder", lambda model, threads=None: FakeEncoder())
    monkeypatch.setattr(cli, "get_model", lambda key: FakeEncoder.model)
    monkeypatch.setattr(
        cli.QdrantIndexStore, "connect", classmethod(lambda cls, *a, **k: qdrant)
    )
    monkeypatch.setattr(
        cli,
        "take_snapshot",
        lambda client, url, key, collection, path: path.write_bytes(b"snapshot"),
    )

    def load(platform, model_id, env):
        if platform.load_fails:
            raise RuntimeError("Smoke test failed")
        platform.calls.append(("load", model_id, env))

    monkeypatch.setattr(cli, "reload_model", load)
    monkeypatch.setattr(
        cli,
        "unload_model",
        lambda platform, model_id, env: platform.calls.append(
            ("unload", model_id, env)
        ),
    )
    monkeypatch.setattr(cli, "UNLOAD_DELAY_SECONDS", 0)
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", str(tmp_path / "cache"))

    def run(target, serving=None):
        platform.serving = serving
        args = cli.parse_args(
            [
                "--model_types",
                '["fake"]',
                "--model_id",
                "5",
                "--job_id",
                "1",
                "--dataset_id",
                "3",
                "--model_name",
                "m",
                "--major_version",
                "1",
                "--minor_version",
                "0",
                "--latest",
                "true",
                "--deployment_environment",
                target,
                "--session_id",
                "9",
            ]
        )
        cli.run(args, platform)
        return platform

    run.platform = platform
    return run


def test_job_reports_progress_like_the_trainer_and_deploys(job, tmp_path):
    platform = job("testing")

    assert platform.calls == [
        ("progress", "Training In-Progress", 30, False),
        ("progress", "Training In-Progress", 40, False),
        ("report", 5, "models/indexes/5/", 1),
        ("progress", "Deploying Model", 100, True),
        ("load", 5, "testing"),
        ("environment", 5, "testing"),
        ("progress", "Model Trained And Deployed", 100, True),
    ]
    # The job builds with builder/scoring.json as shipped
    layer_files = (LAYER_FILE,) if ScoringConfig.load().classifier_layer else ()
    files = (
        "manifest.json",
        "keywords.json",
        "quality_report.json",
        "collection.snapshot",
    ) + layer_files
    # The current build, and the same files kept as the version of dataset 3
    stored = {k for k in platform.s3 if k.startswith("models/indexes/5/")}
    assert stored == {f"models/indexes/5/{n}" for n in files} | {
        f"models/indexes/5/versions/ds3/{n}" for n in files
    }
    folder = tmp_path / "check"
    folder.mkdir()
    for name in files:
        (folder / name).write_bytes(platform.s3[f"models/indexes/5/{name}"])
    manifest, _ = read_build_files(folder)
    assert set(manifest["files"]) == {
        "keywords.json",
        "quality_report.json",
        "collection.snapshot",
    } | set(layer_files)
    assert MANIFEST not in manifest["files"]


def test_job_for_undeployed_skips_the_deploy_call(job):
    platform = job("undeployed")
    assert not [c for c in platform.calls if c[0] in ("load", "environment", "switch")]
    assert platform.calls[-1] == ("progress", "Model Trained And Deployed", 100, True)


def test_job_takes_production_from_the_serving_model_after_it_loads(job):
    platform = job("production", serving=4)

    steps = [c for c in platform.calls if c[0] != "progress"]
    assert steps == [
        ("report", 5, "models/indexes/5/", 1),
        ("load", 5, "production"),
        ("switch", 5, 4, "production", False),
        ("unload", 4, "production"),
    ]


def test_job_whose_model_does_not_load_leaves_production_alone(job):
    job.platform.load_fails = True
    with pytest.raises(RuntimeError):
        job("production", serving=4)

    steps = [c for c in job.platform.calls if c[0] not in ("progress", "report")]
    assert steps == [("unload", 5, "production")]


def test_job_for_the_first_production_model_takes_production(job):
    platform = job("production", serving=None)
    assert ("environment", 5, "production") in platform.calls
    assert not [c for c in platform.calls if c[0] in ("switch", "unload")]


def test_gui_builds_enforce_the_quality_gate():
    assert GateConfig.load().mode == ENFORCE


def test_job_failing_the_gate_is_marked_failed_with_its_results(
    job, monkeypatch, qdrant
):
    monkeypatch.setattr(
        cli.GateConfig,
        "load",
        classmethod(lambda cls: replace(IMPOSSIBLE, mode=ENFORCE)),
    )
    with pytest.raises(cli.GateFailed):
        job("production", serving=4)

    platform = job.platform
    assert ("failed", 5, "models/indexes/5/", 1) in platform.calls
    # Nothing deployed and nothing switched: the serving model stays
    assert not [
        c for c in platform.calls if c[0] in ("report", "load", "switch", "environment")
    ]
    assert [k for k in platform.s3 if k.startswith("models/")] == [
        "models/indexes/5/quality_report.json"
    ]
    assert qdrant.client.get_collections().collections == []


def test_retention_keeps_deployed_recent_and_new_builds():
    now = datetime(2026, 10, 30, tzinfo=timezone.utc)

    def row(model_id, env, days_ago):
        return {
            "modelId": model_id,
            "deploymentEnv": env,
            "lastTrained": (now - timedelta(days=days_ago)).isoformat(),
        }

    rows = [
        row(1, "undeployed", 60),
        row(2, "testing", 50),
        row(3, "undeployed", 40),
        row(4, "undeployed", 30),
        row(5, "undeployed", 20),
        row(6, "undeployed", 10),
        row(7, "undeployed", 2),
    ]
    keep = to_keep(
        [str(i) for i in range(1, 9)], rows, "8", keep_recent=3, keep_days=7, now=now
    )

    # 8 is production and 2 testing; 7, 6 and 5 are the 3 most recent others
    # (7 is also within 7 days); 1, 3 and 4 go
    assert keep == {"8", "2", "7", "6", "5"}


def test_questions_read_from_csv_keep_numeric_ids(tmp_path):
    path = tmp_path / "data.csv"
    pd.DataFrame({"data_item": ["a"], "agency_name": ["A"], "agency_id": [12]}).to_csv(
        path, index=False
    )
    assert json.dumps(int(pd.read_csv(path)["agency_id"][0])) == "12"


def test_a_single_agency_builds_and_routes_or_flags_off_topic(qdrant, questions):
    from embedding_classifier.artifact import agencies_from_manifest, gate_from_manifest
    from embedding_classifier.gate import decide
    from embedding_classifier.output import predictions
    from embedding_classifier.scoring import ScoringParams, score

    only_ppa = questions[questions["agency_id"] == "ppa"].reset_index(drop=True)
    result = build(qdrant, only_ppa)

    assert result.passed
    assert any("Only one agency" in w for w in result.report["warnings"])
    gate = gate_from_manifest(result.manifest)
    encoder = FakeEncoder()
    texts = ["Lapse pass on kadunud", "tomat tomat tomat"]
    scores = score(
        qdrant,
        result.collection,
        ["ppa"],
        encoder.encode(texts),
        result.keywords.transform(texts),
        ScoringParams(),
    )
    decisions = decide(scores, gate)
    lists = predictions(
        scores, decisions, agencies_from_manifest(result.manifest), gate
    )

    assert decisions[0].decision == "route" and lists[0][0]["agency_id"] == "ppa"
    assert (
        decisions[1].decision == "out_of_distribution" and lists[1][0]["agency_id"] == 0
    )
