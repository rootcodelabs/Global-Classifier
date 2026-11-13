"""
Evaluate the classifier on the agency knowledge base, through Qdrant or the
in-memory store, with the benchmark's protocol: per agency, 50% of the real
questions are stored, 10% calibrate the gate and 40% are test questions;
results are averaged over seeds 0 to 2.

Stores compared:
  A  questions + answers + titles + passages   must reproduce the reference numbers
  B  questions + titles + passages             no answers
  D  questions only                            what production builds until CKB content is kept
Off-topic detection (C) is measured on every store; A is "the full store".

The knowledge base and off-topic sets stay outside the repo and are passed by
path. --off-topic takes a CSV of conversations (user turns are kept), a text
file with one message per line, or a Python file whose OFF_TOPIC list is read
without importing it.

Example, from src/embedding-classifier:
    python -m tools.evaluate_kb --kb <knowledge base folder> \\
        --off-topic <off-topic messages> \\
        --off-topic ../../experiments/ood_detection/data/ood_test.csv \\
        --store qdrant --out <results folder>
"""

import argparse
import ast
import json
import logging
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from embedding_classifier import evaluation
from embedding_classifier.calibration import calibrate
from embedding_classifier.content import (
    read_kb_documents,
    read_kb_questions,
    user_turns,
)
from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import Encoder, get_model
from embedding_classifier.gate import (
    OUT_OF_DISTRIBUTION,
    ROUTE,
    decide,
    margins,
    ranking,
)
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.scoring import Scores, ScoringParams, score
from embedding_classifier.store import ANSWER, PASSAGE, QUESTION, TITLE, Row
from embedding_classifier.vector_store import MemoryIndexStore, QdrantIndexStore

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

STORES = {
    "A": [QUESTION, ANSWER, TITLE, PASSAGE],
    "B": [QUESTION, TITLE, PASSAGE],
    "D": [QUESTION],
}
STORE_LABELS = {
    "A": "questions + answers + titles + passages",
    "B": "questions + titles + passages",
    "D": "questions only",
}
# A passage containing a test question, or the start of its answer, is not stored
ANSWER_PREFIX_CHARS = 80
ANSWER_MIN_CHARS = 30
PARITY_TOLERANCE = 1e-4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kb", required=True, type=Path, help="Knowledge base folder")
    parser.add_argument("--off-topic", action="append", default=[], type=Path)
    parser.add_argument(
        "--model", default="multilingual-e5-large-instruct", help="Model key"
    )
    parser.add_argument("--store", choices=["qdrant", "memory"], default="qdrant")
    parser.add_argument(
        "--qdrant-url", default=os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")
    )
    parser.add_argument(
        "--qdrant-grpc", action="store_true", help="Talk to Qdrant over gRPC"
    )
    parser.add_argument(
        "--parity",
        action="store_true",
        help="Also score with the memory store and compare",
    )
    parser.add_argument("--stores", default="ABD", help="Which stores to evaluate")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--threads", type=int, default=None)
    parser.add_argument(
        "--cache", type=Path, help="Embedding cache folder (default: <out>/cache)"
    )
    parser.add_argument(
        "--second-opinion-url",
        help="llama-server URL: also report stores B and D with the second opinion applied",
    )
    parser.add_argument("--ood-band", type=float, default=0.03)
    parser.add_argument("--min-probability", type=float, default=0.5)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    questions = read_kb_questions(args.kb)
    agency_ids = sorted(questions["agency_id"].unique())
    position = {agency_id: i for i, agency_id in enumerate(agency_ids)}
    names = dict(zip(questions["agency_id"], questions["agency_name"]))
    passages, titles = read_kb_documents(args.kb, agency_ids)
    off_topic = read_off_topic(args.off_topic)
    logger.info(
        f"{len(questions)} questions, {len(titles)} titles, {len(passages)} passages, "
        f"{len(agency_ids)} agencies, {len(off_topic)} off-topic messages"
    )

    model = get_model(args.model)
    encoder = Encoder(model, threads=args.threads)
    cache = EmbeddingCache(args.cache or args.out / "cache")
    answers = questions["answer"].fillna("").astype(str)
    vectors = {
        QUESTION: cache.encode(encoder, questions["question"].tolist(), "short"),
        ANSWER: cache.encode(encoder, answers.tolist(), "long"),
        TITLE: cache.encode(encoder, titles["text"].tolist(), "short"),
        PASSAGE: cache.encode(encoder, passages["text"].tolist(), "long"),
    }
    off_topic_vectors = cache.encode(encoder, off_topic, "short")

    store = make_store(args)
    oracle = MemoryIndexStore() if args.parity and args.store == "qdrant" else None
    scoring = ScoringParams()
    runs: dict[str, list[dict]] = {name: [] for name in args.stores}
    for seed in range(args.seeds):
        split = split_questions(questions, seed)
        test, calib = questions.loc[split["test"]], questions.loc[split["calibration"]]
        stored = split["store"]
        title_kept = (
            ~titles["text"]
            .str.lower()
            .isin(set(test["question"].str.lower()))
            .to_numpy()
        )
        passage_kept = without_test_content(passages, test)
        parts = {
            QUESTION: (
                questions.loc[stored, "agency_id"],
                questions.loc[stored, "question"],
                vectors[QUESTION][stored],
            ),
            ANSWER: (
                questions.loc[stored, "agency_id"],
                answers.loc[stored],
                vectors[ANSWER][stored],
            ),
            TITLE: (
                titles.loc[title_kept, "agency_id"],
                titles.loc[title_kept, "text"],
                vectors[TITLE][title_kept],
            ),
            PASSAGE: (
                passages.loc[passage_kept, "agency_id"],
                passages.loc[passage_kept, "text"],
                vectors[PASSAGE][passage_kept],
            ),
        }
        messages = {
            "test": (vectors[QUESTION][split["test"]], test["question"].tolist()),
            "calibration": (
                vectors[QUESTION][split["calibration"]],
                calib["question"].tolist(),
            ),
            "off_topic": (off_topic_vectors, off_topic),
        }
        truth = {
            "test": np.array([position[a] for a in test["agency_id"]]),
            "calibration": np.array([position[a] for a in calib["agency_id"]]),
        }
        for name in args.stores:
            rows, dense = assemble(parts, STORES[name], names)
            second_opinion = (
                {
                    "url": args.second_opinion_url,
                    "ood_band": args.ood_band,
                    "min_probability": args.min_probability,
                    "names": [names[a] for a in agency_ids],
                }
                if args.second_opinion_url and name in "BD"
                else None
            )
            result = evaluate_store(
                store,
                oracle,
                f"gc_eval_kb_{name}_s{seed}",
                rows,
                dense,
                messages,
                truth,
                agency_ids,
                scoring,
                second_opinion,
            )
            runs[name].append(result)
            logger.info(
                f"seed {seed} store {name}: {len(rows)} rows, top-1 {result['top1']:.3f}, "
                f"top-3 {result['top3']:.3f}, routed at 90% {result['coverage_at_90_test_cutoff']:.3f}"
            )

    report = summarise(
        runs,
        args,
        model,
        questions,
        agency_ids,
        names,
        len(off_topic),
        time.perf_counter() - started,
    )
    write_report(report, args.out)
    logger.info(f"Results written to {args.out}")


def read_off_topic(paths: list[Path]) -> list[str]:
    messages = []
    for path in paths:
        if path.suffix == ".csv":
            frame = pd.read_csv(path)
            column = (
                "conversation" if "conversation" in frame.columns else frame.columns[0]
            )
            messages += [user_turns(str(text)) for text in frame[column]]
        elif path.suffix == ".py":
            messages += off_topic_list(path)
        else:
            messages += path.read_text(encoding="utf-8").splitlines()
    return [m for m in messages if m.strip()]


def off_topic_list(path: Path) -> list[str]:
    """The OFF_TOPIC list literal of a Python file, read without running it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "OFF_TOPIC"
            for target in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise ValueError(f"No OFF_TOPIC list in {path}")


def split_questions(questions: pd.DataFrame, seed: int) -> dict[str, np.ndarray]:
    """Per agency (in sorted order): 50% stored, 10% calibration, the rest test."""
    rng = np.random.default_rng(seed)
    parts = {"store": [], "calibration": [], "test": []}
    for _, group in questions.groupby("agency_id"):
        rows = rng.permutation(group.index.to_numpy())
        n_store = max(1, round(len(rows) * 0.5))
        n_calibration = round(len(rows) * 0.1)
        parts["store"].extend(rows[:n_store])
        parts["calibration"].extend(rows[n_store : n_store + n_calibration])
        parts["test"].extend(rows[n_store + n_calibration :])
    return {name: np.array(rows, dtype=int) for name, rows in parts.items()}


def without_test_content(passages: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Mask of passages that contain neither a test question nor the start of its answer."""
    needles = [q.lower() for q in test["question"]]
    needles += [
        answer.lower()[:ANSWER_PREFIX_CHARS]
        for answer in test["answer"].fillna("").astype(str)
        if len(answer) >= ANSWER_MIN_CHARS
    ]
    return np.array(
        [not any(n in text for n in needles) for text in passages["text"].str.lower()]
    )


def assemble(
    parts: dict, kinds: list[str], names: dict
) -> tuple[list[Row], np.ndarray]:
    rows, dense = [], []
    for kind in kinds:
        agency_ids, texts, vectors = parts[kind]
        rows += [
            Row(str(a), names[a], kind, str(t), "knowledge_base")
            for a, t in zip(agency_ids, texts)
        ]
        dense.append(vectors)
    return rows, np.vstack(dense)


def evaluate_store(
    store,
    oracle,
    collection,
    rows,
    dense,
    messages,
    truth,
    agency_ids,
    scoring,
    second_opinion=None,
) -> dict:
    keywords = KeywordVectorizer.fit([row.text for row in rows])
    stored_keywords = keywords.transform([row.text for row in rows])
    agency_keys = [str(a) for a in agency_ids]
    scores, parity = {}, {}
    for current in [store] + ([oracle] if oracle else []):
        current.delete_collection(collection)
        current.create_collection(collection, rows, dense, stored_keywords)
        try:
            for name, (vectors, texts) in messages.items():
                result = score(
                    current,
                    collection,
                    agency_keys,
                    vectors,
                    keywords.transform(texts),
                    scoring,
                    with_texts=second_opinion is not None and name == "test",
                )
                if current is store:
                    scores[name] = result
                else:
                    parity[name] = compare(scores[name], result)
        finally:
            current.delete_collection(collection)

    test, test_truth = scores["test"], truth["test"]
    order = ranking(test.fused)
    correct = order[:, 0] == test_truth
    test_margin = margins(test.fused)
    gate, warnings = calibrate(scores["calibration"], truth["calibration"])
    gate_decisions = decide(test, gate)
    decisions = [d.decision for d in gate_decisions]
    reviewed = (
        with_second_opinion(
            test, gate_decisions, gate, messages["test"][1], test_truth, second_opinion
        )
        if second_opinion is not None
        else None
    )
    return {
        **evaluation.topk_accuracy(test.fused, test_truth),
        "second_opinion": reviewed,
        "rows": len(rows),
        "coverage_at_90_test_cutoff": evaluation.coverage_at(test_margin, correct, 0.9),
        "routed_calibrated": evaluation.routed(test_margin, correct, gate.route_margin),
        "off_topic": evaluation.off_topic(
            scores["off_topic"].top_similarity, test.top_similarity, gate.ood_cutoff
        ),
        "decision_mix": {
            d: float(np.mean([x == d for x in decisions]))
            for d in (ROUTE, "clarify", OUT_OF_DISTRIBUTION)
        },
        "gate": {
            "ood_cutoff": gate.ood_cutoff,
            "route_margin": gate.route_margin,
            "temperature": gate.temperature,
        },
        "warnings": warnings,
        "predicted": order[:, 0].tolist(),
        "truth": test_truth.tolist(),
        "parity": parity,
    }


def with_second_opinion(test, decisions, gate, texts, truth, settings) -> dict:
    """Top-1 on the test questions after the second opinion, asked as the service asks it."""
    from embedding_classifier import second_opinion as so
    from tools.second_opinion_benchmark import ask

    order = ranking(test.fused)
    top1 = order[:, 0].copy()
    asked = applied = failed = 0
    for i, d in enumerate(decisions):
        reason = so.trigger(d, gate.ood_cutoff, settings["ood_band"])
        if reason is None:
            continue
        options = so.candidates(
            order[i], settings["names"], test.texts[i], gate.clarify_candidates
        )
        asked += 1
        try:
            response, _ = ask(
                settings["url"], so.build_prompt(texts[i], options), len(options), 300
            )
            answer = so.read_answer(response, len(options))
        except Exception as error:
            failed += 1
            logger.warning(f"Second opinion failed: {error}")
            continue
        pick = answer.pick()
        if (
            pick is None
            or answer.probability < settings["min_probability"]
            or (reason == so.CLARIFY_TRIGGER and pick == 0)
        ):
            continue
        top1[i] = options[pick].position
        applied += 1
    return {
        "asked": asked,
        "applied": applied,
        "failed": failed,
        "top1": float(np.mean(top1 == truth)),
        "fixed": int(np.sum((order[:, 0] != truth) & (top1 == truth))),
        "broken": int(np.sum((order[:, 0] == truth) & (top1 != truth))),
    }


def compare(served: Scores, oracle: Scores) -> dict:
    """How far the store under test is from the in-memory oracle."""
    diff = max(
        float(np.abs(served.dense - oracle.dense).max(initial=0)),
        float(np.abs(served.keywords - oracle.keywords).max(initial=0)),
        float(np.abs(served.fused - oracle.fused).max(initial=0)),
    )
    a, b = ranking(served.fused)[:, :5], ranking(oracle.fused)[:, :5]
    mismatched = np.nonzero((a != b).any(axis=1))[0]
    # A different order is only acceptable between agencies whose scores tie
    unexplained = [
        int(i)
        for i in mismatched
        if np.abs(oracle.fused[i, a[i]] - oracle.fused[i, b[i]]).max()
        > PARITY_TOLERANCE
    ]
    return {
        "messages": int(len(a)),
        "max_score_diff": diff,
        "top5_order_differences": int(len(mismatched)),
        "unexplained_order_differences": len(unexplained),
        "passed": diff <= PARITY_TOLERANCE and not unexplained,
    }


def make_store(args):
    if args.store == "memory":
        return MemoryIndexStore()
    api_key = os.environ.get("QDRANT_API_KEY")
    return QdrantIndexStore.connect(
        args.qdrant_url, api_key, timeout=120, prefer_grpc=args.qdrant_grpc
    )


def summarise(
    runs, args, model, questions, agency_ids, names, n_off_topic, seconds
) -> dict:
    def mean_std(values):
        values = [v for v in values if v is not None and not np.isnan(v)]
        return (
            {"mean": float(np.mean(values)), "std": float(np.std(values))}
            if values
            else None
        )

    stores = {}
    for name, results in runs.items():
        predicted = np.concatenate([r["predicted"] for r in results])
        truth = np.concatenate([r["truth"] for r in results])
        agency_metrics = evaluation.per_agency(predicted, truth, len(agency_ids))
        parity = [p for r in results for p in r["parity"].values()]
        stores[name] = {
            "label": STORE_LABELS[name],
            "rows": mean_std([r["rows"] for r in results]),
            **{
                k: mean_std([r[k] for r in results])
                for k in ("top1", "top3", "top5", "coverage_at_90_test_cutoff")
            },
            "routed_calibrated_share": mean_std(
                [r["routed_calibrated"]["share"] for r in results]
            ),
            "routed_calibrated_accuracy": mean_std(
                [r["routed_calibrated"]["accuracy"] for r in results]
            ),
            "off_topic_caught": mean_std([r["off_topic"]["caught"] for r in results]),
            "real_wrongly_flagged": mean_std(
                [r["off_topic"]["wrongly_flagged"] for r in results]
            ),
            "decision_mix": {
                d: mean_std([r["decision_mix"][d] for r in results])
                for d in results[0]["decision_mix"]
            },
            "gate": {
                k: mean_std([r["gate"][k] for r in results]) for k in results[0]["gate"]
            },
            "top1_with_second_opinion": mean_std(
                [r["second_opinion"]["top1"] for r in results if r["second_opinion"]]
            ),
            "second_opinion": {
                k: sum(r["second_opinion"][k] for r in results)
                for k in ("asked", "applied", "failed", "fixed", "broken")
            }
            if results[0]["second_opinion"]
            else None,
            "warnings": sorted({w for r in results for w in r["warnings"]}),
            "per_agency": [
                {
                    "agency_id": a,
                    "agency_name": names[a],
                    "questions": int((questions["agency_id"] == a).sum()),
                    **{m: agency_metrics[m][i] for m in ("recall", "precision", "f1")},
                }
                for i, a in enumerate(agency_ids)
            ],
            "parity": {
                "checked": bool(parity),
                "passed": all(p["passed"] for p in parity) if parity else None,
                "messages": sum(p["messages"] for p in parity),
                "max_score_diff": max(
                    (p["max_score_diff"] for p in parity), default=None
                ),
                "top5_order_differences": sum(
                    p["top5_order_differences"] for p in parity
                ),
                "unexplained_order_differences": sum(
                    p["unexplained_order_differences"] for p in parity
                ),
            },
        }
    return {
        "setup": {
            "model": model.hf_id,
            "revision": model.revision,
            "store": args.store + (" (gRPC)" if args.qdrant_grpc else ""),
            "agencies": len(agency_ids),
            "questions": len(questions),
            "off_topic_messages": n_off_topic,
            "seeds": args.seeds,
            "split": "per agency 50% stored, 10% calibration, 40% test",
            "minutes": round(seconds / 60, 1),
        },
        "stores": stores,
    }


def write_report(report: dict, out: Path) -> None:
    with open(out / "results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    def pct(stat, std=False):
        if stat is None:
            return "n/a"
        text = f"{stat['mean'] * 100:.1f}%"
        return text + (f" ± {stat['std'] * 100:.1f}" if std else "")

    s = report["setup"]
    lines = [
        "# Knowledge base evaluation",
        "",
        f"Model `{s['model']}` at `{s['revision'][:12]}`, store {s['store']}, {s['agencies']} agencies, "
        f"{s['questions']} real questions ({s['split']}), {s['off_topic_messages']} off-topic messages, "
        f"averaged over {s['seeds']} seeds. Took {s['minutes']} minutes.",
        "",
        "| Store | Rows | Top-1 | Top-3 | Top-5 | Routed at 90% (test cutoff) | Routed (calibrated cutoff) | "
        "Accuracy of routed | Off-topic caught | Real wrongly flagged | Parity |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, r in report["stores"].items():
        parity = r["parity"]
        parity_text = (
            "not checked"
            if not parity["checked"]
            else f"{'passed' if parity['passed'] else 'FAILED'} (max diff {parity['max_score_diff']:.1e})"
        )
        lines.append(
            f"| {name}: {r['label']} | {r['rows']['mean']:.0f} | {pct(r['top1'], True)} | {pct(r['top3'])} "
            f"| {pct(r['top5'])} | {pct(r['coverage_at_90_test_cutoff'], True)} "
            f"| {pct(r['routed_calibrated_share'], True)} | {pct(r['routed_calibrated_accuracy'])} "
            f"| {pct(r['off_topic_caught'])} | {pct(r['real_wrongly_flagged'])} | {parity_text} |"
        )
    reviewed = {n: r for n, r in report["stores"].items() if r["second_opinion"]}
    if reviewed:
        lines += ["", "With the second opinion applied (all seeds):", ""]
        for name, r in reviewed.items():
            s = r["second_opinion"]
            lines.append(
                f"- {name}: top-1 {pct(r['top1'])} -> {pct(r['top1_with_second_opinion'])}; "
                f"asked {s['asked']}, applied {s['applied']}, fixed {s['fixed']}, "
                f"broken {s['broken']}, failed calls {s['failed']}"
            )
    lines += ["", "Gate decisions on test questions (calibrated thresholds):", ""]
    for name, r in report["stores"].items():
        mix = ", ".join(f"{d} {pct(v)}" for d, v in r["decision_mix"].items())
        lines.append(f"- {name}: {mix}")
    for name, r in report["stores"].items():
        weak = [a for a in r["per_agency"] if a["recall"] < 0.2]
        if weak:
            lines += ["", f"Agencies under 20% recall in store {name}:", ""]
            lines += [
                f"- {a['agency_name']}: {a['recall'] * 100:.1f}% from {a['questions']} questions"
                for a in weak
            ]
    with open(out / "RESULTS.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
