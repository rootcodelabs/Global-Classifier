"""
Contract tests: the service answers the calls the DSL makes today, with a fake
encoder, Qdrant's local mode and build files in a temporary folder.
"""

import json
import warnings

import pytest
from fastapi.testclient import TestClient

from builder.index_build import GateConfig, build_index
from embedding_classifier.artifact import write_build_files
from embedding_classifier.classifier_layer import LAYER_FILE, LayerParams
from embedding_classifier.encoder import EmbeddingModel
from embedding_classifier.vector_store import QdrantIndexStore
from service.app import create_app
from service.build_files import LocalBuildFiles, loaded_set_key
from service.registry import IndexRegistry
from tests.conftest import FakeEncoder

# The body DSL/Ruuter.public/global-classifier/POST/chats/classify.yml sends
CLASSIFY_YML_BODY = {
    "inputs": [
        {
            "name": "TEXT",
            "datatype": "BYTES",
            "shape": [1, 1],
            "data": ["Kuidas pass taotleda?"],
        }
    ]
}


class SwitchableStore:
    """Wraps a store; while down, every call fails as if Qdrant were unreachable."""

    def __init__(self, store):
        self.store = store
        self.down = False

    def __getattr__(self, name):
        attribute = getattr(self.store, name)
        if not callable(attribute):
            return attribute

        def call(*args, **kwargs):
            if self.down:
                raise ConnectionError("Qdrant is unreachable")
            return attribute(*args, **kwargs)

        return call

    def ping(self):
        return not self.down


@pytest.fixture
def qdrant():
    from qdrant_client import QdrantClient

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        yield SwitchableStore(QdrantIndexStore(QdrantClient(":memory:")))


def build(models_dir, store, questions, model_id=42, layer_params=None):
    encoder = FakeEncoder()
    result = build_index(
        model_id=model_id,
        questions=questions,
        model=encoder.model,
        encoder=encoder,
        store=store,
        gate_config=GateConfig(),
        dataset={"id": 1, "major": 1, "minor": 0},
        layer_params=layer_params,
    )
    write_build_files(
        models_dir / "indexes" / str(model_id),
        result.manifest,
        result.keywords,
        result.report,
        result.layer,
    )
    return result


def make_client(models_dir, store, models=None):
    registry = IndexRegistry(
        store=store,
        files=LocalBuildFiles(str(models_dir)),
        index_env="testing",
        encoder_factory=lambda model: FakeEncoder(),
        models=models or {"fake": FakeEncoder.model},
    )
    return TestClient(create_app(registry, start_in_background=False))


@pytest.fixture
def client(tmp_path, qdrant, questions):
    build(tmp_path, qdrant, questions)
    with make_client(tmp_path, qdrant) as client:
        assert (
            client.post("/v2/repository/models/42-classifier-ensemble/load").status_code
            == 200
        )
        yield client


def parse(response):
    """As classify.yml does: JSON.parse(response.body.outputs[0].data[0])"""
    return json.loads(response.json()["outputs"][0]["data"][0])


def test_classify_yml_request(client):
    response = client.post(
        "/v2/models/42-classifier-ensemble/infer", json=CLASSIFY_YML_BODY
    )

    assert response.status_code == 200
    predictions = parse(response)
    assert len(predictions) == 1
    assert predictions[0][0]["agency_id"] == "ppa"
    assert set(predictions[0][0]) == {"agency_id", "agency_name", "confidence"}
    decision = json.loads(response.json()["outputs"][1]["data"][0])
    assert decision[0]["decision"] in ("route", "clarify", "out_of_distribution")


def test_batch_and_top_k(client):
    body = {
        "inputs": [
            {
                "name": "TEXT",
                "datatype": "BYTES",
                "shape": [2, 1],
                "data": [["pass kadunud"], ["tarbija kaebus"]],
            },
            {"name": "top_k", "datatype": "INT32", "shape": [1], "data": [2]},
        ]
    }
    predictions = parse(
        client.post("/v2/models/42-classifier-ensemble/infer", json=body)
    )

    assert len(predictions) == 2
    assert [p["agency_id"] for p in predictions[1] if p["agency_id"] != 0][0] == "ttja"
    assert all(
        len([p for p in result if p["agency_id"] != 0]) == 2 for result in predictions
    )


def test_unknown_model_is_a_400_with_an_error(client):
    response = client.post(
        "/v2/models/7-classifier-ensemble/infer", json=CLASSIFY_YML_BODY
    )
    assert response.status_code == 400
    assert "unknown model" in response.json()["error"]
    assert client.get("/v2/models/7-classifier-ensemble/ready").status_code == 400


def test_test_page_load_ready_and_unload(client, tmp_path):
    for helper in ("pre-processing", "text-classifier", "post-processing"):
        assert client.post(f"/v2/repository/models/42-{helper}/load").status_code == 200
        assert (
            client.post(f"/v2/repository/models/42-{helper}/unload").status_code == 200
        )
    assert client.get("/v2/models/42-classifier-ensemble/ready").status_code == 200
    loaded = json.loads((tmp_path / loaded_set_key("testing")).read_text())
    assert loaded == {"models": ["42"]}

    # unload.yml sends this body for the ensemble
    response = client.post(
        "/v2/repository/models/42-classifier-ensemble/unload",
        json={"unload_dependents": True},
    )
    assert response.status_code == 200
    assert client.get("/v2/models/42-classifier-ensemble/ready").status_code == 400
    assert json.loads((tmp_path / loaded_set_key("testing")).read_text()) == {
        "models": []
    }


def test_loaded_models_come_back_after_a_restart(tmp_path, qdrant, questions):
    build(tmp_path, qdrant, questions)
    with make_client(tmp_path, qdrant) as first:
        first.post("/v2/repository/models/42-classifier-ensemble/load")

    with make_client(tmp_path, qdrant) as restarted:
        assert restarted.get("/v2/health/ready").json()["models"] == ["42"]
        assert (
            restarted.post(
                "/v2/models/42-classifier-ensemble/infer", json=CLASSIFY_YML_BODY
            ).status_code
            == 200
        )


def test_qdrant_down_fails_infer_and_ready_and_recovers(client, qdrant):
    qdrant.down = True
    assert (
        client.post(
            "/v2/models/42-classifier-ensemble/infer", json=CLASSIFY_YML_BODY
        ).status_code
        == 503
    )
    assert client.get("/v2/health/ready").status_code == 503
    assert client.get("/v2/health/live").status_code == 200

    qdrant.down = False
    assert client.get("/v2/health/ready").status_code == 200
    assert (
        client.post(
            "/v2/models/42-classifier-ensemble/infer", json=CLASSIFY_YML_BODY
        ).status_code
        == 200
    )


def test_missing_collection_is_refused_with_how_to_restore(tmp_path, qdrant, questions):
    result = build(tmp_path, qdrant, questions)
    qdrant.delete_collection(result.collection)
    with make_client(tmp_path, qdrant) as client:
        response = client.post("/v2/repository/models/42-classifier-ensemble/load")
    assert response.status_code == 400
    assert "restore it from" in response.json()["error"]


def test_index_from_another_revision_is_refused(tmp_path, qdrant, questions):
    build(tmp_path, qdrant, questions)
    other = EmbeddingModel("fake", FakeEncoder.model.hf_id, "1" * 40)
    with make_client(tmp_path, qdrant, models={"fake": other}) as client:
        response = client.post("/v2/repository/models/42-classifier-ensemble/load")
    assert response.status_code == 400
    assert "was built with" in response.json()["error"]


def test_a_build_with_the_classifier_layer_answers_in_the_same_format(
    tmp_path, qdrant, questions
):
    build(tmp_path, qdrant, questions, layer_params=LayerParams())
    with make_client(tmp_path, qdrant) as client:
        assert (
            client.post("/v2/repository/models/42-classifier-ensemble/load").status_code
            == 200
        )
        response = client.post(
            "/v2/models/42-classifier-ensemble/infer", json=CLASSIFY_YML_BODY
        )
    assert response.status_code == 200
    [predictions] = parse(response)
    assert predictions[0]["agency_id"] == "ppa"
    assert set(predictions[0]) == {"agency_id", "agency_name", "confidence"}
    assert sum(p["confidence"] for p in predictions) == pytest.approx(1.0)


def test_a_changed_classifier_layer_file_is_refused(tmp_path, qdrant, questions):
    build(tmp_path, qdrant, questions, layer_params=LayerParams())
    path = tmp_path / "indexes" / "42" / LAYER_FILE
    path.write_bytes(path.read_bytes() + b"tampered")
    with make_client(tmp_path, qdrant) as client:
        response = client.post("/v2/repository/models/42-classifier-ensemble/load")
    assert response.status_code == 400
    assert "does not match its checksum" in response.json()["error"]


def test_missing_build_files_are_a_400(tmp_path, qdrant):
    with make_client(tmp_path, qdrant) as client:
        response = client.post("/v2/repository/models/99-classifier-ensemble/load")
    assert response.status_code == 400
    assert "99" in response.json()["error"]


def test_startup_waits_for_an_unreadable_loaded_set_file(tmp_path, qdrant, questions):
    build(tmp_path, qdrant, questions)
    LocalBuildFiles(str(tmp_path)).write_json(
        loaded_set_key("testing"), {"models": ["42"]}
    )
    files = LocalBuildFiles(str(tmp_path))
    attempts = []
    read = files.read_json

    def flaky(key):
        attempts.append(key)
        if len(attempts) == 1:
            raise ConnectionError("S3 is still starting")
        return read(key)

    files.read_json = flaky
    registry = IndexRegistry(
        store=qdrant,
        files=files,
        index_env="testing",
        encoder_factory=lambda model: FakeEncoder(),
        models={"fake": FakeEncoder.model},
    )
    registry.start(retry_seconds=0)

    assert len(attempts) == 2
    assert registry.started and registry.loaded() == ["42"]
