"""Dataset check: folds, the cause rules, and a small dataset with one of each problem."""

import numpy as np
import pandas as pd
import pytest

from embedding_classifier.dataset_check import (
    CHECK_LABEL,
    CSV_FILE,
    NO_CLUE,
    OTHER,
    REPORT_FILE,
    SHARED_TOPIC,
    CheckParams,
    cause,
    check,
    fold_ids,
    write_report,
)
from embedding_classifier.scoring import ScoringParams

# Meaning only, so the expected ranks follow from the vectors
DENSE_ONLY = ScoringParams(keyword_weight=0.0)
# With three agencies the labelled agency ranks 0, 1 or 2
THREE_AGENCIES = CheckParams(shared_max_rank=2, check_label_min_rank=2)

MISLABELLED = "Smart-ID PIN-kood on blokeeritud ja ma ei saa sisse"
NO_CLUE_TEXT = "Mida teha?"
SHARED = "Kas passi ja tarbija garantii kehtivad välismaal samamoodi?"


def test_folds_spread_each_agency_evenly():
    truth = np.array([0] * 6 + [1] * 6 + [2] * 5)
    ids = fold_ids(truth, 5, seed=0)
    for agency in range(3):
        sizes = np.bincount(ids[truth == agency], minlength=5)
        assert sizes.max() - sizes.min() <= 1
    assert set(ids) == set(range(5))


@pytest.mark.parametrize(
    "rank, agencies, words, expected",
    [
        (1, 5, 10, NO_CLUE),  # neighbours spread over many agencies
        (7, 1, 4, NO_CLUE),  # very short
        (1, 2, 10, SHARED_TOPIC),
        (2, 2, 10, SHARED_TOPIC),
        (3, 2, 10, OTHER),
        (4, 2, 10, OTHER),
        (5, 2, 10, CHECK_LABEL),
    ],
)
def test_cause_rules(rank, agencies, words, expected):
    assert cause(rank, agencies, words, CheckParams()) == expected


@pytest.fixture
def dataset():
    """Agencies a, b, c with six questions each, plus one question of each problem."""
    rng = np.random.default_rng(0)
    centres = {
        "a": np.array([1.0, 0.0, 0.0]),
        "b": np.array([0.0, 1.0, 0.0]),
        # c leans a little towards b, so a b question ranks a last
        "c": np.array([0.0, 0.3, 1.0]),
    }
    rows, vectors = [], []
    for key, centre in centres.items():
        for i in range(6):
            rows.append(
                (key, f"Agency {key}", f"Agency {key} question number {i} here")
            )
            vectors.append(centre + rng.normal(0, 0.02, 3))
    special = [
        ("a", MISLABELLED, centres["b"]),
        ("a", NO_CLUE_TEXT, np.array([1.0, 1.0, 1.0])),
        ("b", SHARED, np.array([1.0, 0.8, 0.0])),
    ]
    for key, text, vector in special:
        rows.append((key, f"Agency {key}", text))
        vectors.append(vector)
    vectors = np.array(vectors, dtype=np.float32)
    frame = pd.DataFrame(rows, columns=["agency_id", "agency_name", "text"])
    return frame, vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def by_text(result, text):
    return result.questions.set_index("text").loc[text]


def test_each_problem_gets_its_cause(dataset):
    result = check(*dataset, THREE_AGENCIES, DENSE_ONLY)

    mislabelled = by_text(result, MISLABELLED)
    assert mislabelled["cause"] == CHECK_LABEL
    assert mislabelled["predicted_agency_id"] == "b"
    assert mislabelled["label_rank"] == 3
    assert by_text(result, NO_CLUE_TEXT)["cause"] == NO_CLUE
    shared = by_text(result, SHARED)
    assert shared["cause"] == SHARED_TOPIC
    assert shared["predicted_agency_id"] == "a"
    # The ordinary questions are all right
    ordinary = result.questions[result.questions["text"].str.startswith("Agency")]
    assert (ordinary["cause"] == "").all()


def test_agencies_and_pairs(dataset):
    result = check(*dataset, THREE_AGENCIES, DENSE_ONLY)

    agencies = result.agencies.set_index("agency_id")
    assert agencies.loc["a", "questions"] == 8
    assert agencies.loc["a", "top1"] == pytest.approx(6 / 8)
    assert agencies.loc["a", CHECK_LABEL] == 1
    assert agencies.loc["a", NO_CLUE] == 1
    assert agencies["needs_more_examples"].all()
    # Worst agency first
    assert list(result.agencies["top1"]) == sorted(result.agencies["top1"])
    assert [p["agencies"] for p in result.pairs] == [("Agency a", "Agency b")]
    assert result.pairs[0]["examples"] == [(SHARED, "Agency b", "Agency a")]


def test_report_files(dataset, tmp_path):
    result = check(*dataset, THREE_AGENCIES, DENSE_ONLY)
    write_report(result, tmp_path, title="dataset 7")

    mistakes = pd.read_csv(tmp_path / CSV_FILE)
    assert sorted(mistakes["text"]) == sorted([MISLABELLED, NO_CLUE_TEXT, SHARED])
    report = (tmp_path / REPORT_FILE).read_text(encoding="utf-8")
    assert report.startswith("# Dataset check: dataset 7")
    assert "21 questions, 3 agencies" in report
    assert f"| {MISLABELLED} | Agency a | Agency b |" in report
    assert f"| {NO_CLUE_TEXT} | Agency a |" in report
    assert "**Agency a / Agency b**: 1 mistakes" in report
