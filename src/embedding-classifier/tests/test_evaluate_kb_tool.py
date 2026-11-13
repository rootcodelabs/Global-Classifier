"""The knowledge base evaluation CLI's protocol helpers."""

import numpy as np
import pandas as pd

from tools.evaluate_kb import (
    off_topic_list,
    read_off_topic,
    split_questions,
    without_test_content,
)


def test_split_is_50_10_40_per_agency_and_repeatable():
    questions = pd.DataFrame(
        {"agency_id": ["a"] * 20 + ["b"] * 10, "question": [f"q{i}" for i in range(30)]}
    )
    split = split_questions(questions, seed=0)

    a = questions.index[questions["agency_id"] == "a"]
    assert [np.isin(split[p], a).sum() for p in ("store", "calibration", "test")] == [
        10,
        2,
        8,
    ]
    assert sorted(np.concatenate(list(split.values()))) == list(range(30))
    assert all((split[p] == split_questions(questions, seed=0)[p]).all() for p in split)
    assert not (split["test"] == split_questions(questions, seed=1)["test"]).all()


def test_passages_holding_a_test_question_or_answer_start_are_left_out():
    passages = pd.DataFrame(
        {"text": ["Kuidas taotleda passi? Vastus siin", "Muu tekst", "x " + "a" * 90]}
    )
    test = pd.DataFrame({"question": ["Kuidas taotleda passi?"], "answer": ["a" * 100]})
    assert without_test_content(passages, test).tolist() == [False, True, False]


def test_off_topic_list_is_read_without_running_the_file(tmp_path):
    source = tmp_path / "prototype.py"
    source.write_text(
        'raise SystemExit("must not run")\nOFF_TOPIC = ["Ilm homme?", "Retsept"]\n',
        encoding="utf-8",
    )
    assert off_topic_list(source) == ["Ilm homme?", "Retsept"]


def test_off_topic_files(tmp_path):
    (tmp_path / "chats.csv").write_text(
        'conversation\n"user: Tomatid? assistant: Mais. user: Aitäh"\n',
        encoding="utf-8",
    )
    (tmp_path / "lines.txt").write_text("Kino täna?\n\nPannkoogid\n", encoding="utf-8")
    messages = read_off_topic([tmp_path / "chats.csv", tmp_path / "lines.txt"])
    assert messages == ["Tomatid?\nAitäh", "Kino täna?", "Pannkoogid"]
