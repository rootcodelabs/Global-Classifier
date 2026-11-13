"""Question cleaning, passage chunking, titles and the input adapters."""

import pandas as pd

from embedding_classifier.content import (
    clean_questions,
    chunk_passages,
    is_title,
    read_aggregated_dataset,
    sample_passages,
    user_turns,
)
from embedding_classifier.store import agencies_from_frame


def words(n, word="sõna"):
    return " ".join([word] * n)


def test_chunk_emits_once_a_chunk_reaches_80_words():
    passages = chunk_passages("\n".join([words(50), words(30), words(10)]))
    assert [len(p.split()) for p in passages] == [80]


def test_chunk_keeps_only_the_first_160_words():
    passages = chunk_passages(words(200))
    assert [len(p.split()) for p in passages] == [160]


def test_chunk_keeps_a_remainder_of_20_words_and_drops_a_shorter_one():
    assert [
        len(p.split()) for p in chunk_passages("\n".join([words(80), words(20)]))
    ] == [80, 20]
    assert [
        len(p.split()) for p in chunk_passages("\n".join([words(80), words(19)]))
    ] == [80]


def test_chunk_of_79_words_is_only_a_remainder():
    assert [len(p.split()) for p in chunk_passages(words(79))] == [79]


def test_titles_need_two_words():
    assert is_title("Kiiruskaamerad ja trahvid")
    assert not is_title("Kiiruskaamerad")


def test_passages_are_deduplicated_and_capped_per_agency():
    frame = pd.DataFrame(
        [("a", f"tekst {i}") for i in range(10)] + [("a", "tekst 0"), ("b", "muu")],
        columns=["agency_id", "text"],
    )
    sampled = sample_passages(frame, per_agency=4)
    assert sampled.groupby("agency_id").size().to_dict() == {"a": 4, "b": 1}
    assert sampled.equals(sample_passages(frame, per_agency=4))


def test_clean_questions_drops_empty_duplicate_and_shared_questions():
    frame = pd.DataFrame(
        [("a", "A", "  ")]
        + [("a", "A", f"küsimus {i}") for i in range(5)]
        + [("a", "A", "küsimus 0"), ("a", "A", "Ühine küsimus")]
        + [("b", "B", f"teine {i}") for i in range(5)]
        + [("b", "B", "ühine  KÜSIMUS")],
        columns=["agency_id", "agency_name", "text"],
    )
    kept, warnings = clean_questions(frame)

    assert sorted(kept["text"]) == sorted(
        [f"küsimus {i}" for i in range(5)] + [f"teine {i}" for i in range(5)]
    )
    assert any("several agencies" in w for w in warnings)


def test_agencies_with_fewer_than_5_questions_are_left_out_with_a_warning():
    frame = pd.DataFrame(
        [("a", "A", f"küsimus {i}") for i in range(5)]
        + [("b", "B", f"teine {i}") for i in range(4)],
        columns=["agency_id", "agency_name", "text"],
    )
    kept, warnings = clean_questions(frame)

    assert set(kept["agency_id"]) == {"a"}
    assert warnings == ["Left out B (b): 4 questions, fewer than 5"]


def test_numeric_agency_ids_stay_integers(tmp_path):
    path = tmp_path / "aggregated_dataset.csv"
    path.write_text(
        "data_item,agency_name,agency_id\nKüsimus,Maksuamet,123\nTeine,Politsei,45\n",
        encoding="utf-8",
    )

    agencies = agencies_from_frame(read_aggregated_dataset(str(path)))

    assert [a.agency_id for a in agencies] == [123, 45]
    assert all(type(a.agency_id) is int for a in agencies)


def test_text_agency_ids_stay_strings(tmp_path):
    path = tmp_path / "aggregated_dataset.csv"
    path.write_text(
        "data_item,agency_name,agency_id\nKüsimus,PPA,ppa\n", encoding="utf-8"
    )

    assert agencies_from_frame(read_aggregated_dataset(str(path)))[0].agency_id == "ppa"


def test_user_turns_drop_assistant_replies():
    conversation = "user: Tere! Kuidas passi taotleda? assistant: Politsei teeninduses. user: Aitäh"
    assert user_turns(conversation) == "Tere! Kuidas passi taotleda?\nAitäh"
    assert user_turns("  Lihtne tekst ") == "Lihtne tekst"
