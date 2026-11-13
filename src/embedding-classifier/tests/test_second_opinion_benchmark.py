"""The second-opinion benchmark's counting: fixed, broken, rescued and off-topic routed."""

import pandas as pd
import pytest

from tools.second_opinion_benchmark import OFF_TOPIC, model_summary, top1_after


def message(id, truth, trigger, e5_top1="a", source="kb", language="et"):
    return {
        "id": id,
        "truth": truth,
        "trigger": trigger,
        "e5_top1": e5_top1,
        "options": ["a", "b", "c"],
        "source": source,
        "language": language,
    }


def answers(rows):
    return pd.DataFrame(
        [
            {
                "id": id,
                "letter": letter,
                "probability": p,
                "ms": 1000 + i,
                "prompt_tokens": 400,
                "cached_tokens": 100,
                "first_call": i == 0,
                "outcome": "ok",
            }
            for i, (id, letter, p) in enumerate(rows)
        ]
    )


def test_top1_after():
    clarify = message("1", "b", "clarify")
    assert top1_after(clarify, "B", 0.9, 0.5) == ("b", True)
    assert top1_after(clarify, "B", 0.4, 0.5) == ("a", False)
    assert top1_after(clarify, "A", 0.9, 0.5) == ("a", False)
    assert top1_after(clarify, "N", 0.9, 0.5) == ("a", False)
    # A failed call has no letter
    assert top1_after(clarify, float("nan"), float("nan"), 0.5) == ("a", False)
    # Off-topic by a small margin: even A is applied (it leaves out_of_distribution)
    assert top1_after(message("2", "a", "ood_band"), "A", 0.9, 0.5) == ("a", True)


def test_model_summary_counts():
    messages = [
        message("fix", "b", "clarify"),  # e5 wrong, B right
        message("break", "a", "clarify"),  # e5 right, C wrong
        message("rescue", "a", "ood_band", language="ru", source="extra"),
        message("leak", OFF_TOPIC, "ood_band", source="off_topic"),
        message("held", OFF_TOPIC, "ood_band", source="off_topic"),
    ]
    given = answers(
        [
            ("fix", "B", 0.9),
            ("break", "C", 0.6),
            ("rescue", "A", 0.8),
            ("leak", "B", 0.7),
            ("held", "N", 0.9),
        ]
    )
    totals = {"0": {"kb_test": 100, "bands": {}}}

    summary = model_summary(messages, given, totals, time_limit_ms=3000)

    at_half = summary["min_probability_sweep"]["0.5"]
    assert (at_half["fixed"], at_half["broken"]) == (1, 1)
    assert at_half["net_top1_gain_points"] == pytest.approx(0.0)
    assert at_half["borderline_rescued"] == 1
    assert (at_half["off_topic_routed"], at_half["off_topic_seen"]) == (1, 2)
    assert at_half["by_language"]["ru"]["rescued"] == 1
    # At 0.7 the unsure break and the unsure leak no longer apply
    at_07 = summary["min_probability_sweep"]["0.7"]
    assert (at_07["fixed"], at_07["broken"], at_07["off_topic_routed"]) == (1, 0, 1)
    assert summary["answer_mix"]["B"] == pytest.approx(0.4)
    assert summary["ms"]["first_call"] == 1000
    assert summary["checks_at_min_probability_0.5"]["p95_within_time_limit"]
    assert not summary["go"]
