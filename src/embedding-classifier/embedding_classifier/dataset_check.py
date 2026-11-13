"""
Dataset check: the questions the classifier gets wrong and the likely cause,
for people who know the agencies to review. Every question is scored against
the rest of the dataset (k-fold cross-validation with the classifier's own
scoring), and each one it gets wrong is put in one of four groups:

- no_clue: nothing in the question points to an agency ("Kui suur on toetuse
  määr?"); its most similar questions belong to many agencies, or it is very
  short. Rewrite it to name its topic, or remove it.
- shared_topic: the labelled agency is the classifier's 2nd or 3rd choice; two
  agencies cover the topic. Decide which one owns it, or add questions that
  tell them apart.
- check_label: the labelled agency isn't even among the top few; the label may
  be wrong.
- other: none of the above, most likely the classifier's own mistake.

The groups are candidates found by simple rules, not verdicts.
"""

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from embedding_classifier.gate import ranking
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.scoring import ScoringParams, score
from embedding_classifier.store import QUESTION, Row
from embedding_classifier.vector_store import MemoryIndexStore

NO_CLUE = "no_clue"
SHARED_TOPIC = "shared_topic"
CHECK_LABEL = "check_label"
OTHER = "other"
CAUSES = (NO_CLUE, SHARED_TOPIC, CHECK_LABEL, OTHER)

CSV_FILE = "dataset_check.csv"
REPORT_FILE = "dataset_check.md"
EXAMPLES_PER_PAIR = 3
PAIRS_SHOWN = 15


@dataclass(frozen=True)
class CheckParams:
    """
    folds: Cross-validation folds
    neighbours: Most similar stored questions looked at for no_clue
    no_clue_min_agencies: Those neighbours spread over at least this many agencies is no_clue
    no_clue_max_words: A question of at most this many words is no_clue
    shared_max_rank: The labelled agency ranked below this (0 is first) is shared_topic
    check_label_min_rank: The labelled agency ranked at or past this is check_label
    min_examples: Agencies with fewer questions are marked as needing more
    seed: Fixes the folds
    """

    folds: int = 5
    neighbours: int = 10
    no_clue_min_agencies: int = 5
    no_clue_max_words: int = 4
    shared_max_rank: int = 3
    check_label_min_rank: int = 5
    min_examples: int = 100
    seed: int = 0


@dataclass
class CheckResult:
    """questions: one row per question; agencies: one row per agency."""

    questions: pd.DataFrame
    agencies: pd.DataFrame
    pairs: list[dict]
    params: CheckParams


def fold_ids(truth: np.ndarray, folds: int, seed: int) -> np.ndarray:
    """A fold per question, dealt round-robin within each agency after shuffling."""
    rng = np.random.default_rng(seed)
    ids = np.zeros(len(truth), dtype=int)
    for agency in np.unique(truth):
        members = rng.permutation(np.nonzero(truth == agency)[0])
        ids[members] = np.arange(len(members)) % folds
    return ids


def cause(
    label_rank: int, neighbour_agencies: int, words: int, params: CheckParams
) -> str:
    """The likely cause of a mistake (label_rank > 0), see the module docstring."""
    if (
        neighbour_agencies >= params.no_clue_min_agencies
        or words <= params.no_clue_max_words
    ):
        return NO_CLUE
    if label_rank < params.shared_max_rank:
        return SHARED_TOPIC
    if label_rank >= params.check_label_min_rank:
        return CHECK_LABEL
    return OTHER


def check(
    questions: pd.DataFrame,
    vectors: np.ndarray,
    params: CheckParams = CheckParams(),
    scoring: ScoringParams = ScoringParams(),
) -> CheckResult:
    """
    Cross-validate a cleaned dataset and sort its mistakes by likely cause.

    Args:
        questions: Cleaned questions, columns agency_id, agency_name, text
        vectors: Their embeddings, in row order
    """
    questions = questions.reset_index(drop=True)
    keys = sorted(questions["agency_id"].astype(str).unique())
    position = {key: i for i, key in enumerate(keys)}
    names = dict(zip(questions["agency_id"].astype(str), questions["agency_name"]))
    truth = np.array([position[str(a)] for a in questions["agency_id"]])
    texts = questions["text"].astype(str).tolist()
    rows = [
        Row(keys[t], names[keys[t]], QUESTION, text) for t, text in zip(truth, texts)
    ]

    folds = fold_ids(truth, params.folds, params.seed)
    predicted = np.zeros(len(texts), dtype=int)
    label_rank = np.zeros(len(texts), dtype=int)
    neighbour_agencies = np.zeros(len(texts), dtype=int)
    store = MemoryIndexStore()
    for fold in range(params.folds):
        held = np.nonzero(folds == fold)[0]
        stored = np.nonzero(folds != fold)[0]
        if len(held) == 0:
            continue
        keywords = KeywordVectorizer.fit([texts[i] for i in stored])
        store.delete_collection("check")
        store.create_collection(
            "check",
            [rows[i] for i in stored],
            vectors[stored],
            keywords.transform([texts[i] for i in stored]),
        )
        scores = score(
            store,
            "check",
            keys,
            vectors[held],
            keywords.transform([texts[i] for i in held]),
            scoring,
        )
        order = ranking(scores.fused)
        predicted[held] = order[:, 0]
        label_rank[held] = np.argmax(order == truth[held, None], axis=1)
        n = min(params.neighbours, len(stored))
        nearest = np.argsort(-(vectors[held] @ vectors[stored].T), axis=1)[:, :n]
        neighbour_agencies[held] = [len(set(truth[stored][row])) for row in nearest]
    store.delete_collection("check")

    words = np.array([len(text.split()) for text in texts])
    causes = [
        "" if rank == 0 else cause(rank, agencies, n_words, params)
        for rank, agencies, n_words in zip(label_rank, neighbour_agencies, words)
    ]
    frame = pd.DataFrame(
        {
            "agency_id": questions["agency_id"],
            "agency_name": questions["agency_name"],
            "text": texts,
            "predicted_agency_id": [keys[p] for p in predicted],
            "predicted_agency_name": [names[keys[p]] for p in predicted],
            "label_rank": label_rank + 1,
            "neighbour_agencies": neighbour_agencies,
            "words": words,
            "cause": causes,
        }
    )
    return CheckResult(
        frame,
        _per_agency(frame, keys, names, truth, params),
        _pairs(frame),
        params,
    )


def _per_agency(frame, keys, names, truth, params) -> pd.DataFrame:
    rows = []
    for i, key in enumerate(keys):
        mine = frame[truth == i]
        counts = Counter(mine["cause"])
        rows.append(
            {
                "agency_id": key,
                "agency_name": names[key],
                "questions": len(mine),
                "top1": float(np.mean(mine["cause"] == "")),
                **{c: counts.get(c, 0) for c in CAUSES},
                "needs_more_examples": len(mine) < params.min_examples,
            }
        )
    return pd.DataFrame(rows).sort_values("top1").reset_index(drop=True)


def _pairs(frame: pd.DataFrame) -> list[dict]:
    """Agency pairs mixed up on shared topics, both directions together, most first."""
    shared = frame[frame["cause"] == SHARED_TOPIC]
    groups: dict[tuple[str, str], list] = {}
    for row in shared.itertuples():
        pair = tuple(sorted((row.agency_name, row.predicted_agency_name)))
        groups.setdefault(pair, []).append(row)
    pairs = [
        {
            "agencies": pair,
            "mistakes": len(items),
            "examples": [
                (item.text, item.agency_name, item.predicted_agency_name)
                for item in items[:EXAMPLES_PER_PAIR]
            ],
        }
        for pair, items in groups.items()
    ]
    return sorted(pairs, key=lambda p: (-p["mistakes"], p["agencies"]))


def write_report(result: CheckResult, folder: Path, title: str = "") -> None:
    """Write dataset_check.csv (every question the classifier got wrong) and dataset_check.md."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    wrong = result.questions[result.questions["cause"] != ""]
    wrong.sort_values(["cause", "agency_name"]).to_csv(
        folder / CSV_FILE, index=False, quoting=csv.QUOTE_NONNUMERIC, encoding="utf-8"
    )
    (folder / REPORT_FILE).write_text(_markdown(result, title), encoding="utf-8")


def _markdown(result: CheckResult, title: str) -> str:
    q, p = result.questions, result.params
    total = len(q)
    counts = Counter(q["cause"])
    wrong = total - counts.get("", 0)
    lines = [
        f"# Dataset check{': ' + title if title else ''}",
        "",
        f"{total} questions, {len(result.agencies)} agencies. Each question was scored "
        f"against the others ({p.folds}-fold cross-validation, the classifier's own "
        f"scoring). The classifier picked the labelled agency first for "
        f"{counts.get('', 0)} ({counts.get('', 0) / total:.1%}); the {wrong} others "
        "are sorted below by likely cause. The causes come from simple rules: "
        "they are candidates to review, not verdicts.",
        "",
        "| Likely cause | Questions | Share of all | What to do |",
        "| --- | --- | --- | --- |",
    ]
    advice = {
        NO_CLUE: "Rewrite the question to name its topic, or remove it",
        SHARED_TOPIC: "Decide which agency owns the topic, or add questions that tell them apart",
        CHECK_LABEL: "Check the label; the question may belong to the agency the classifier picked",
        OTHER: "Probably the classifier's mistake; more examples for the agency help",
    }
    meaning = {
        NO_CLUE: "No clue to the agency",
        SHARED_TOPIC: "Topic shared with another agency",
        CHECK_LABEL: "Label may be wrong",
        OTHER: "Other",
    }
    for c in CAUSES:
        lines.append(
            f"| {meaning[c]} (`{c}`) | {counts.get(c, 0)} | {counts.get(c, 0) / total:.1%} | {advice[c]} |"
        )
    lines += [
        "",
        f"`{NO_CLUE}`: its {p.neighbours} most similar questions belong to at least "
        f"{p.no_clue_min_agencies} agencies, or it has at most {p.no_clue_max_words} words. "
        f"`{SHARED_TOPIC}`: the labelled agency was the classifier's choice 2 to "
        f"{p.shared_max_rank}. `{CHECK_LABEL}`: the labelled agency ranked "
        f"{p.check_label_min_rank + 1} or lower. Every question is in {CSV_FILE}.",
        "",
        "## Agencies",
        "",
        f"Worst first. Agencies with fewer than {p.min_examples} questions are marked: "
        "more examples is the surest way to raise their accuracy.",
        "",
        "| Agency | Questions | Top-1 | No clue | Shared topic | Check label | Other | Needs more examples |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for a in result.agencies.itertuples():
        lines.append(
            f"| {a.agency_name} | {a.questions} | {a.top1:.0%} | {a.no_clue} | "
            f"{a.shared_topic} | {a.check_label} | {a.other} | "
            f"{'yes' if a.needs_more_examples else ''} |"
        )
    lines += ["", "## Topics two agencies share", ""]
    if not result.pairs:
        lines.append("None found.")
    for pair in result.pairs[:PAIRS_SHOWN]:
        lines.append(
            f"**{pair['agencies'][0]} / {pair['agencies'][1]}**: {pair['mistakes']} mistakes"
        )
        lines.append("")
        for text, labelled, picked in pair["examples"]:
            lines.append(f"- {_one_line(text)} (labelled {labelled}, picked {picked})")
        lines.append("")
    for c, heading in (
        (CHECK_LABEL, "Labels to check"),
        (NO_CLUE, "Questions with no clue to the agency"),
    ):
        rows = q[q["cause"] == c].sort_values(["agency_name", "text"])
        lines += ["", f"## {heading}", "", f"{len(rows)} questions.", ""]
        if c == CHECK_LABEL:
            lines += [
                "| Question | Labelled | Classifier picked |",
                "| --- | --- | --- |",
            ]
            lines += [
                f"| {_one_line(r.text)} | {r.agency_name} | {r.predicted_agency_name} |"
                for r in rows.itertuples()
            ]
        else:
            lines += ["| Question | Labelled |", "| --- | --- |"]
            lines += [
                f"| {_one_line(r.text)} | {r.agency_name} |" for r in rows.itertuples()
            ]
    return "\n".join(lines) + "\n"


def _one_line(text: str, limit: int = 200) -> str:
    """Whitespace collapsed, pipes escaped for a table, cut to limit."""
    flat = " ".join(str(text).split()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"
