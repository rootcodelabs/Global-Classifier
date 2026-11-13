"""Second opinion core: triggers, prompt, grammar, reading the answer, applying it."""

import math

import pytest

from embedding_classifier import second_opinion as so
from embedding_classifier.gate import CLARIFY, OUT_OF_DISTRIBUTION, ROUTE, Decision
from embedding_classifier.output import OOD_AGENCY_ID, OOD_AGENCY_NAME


def chat_response(letter, probabilities, prompt_tokens=321):
    """A llama-server chat completions answer with log-probabilities."""
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": letter},
                "logprobs": {
                    "content": [
                        {
                            "token": letter,
                            "logprob": math.log(probabilities[letter]),
                            "top_logprobs": [
                                {"token": t, "logprob": math.log(p)}
                                for t, p in probabilities.items()
                            ],
                        }
                    ]
                },
            }
        ],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": 1},
    }


def items(*ids_and_confidences, ood=False):
    out = [
        {"agency_id": a, "agency_name": f"name {a}", "confidence": c}
        for a, c in ids_and_confidences
    ]
    if ood:
        out.insert(
            0,
            {
                "agency_id": OOD_AGENCY_ID,
                "agency_name": OOD_AGENCY_NAME,
                "confidence": 1 - out[0]["confidence"],
            },
        )
    return out


PREDICTIONS = items(("ppa", 0.5), ("ttja", 0.3), ("idee", 0.15), ("emta", 0.05))
CLARIFY_RECORD = {
    "decision": CLARIFY,
    "margin": 0.05,
    "top_similarity": 0.98,
    "candidates": ["ppa", "ttja", "idee"],
}
OOD_RECORD = {
    "decision": OUT_OF_DISTRIBUTION,
    "margin": 0.2,
    "top_similarity": 0.95,
    "candidates": [],
}
IDS = ["ppa", "ttja", "idee"]


def test_trigger_clarify_and_never_route():
    assert so.trigger(Decision(CLARIFY, 0.1, 0.99, [0, 1, 2]), 0.97, 0.03) == "clarify"
    assert so.trigger(Decision(ROUTE, 0.5, 0.99, [0]), 0.97, 0.03) is None


@pytest.mark.parametrize(
    "top_similarity,expected",
    [
        (0.75, "ood_band"),  # just below the cutoff
        (0.5, "ood_band"),  # exactly ood_band below: still in
        (0.4999, None),  # further below: plainly off-topic
    ],
)
def test_trigger_ood_band_edges(top_similarity, expected):
    decision = Decision(OUT_OF_DISTRIBUTION, 0.1, top_similarity, [])
    assert so.trigger(decision, ood_cutoff=0.75, ood_band=0.25) == expected


def test_candidates_follow_the_ranking_with_nearest_texts():
    names = ["PPA", "TTJA", "ID.ee", "EMTA"]
    texts = [["p1", "p2", "p3", "p4"], ["t1"], ["i1", "i2"], ["e1"]]

    options = so.candidates([2, 0, 3, 1], names, texts)

    assert [(o.position, o.name) for o in options] == [
        (2, "ID.ee"),
        (0, "PPA"),
        (3, "EMTA"),
    ]
    assert options[0].examples == ["i1", "i2"]
    assert options[1].examples == ["p1", "p2", "p3"]  # at most 3


def test_prompt_lists_letters_in_order_and_cuts_texts():
    message = "Kuidas   lapsele\npassi taotleda? " + "x" * 2000
    options = [
        so.Candidate(
            0, "Politsei- ja Piirivalveamet", ["Kuidas pass taotleda?", "y" * 300]
        ),
        so.Candidate(1, "ID.ee", ["Smart-ID ei tööta"]),
        so.Candidate(2, "Tarbijakaitse", []),
    ]

    prompt = so.build_prompt(message, options)
    lines = prompt.split("\n")

    assert prompt.startswith(
        so.INSTRUCTIONS + "\n\nMessage: Kuidas lapsele passi taotleda? x"
    )
    message_line = next(line for line in lines if line.startswith("Message: "))
    assert len(message_line) == len("Message: ") + so.MESSAGE_CHARS
    assert lines.index("A) Politsei- ja Piirivalveamet") < lines.index("B) ID.ee")
    assert lines.index("B) ID.ee") < lines.index("C) Tarbijakaitse")
    assert "   - Kuidas pass taotleda?" in lines
    assert "   - " + "y" * so.EXAMPLE_CHARS in lines
    assert lines[-3:] == ["N) None of these", "", "Answer:"]


def test_grammar_and_request_body():
    assert so.grammar() == 'root ::= "A" | "B" | "C" | "N"'
    assert so.grammar(2) == 'root ::= "A" | "B" | "N"'

    body = so.request_body("prompt")
    assert body["messages"] == [{"role": "user", "content": "prompt"}]
    assert body["max_tokens"] == 1
    assert body["temperature"] == 0
    assert body["grammar"] == so.grammar()
    assert body["logprobs"] is True


def test_read_answer_renormalises_over_the_letters():
    # The model's own distribution also gave weight to tokens that aren't letters
    response = chat_response("B", {"B": 0.6, "A": 0.2, "**": 0.15, "N": 0.05})

    answer = so.read_answer(response)

    assert answer.letter == "B"
    assert answer.pick() == 1
    assert answer.probability == pytest.approx(0.6 / 0.85)
    assert answer.prompt_tokens == 321


def test_read_answer_with_spaced_tokens_and_none():
    response = chat_response("N", {"N": 0.9, " A": 0.1})
    answer = so.read_answer(response)
    assert answer.pick() is None
    assert answer.probability == pytest.approx(0.9)


@pytest.mark.parametrize(
    "response",
    [
        chat_response("D", {"D": 1.0}),
        {"choices": [{"message": {"content": "A"}}]},  # no log-probabilities
    ],
)
def test_read_answer_rejects_anything_else(response):
    with pytest.raises(ValueError):
        so.read_answer(response)


def answer(letter, probability=0.9):
    return so.Answer(letter, probability)


def test_clarify_b_moves_first_and_reassigns_confidences():
    new_items, record, applied = so.apply_answer(
        PREDICTIONS, CLARIFY_RECORD, "clarify", IDS, answer("B"), 0.5
    )

    assert applied
    assert [(i["agency_id"], i["confidence"]) for i in new_items] == [
        ("ttja", 0.5),
        ("ppa", 0.3),
        ("idee", 0.15),
        ("emta", 0.05),
    ]
    assert record["decision"] == CLARIFY
    assert record["candidates"] == ["ttja", "ppa", "idee"]
    assert record["margin"] == CLARIFY_RECORD["margin"]


def test_clarify_c_moves_first():
    new_items, record, applied = so.apply_answer(
        PREDICTIONS, CLARIFY_RECORD, "clarify", IDS, answer("C"), 0.5
    )
    assert applied
    assert [i["agency_id"] for i in new_items] == ["idee", "ppa", "ttja", "emta"]
    assert record["candidates"] == ["idee", "ppa", "ttja"]


@pytest.mark.parametrize(
    "given", [answer("A"), answer("N"), answer("B", probability=0.49)]
)
def test_clarify_a_none_or_unsure_changes_nothing(given):
    new_items, record, applied = so.apply_answer(
        PREDICTIONS, CLARIFY_RECORD, "clarify", IDS, given, 0.5
    )
    assert not applied
    assert new_items is PREDICTIONS
    assert record is CLARIFY_RECORD


@pytest.mark.parametrize("letter,first", [("A", "ppa"), ("B", "ttja"), ("C", "idee")])
def test_borderline_off_topic_is_rescued_as_clarify(letter, first):
    off_topic = items(("ppa", 0.5), ("ttja", 0.3), ("idee", 0.15), ood=True)

    new_items, record, applied = so.apply_answer(
        off_topic, OOD_RECORD, "ood_band", IDS, answer(letter), 0.5
    )

    assert applied
    assert all(i["agency_name"] != OOD_AGENCY_NAME for i in new_items)
    assert new_items[0]["agency_id"] == first
    assert [i["confidence"] for i in new_items] == [0.5, 0.3, 0.15]
    assert record["decision"] == CLARIFY
    assert record["candidates"][0] == first
    assert len(record["candidates"]) == 3


@pytest.mark.parametrize("given", [answer("N"), answer("A", probability=0.2)])
def test_borderline_off_topic_none_or_unsure_changes_nothing(given):
    off_topic = items(("ppa", 0.5), ("ttja", 0.3), ("idee", 0.15), ood=True)
    new_items, record, applied = so.apply_answer(
        off_topic, OOD_RECORD, "ood_band", IDS, given, 0.5
    )
    assert not applied
    assert new_items is off_topic
    assert record is OOD_RECORD


def test_read_answer_keeps_every_letters_share():
    response = chat_response("B", {"B": 0.6, "A": 0.2, "**": 0.15, "N": 0.05})

    letters = so.read_answer(response).letters

    assert letters == pytest.approx(
        {"A": 0.2 / 0.85, "B": 0.6 / 0.85, "C": 0.0, "N": 0.05 / 0.85}
    )


NAMES = ["Politsei- ja Piirivalveamet", "ID.ee", "Tarbijakaitse"]
EXAMPLES = [["Kuidas pass taotleda?", "y" * 300, "p3", "p4"], ["Smart-ID ei tööta"], []]


def test_catalogue_numbers_every_agency_with_its_examples():
    opening = so.catalogue(NAMES, EXAMPLES)
    lines = opening.split("\n")

    assert opening.startswith(
        so.CATALOGUE_HEADER + "\n\n1. Politsei- ja Piirivalveamet"
    )
    assert lines.index("2. ID.ee") < lines.index("3. Tarbijakaitse")
    assert "   - Kuidas pass taotleda?" in lines
    assert "   - " + "y" * so.EXAMPLE_CHARS in lines
    assert "   - p4" not in lines  # at most CATALOGUE_EXAMPLES
    assert lines[-1] == "3. Tarbijakaitse"


def test_catalogue_drops_examples_to_fit_and_refuses_names_that_dont():
    full = so.catalogue(NAMES, EXAMPLES)
    names_only = so.catalogue(NAMES, [[], [], []])

    shorter = so.catalogue(NAMES, EXAMPLES, max_chars=len(full) - 1)

    assert "   - p3" not in shorter.split("\n")
    assert "   - Kuidas pass taotleda?" in shorter.split("\n")
    assert so.catalogue(NAMES, EXAMPLES, max_chars=len(names_only)) == names_only
    with pytest.raises(ValueError):
        so.catalogue(NAMES, EXAMPLES, max_chars=len(names_only) - 1)


def test_catalogue_prompt_keeps_the_opening_first_and_numbers_the_options():
    opening = so.catalogue(NAMES, EXAMPLES)
    message = "Kuidas   lapsele\npassi taotleda? " + "x" * 2000

    prompt = so.build_catalogue_prompt(opening, message, [2, 0, 1])
    other = so.build_catalogue_prompt(opening, "Smart-ID", [1, 0, 2])
    lines = prompt.split("\n")

    # Everything up to the message is the same for every message: the cached part
    shared = prompt[: prompt.index("Message: ")]
    assert other.startswith(shared)
    assert shared == opening + "\n\n" + so.CATALOGUE_INSTRUCTIONS + "\n\n"
    message_line = next(line for line in lines if line.startswith("Message: "))
    assert message_line.startswith("Message: Kuidas lapsele passi taotleda? x")
    assert len(message_line) == len("Message: ") + so.MESSAGE_CHARS
    assert lines[-4:] == ["Options:", "A) 3  B) 1  C) 2  N) none", "", "Answer:"]


def letters(a, b, c, n=0.0):
    return {"A": a, "B": b, "C": c, "N": n}


def test_combined_order_weighs_the_model_against_e5():
    confidences = [0.5, 0.3, 0.15]
    sure_of_b = letters(0.01, 0.98, 0.01)

    assert so.combined_order(confidences, sure_of_b, 0.0) == [0, 1, 2]
    assert so.combined_order(confidences, sure_of_b, 0.5) == [1, 0, 2]
    # A model torn between A and B leaves e5's order
    assert so.combined_order(confidences, letters(0.45, 0.55, 0.0), 0.5) == [0, 1, 2]
    # Equal scores keep e5's order
    assert so.combined_order([0.4, 0.4, 0.2], letters(0.3, 0.3, 0.4), 0.0) == [0, 1, 2]


def combined(
    given_letters, trigger="clarify", predictions=PREDICTIONS, record=CLARIFY_RECORD
):
    pick = max("ABCN", key=lambda x: given_letters[x])
    answer = so.Answer(pick, given_letters[pick], letters=given_letters)
    return so.apply_combined(predictions, record, trigger, IDS, answer, 0.5, 0.5)


def test_combined_clarify_reorders_the_top_and_keeps_the_rest():
    new_items, record, applied = combined(letters(0.01, 0.01, 0.98))

    assert applied
    # idee: log 0.15 + 0.5 log 0.98 beats ppa: log 0.5 + 0.5 log 0.01
    assert [(i["agency_id"], i["confidence"]) for i in new_items] == [
        ("idee", 0.5),
        ("ppa", 0.3),
        ("ttja", 0.15),
        ("emta", 0.05),
    ]
    assert record["decision"] == CLARIFY
    assert record["candidates"] == ["idee", "ppa", "ttja"]
    assert record["margin"] == CLARIFY_RECORD["margin"]


@pytest.mark.parametrize(
    "given",
    [letters(0.9, 0.05, 0.05), letters(0.45, 0.55, 0.0), letters(0.1, 0.1, 0.1, 0.7)],
)
def test_combined_clarify_that_keeps_e5s_order_changes_nothing(given):
    new_items, record, applied = combined(given)
    assert not applied
    assert new_items is PREDICTIONS
    assert record is CLARIFY_RECORD


def test_combined_needs_the_candidates_at_the_top_of_the_list():
    short = PREDICTIONS[:1]  # a request with top_k 1
    new_items, record, applied = combined(letters(0.01, 0.01, 0.98), predictions=short)
    assert not applied
    assert new_items is short


def test_combined_rescues_a_borderline_off_topic_message():
    off_topic = items(("ppa", 0.5), ("ttja", 0.3), ("idee", 0.15), ood=True)

    new_items, record, applied = combined(
        letters(0.01, 0.98, 0.01), "ood_band", off_topic, OOD_RECORD
    )

    assert applied
    assert all(i["agency_name"] != OOD_AGENCY_NAME for i in new_items)
    assert [i["agency_id"] for i in new_items] == ["ttja", "ppa", "idee"]
    assert [i["confidence"] for i in new_items] == [0.5, 0.3, 0.15]
    assert record["decision"] == CLARIFY
    assert record["candidates"] == ["ttja", "ppa", "idee"]


@pytest.mark.parametrize(
    "given", [letters(0.05, 0.05, 0.05, 0.85), letters(0.4, 0.3, 0.3)]
)
def test_combined_borderline_off_topic_none_or_unsure_changes_nothing(given):
    off_topic = items(("ppa", 0.5), ("ttja", 0.3), ("idee", 0.15), ood=True)
    new_items, record, applied = combined(given, "ood_band", off_topic, OOD_RECORD)
    assert not applied
    assert new_items is off_topic
    assert record is OOD_RECORD


def test_record_field():
    assert so.record_field(answer("B", 0.87), IDS, True, 1840.4, "ok") == {
        "pick": "ttja",
        "probability": 0.87,
        "applied": True,
        "ms": 1840,
        "outcome": "ok",
    }
    assert so.record_field(answer("N"), IDS, False, 10, "ok")["pick"] == "none"
    assert so.record_field(None, IDS, False, 3001, "timeout") == {
        "pick": None,
        "probability": None,
        "applied": False,
        "ms": 3001,
        "outcome": "timeout",
    }
