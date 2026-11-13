"""The output must be what today's post-processing returns and classify.yml parses."""

import json

import numpy as np

from embedding_classifier.gate import GateParams, decide
from embedding_classifier.output import decision_records, infer_outputs, predictions
from embedding_classifier.scoring import Scores
from embedding_classifier.store import Agency

AGENCIES = [
    Agency(101, "Politsei- ja Piirivalveamet"),
    Agency(7, "Tööinspektsioon"),
    Agency(55, "Maksu- ja Tolliamet"),
]
GATE = GateParams(ood_cutoff=0.5, route_margin=0.3, temperature=0.1)


def scores(dense_rows, fused_rows):
    dense = np.array(dense_rows, dtype=float)
    return Scores(
        dense=dense,
        keywords=np.zeros_like(dense),
        fused=np.array(fused_rows, dtype=float),
    )


def classify(s, top_k=None):
    decisions = decide(s, GATE)
    lists = predictions(s, decisions, AGENCIES, GATE, top_k)
    return lists, decision_records(decisions, AGENCIES)


def parse_like_classify_yml(outputs):
    """classify.yml: JSON.parse(response.body.outputs[0].data[0])"""
    return json.loads(outputs[0]["data"][0])


def test_top_k_predictions_are_todays_format():
    lists, records = classify(scores([[0.9, 0.6, 0.5]], [[1.2, 0.6, 0.5]]))
    outputs = infer_outputs(lists, records)

    assert outputs[0]["name"] == "TOP_K_PREDICTIONS"
    assert outputs[0]["datatype"] == "BYTES" and outputs[0]["shape"] == [1]
    parsed = parse_like_classify_yml(outputs)
    assert len(parsed) == 1
    assert [p["agency_id"] for p in parsed[0]] == [101, 7, 55]
    assert list(parsed[0][0]) == ["agency_id", "agency_name", "confidence"]
    confidence = [p["confidence"] for p in parsed[0]]
    assert confidence == sorted(confidence, reverse=True)
    # Same serialisation as today's json.dumps(top_k_results): default separators, ASCII escapes
    assert outputs[0]["data"][0] == json.dumps(lists)
    assert '"agency_name": "T\\u00f6\\u00f6inspektsioon"' in outputs[0]["data"][0]


def test_off_topic_message_gets_the_ood_entry_first():
    lists, _ = classify(scores([[0.4, 0.3, 0.2]], [[1.2, 0.6, 0.5]]))
    first, top_agency = lists[0][0], lists[0][1]

    assert first == {
        "agency_id": 0,
        "agency_name": "out_of_distribution",
        "confidence": 1.0,
    }
    assert type(first["agency_id"]) is int
    assert len(lists[0]) == 4
    # A caller that picks the highest confidence gets off-topic too
    assert max(lists[0], key=lambda p: p["confidence"]) is first
    assert top_agency["confidence"] > 0.5


def test_top_k_limits_the_agencies():
    lists, _ = classify(scores([[0.9, 0.6, 0.5]], [[1.2, 0.6, 0.5]]), top_k=2)
    assert len(lists[0]) == 2


def test_decision_output():
    lists, records = classify(
        scores(
            [[0.9, 0.6, 0.5], [0.9, 0.85, 0.8], [0.4, 0.3, 0.2]],
            [[1.2, 0.6, 0.5], [1.0, 0.95, 0.9], [1.3, 0.2, 0.1]],
        )
    )
    decision = json.loads(infer_outputs(lists, records)[1]["data"][0])

    assert [d["decision"] for d in decision] == [
        "route",
        "clarify",
        "out_of_distribution",
    ]
    assert [d["candidates"] for d in decision] == [[101], [101, 7, 55], []]
    assert set(decision[0]) == {"decision", "margin", "top_similarity", "candidates"}


def test_batch_gives_one_list_per_message():
    lists, _ = classify(scores([[0.9, 0.6, 0.5]] * 3, [[1.2, 0.6, 0.5]] * 3))
    assert len(parse_like_classify_yml(infer_outputs(lists, []))) == 3
