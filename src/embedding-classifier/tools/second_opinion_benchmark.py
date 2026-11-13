"""
Second-opinion benchmark: decides whether to
turn the second opinion on, and with which values. It builds the prompts with
embedding_classifier.second_opinion, so it measures exactly what ships, and
sends them straight to a llama-server; the classifier service isn't needed.

Inputs, per seed (the evaluation CLI's split: per agency 50% stored, 10%
calibration, 40% test): the knowledge base with a questions-only store (as
production builds have) and thresholds calibrated on the calibration split; the off-topic sets;
and --extra CSVs (text, agency_id, language; an empty agency_id is
off-topic), such as English and Russian questions. Only the messages that
trigger the second opinion are sent: clarify, and out_of_distribution within
--ood-band below the cutoff.

One model per run, so each can run alone on a small machine. Prompts are
written once to messages.jsonl and every model answers the same ones;
answers go to answers_{model}.csv, and a run picks up where it stopped. The
summary (summary.json, SUMMARY.md) covers every answers file in --out.

Example, from src/embedding-classifier, with a llama-server on port 8012:
    python -m tools.second_opinion_benchmark --kb <knowledge base folder> \\
        --off-topic <off-topic messages> \\
        --off-topic ../../experiments/ood_detection/data/ood_test.csv \\
        --extra multilingual.csv --model gemma-4-e4b --url http://127.0.0.1:8012 --out <folder>
"""

import argparse
import csv
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests

from embedding_classifier import second_opinion as so
from embedding_classifier.calibration import calibrate
from embedding_classifier.content import read_kb_questions
from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import Encoder, get_model
from embedding_classifier.gate import OUT_OF_DISTRIBUTION, decide, ranking
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.scoring import ScoringParams, score
from embedding_classifier.store import QUESTION
from embedding_classifier.vector_store import MemoryIndexStore
from tools.evaluate_kb import assemble, read_off_topic, split_questions

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

OFF_TOPIC = "off-topic"
BANDS = (0.01, 0.02, 0.03)
MIN_PROBABILITIES = (0.0, 0.5, 0.7, 0.9)
MESSAGES_FILE = "messages.jsonl"
ANSWER_FIELDS = [
    "id",
    "letter",
    "probability",
    "ms",
    "prompt_tokens",
    "cached_tokens",
    "first_call",
    "outcome",
]
# Go/no-go defaults; the developer and lead may change them
MIN_NET_GAIN_POINTS = 2.0
MAX_BROKEN_PER_FIXED = 0.5
MAX_OFF_TOPIC_ROUTED = 0.05


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--kb", type=Path, help="Knowledge base folder")
    parser.add_argument("--off-topic", action="append", default=[], type=Path)
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        type=Path,
        help="CSV of text, agency_id (empty = off-topic), language",
    )
    parser.add_argument("--embedding-model", default="multilingual-e5-large-instruct")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--ood-band", type=float, default=0.03)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Send at most this many knowledge-base messages per seed (a quick run)",
    )
    parser.add_argument("--model", help="Name of the model under test, for the results")
    parser.add_argument("--url", help="llama-server base URL")
    parser.add_argument("--timeout", type=float, default=300, help="Seconds per call")
    parser.add_argument(
        "--time-limit-ms",
        type=float,
        default=3000,
        help="SECOND_OPINION_TIMEOUT_MS to judge p95 against",
    )
    parser.add_argument("--threads", type=int, default=None)
    parser.add_argument("--cache", type=Path, help="Embedding cache folder")
    parser.add_argument(
        "--summarise-only", action="store_true", help="Only rebuild the summary"
    )
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.summarise_only:
        if not (args.out / MESSAGES_FILE).exists():
            if args.kb is None:
                raise SystemExit("--kb is needed to prepare the messages")
            prepare(args)
        if args.model and args.url:
            answer_all(args)
    write_summary(args.out, args.time_limit_ms)


def guess_language(text: str) -> str:
    """Good enough for the off-topic sets: Cyrillic is Russian; a few English words mark English."""
    if re.search("[а-яА-ЯёЁ]", text):
        return "ru"
    if re.search(r"\b(the|how|what|can|is|my|do|does|where|when)\b", text, re.I):
        return "en"
    return "et"


def read_extra(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path, dtype=str, keep_default_na=False) for path in paths]
    if not frames:
        return pd.DataFrame(columns=["text", "agency_id", "language"])
    return pd.concat(frames, ignore_index=True)


def prepare(args) -> None:
    """Score every message per seed and write the prompts of the ones that trigger."""
    questions = read_kb_questions(args.kb)
    agency_ids = sorted(questions["agency_id"].unique())
    position = {agency_id: i for i, agency_id in enumerate(agency_ids)}
    names = dict(zip(questions["agency_id"], questions["agency_name"]))
    name_list = [names[a] for a in agency_ids]
    off_topic = read_off_topic(args.off_topic)
    extra = read_extra(args.extra)
    unknown = set(extra["agency_id"]) - set(agency_ids) - {""}
    if unknown:
        raise SystemExit(
            f"Extra messages name agencies not in the knowledge base: {unknown}"
        )

    encoder = Encoder(get_model(args.embedding_model), threads=args.threads)
    cache = EmbeddingCache(args.cache or args.out / "cache")
    question_vectors = cache.encode(encoder, questions["question"].tolist(), "short")
    extra_texts = off_topic + extra["text"].tolist()
    extra_vectors = cache.encode(encoder, extra_texts, "short")
    extra_truth = [OFF_TOPIC] * len(off_topic) + [
        a if a else OFF_TOPIC for a in extra["agency_id"]
    ]
    extra_language = [guess_language(t) for t in off_topic] + extra["language"].tolist()
    extra_source = ["off_topic"] * len(off_topic) + ["extra"] * len(extra)

    store = MemoryIndexStore()
    agency_keys = [str(a) for a in agency_ids]
    messages, totals = [], {}
    for seed in range(args.seeds):
        split = split_questions(questions, seed)
        stored = split["store"]
        parts = {
            QUESTION: (
                questions.loc[stored, "agency_id"],
                questions.loc[stored, "question"],
                question_vectors[stored],
            )
        }
        rows, dense = assemble(parts, [QUESTION], names)
        keywords = KeywordVectorizer.fit([row.text for row in rows])
        collection = f"benchmark_s{seed}"
        store.delete_collection(collection)
        store.create_collection(
            collection, rows, dense, keywords.transform([row.text for row in rows])
        )

        def scored(vectors, texts):
            return score(
                store,
                collection,
                agency_keys,
                vectors,
                keywords.transform(texts),
                ScoringParams(),
                with_texts=True,
            )

        calib = questions.loc[split["calibration"]]
        gate, _ = calibrate(
            scored(question_vectors[split["calibration"]], calib["question"].tolist()),
            np.array([position[a] for a in calib["agency_id"]]),
        )
        test = questions.loc[split["test"]]
        groups = [
            (
                "kb",
                test["question"].tolist(),
                question_vectors[split["test"]],
                test["agency_id"].tolist(),
                ["et"] * len(test),
            ),
            ("extra", extra_texts, extra_vectors, extra_truth, extra_language),
        ]
        totals[seed] = {"kb_test": len(test), "bands": {}}
        for group, texts, vectors, truth, languages in groups:
            scores = scored(vectors, texts)
            decisions = decide(scores, gate)
            order = ranking(scores.fused)
            reasons = [so.trigger(d, gate.ood_cutoff, args.ood_band) for d in decisions]
            chosen = [i for i, reason in enumerate(reasons) if reason is not None]
            if group == "kb" and args.limit is not None and len(chosen) > args.limit:
                # A random sample: the test questions are in agency order
                rng = np.random.default_rng(seed)
                chosen = sorted(rng.choice(chosen, size=args.limit, replace=False))
            totals[seed][f"{group}_triggered"] = sum(r is not None for r in reasons)
            totals[seed][f"{group}_sent"] = len(chosen)
            for i, d in enumerate(decisions):
                below = gate.ood_cutoff - d.top_similarity
                if d.decision == OUT_OF_DISTRIBUTION and group == "kb":
                    for band in BANDS:
                        if below <= band:
                            key = str(band)
                            totals[seed]["bands"][key] = (
                                totals[seed]["bands"].get(key, 0) + 1
                            )
            for i in chosen:
                d, reason = decisions[i], reasons[i]
                options = so.candidates(
                    order[i], name_list, scores.texts[i], gate.clarify_candidates
                )
                truth_id = truth[i]
                messages.append(
                    {
                        "id": f"s{seed}-{group}-{i}",
                        "seed": seed,
                        "source": group if group == "kb" else extra_source[i],
                        "language": languages[i],
                        "text": texts[i],
                        "truth": truth_id,
                        "trigger": reason,
                        "decision": d.decision,
                        "margin": d.margin,
                        "top_similarity": d.top_similarity,
                        "ood_cutoff": gate.ood_cutoff,
                        "e5_top1": agency_ids[int(order[i, 0])],
                        "options": [agency_ids[o.position] for o in options],
                        "option_names": [o.name for o in options],
                        "option_examples": [o.examples for o in options],
                        "prompt": so.build_prompt(texts[i], options),
                    }
                )
        store.delete_collection(collection)
        logger.info(
            f"seed {seed}: {sum(m['seed'] == seed for m in messages)} messages trigger the second opinion"
        )

    with open(args.out / MESSAGES_FILE, "w", encoding="utf-8") as f:
        for message in messages:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
    with open(args.out / "totals.json", "w", encoding="utf-8") as f:
        json.dump(totals, f, indent=2)
    with open(args.out / "setup.json", "w", encoding="utf-8") as f:
        json.dump(
            {"seeds": args.seeds, "ood_band": args.ood_band, "limit": args.limit},
            f,
            indent=2,
        )


def read_messages(out: Path) -> list[dict]:
    with open(out / MESSAGES_FILE, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def ask(url: str, prompt: str, n_options: int, timeout: float) -> tuple[dict, float]:
    start = time.perf_counter()
    response = requests.post(
        url.rstrip("/") + "/v1/chat/completions",
        json=so.request_body(prompt, n_options),
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json(), (time.perf_counter() - start) * 1000


def answer_all(args) -> None:
    path = args.out / f"answers_{args.model}.csv"
    done = set()
    if path.exists():
        done = set(pd.read_csv(path, dtype=str)["id"])
    messages = [m for m in read_messages(args.out) if m["id"] not in done]
    logger.info(f"{args.model}: {len(messages)} messages to answer, {len(done)} done")
    new_file = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ANSWER_FIELDS)
        if new_file:
            writer.writeheader()
        for n, message in enumerate(messages):
            row = {"id": message["id"], "first_call": not done and n == 0}
            try:
                response, ms = ask(
                    args.url, message["prompt"], len(message["options"]), args.timeout
                )
                answer = so.read_answer(response, len(message["options"]))
                timings = response.get("timings") or {}
                row.update(
                    letter=answer.letter,
                    probability=answer.probability,
                    ms=round(ms),
                    prompt_tokens=answer.prompt_tokens,
                    cached_tokens=timings.get("cache_n"),
                    outcome=so.OK,
                )
            except requests.Timeout:
                row.update(outcome=so.TIMEOUT)
            except Exception as error:
                logger.warning(f"{message['id']}: {type(error).__name__}: {error}")
                row.update(outcome=so.ERROR)
            writer.writerow(row)
            f.flush()
            if (n + 1) % 25 == 0:
                logger.info(f"{args.model}: {n + 1} of {len(messages)} answered")


def top1_after(
    message: dict, letter: Optional[str], probability, min_probability
) -> tuple[str, bool]:
    """The top agency after applying the answer, and whether it was applied."""
    if not isinstance(letter, str) or letter == so.NONE_LETTER:
        return message["e5_top1"], False
    if probability < min_probability:
        return message["e5_top1"], False
    pick = message["options"][so.LETTERS.index(letter)]
    if message["trigger"] == so.CLARIFY_TRIGGER and pick == message["e5_top1"]:
        return pick, False
    return pick, True


def model_summary(
    messages: list[dict], answers: pd.DataFrame, totals: dict, time_limit_ms: float
) -> dict:
    by_id = answers.set_index("id")
    kb_test = sum(t["kb_test"] for t in totals.values())
    sweep = {}
    for min_probability in MIN_PROBABILITIES:
        fixed = broken = rescued = offtopic_routed = offtopic_seen = 0
        borderline_real = 0
        by_language: dict[str, dict] = {}
        for m in messages:
            if m["id"] not in by_id.index:
                continue
            a = by_id.loc[m["id"]]
            top, applied = top1_after(m, a["letter"], a["probability"], min_probability)
            truth = m["truth"]
            stats = by_language.setdefault(
                m["language"], {"messages": 0, "fixed": 0, "broken": 0, "rescued": 0}
            )
            stats["messages"] += 1
            if truth == OFF_TOPIC:
                offtopic_seen += 1
                offtopic_routed += int(applied and m["trigger"] == so.OOD_TRIGGER)
                continue
            was_right, is_right = m["e5_top1"] == truth, top == truth
            if not was_right and is_right:
                stats["fixed"] += 1
                fixed += m["source"] == "kb"
            if was_right and not is_right:
                stats["broken"] += 1
                broken += m["source"] == "kb"
            if m["trigger"] == so.OOD_TRIGGER:
                borderline_real += 1
                if applied and is_right:
                    stats["rescued"] += 1
                    rescued += 1
        sweep[str(min_probability)] = {
            "fixed": fixed,
            "broken": broken,
            "net_top1_gain_points": 100 * (fixed - broken) / kb_test
            if kb_test
            else None,
            "borderline_real_questions": borderline_real,
            "borderline_rescued": rescued,
            "off_topic_seen": offtopic_seen,
            "off_topic_routed": offtopic_routed,
            "by_language": by_language,
        }

    ok = answers[answers["outcome"] == so.OK]
    warm = ok[~ok["first_call"].astype(str).str.lower().eq("true")]["ms"].astype(float)
    first = ok[ok["first_call"].astype(str).str.lower().eq("true")]["ms"].astype(float)
    letters = ok["letter"].value_counts(normalize=True).to_dict()
    default = sweep["0.5"]
    p95 = float(np.percentile(warm, 95)) if len(warm) else None
    checks = {
        "net_gain_at_least_2_points": (default["net_top1_gain_points"] or 0)
        >= MIN_NET_GAIN_POINTS,
        "breaks_at_most_half_what_it_fixes": default["broken"]
        <= MAX_BROKEN_PER_FIXED * default["fixed"],
        "routes_at_most_5pct_of_off_topic": (
            default["off_topic_routed"] / default["off_topic_seen"]
            if default["off_topic_seen"]
            else 0
        )
        <= MAX_OFF_TOPIC_ROUTED,
        "p95_within_time_limit": p95 is not None and p95 <= time_limit_ms,
    }
    return {
        "answered": int(len(answers)),
        "outcomes": answers["outcome"].value_counts().to_dict(),
        "answer_mix": {k: float(v) for k, v in letters.items()},
        "ms": {
            "first_call": float(first.iloc[0]) if len(first) else None,
            "warm_p50": float(np.percentile(warm, 50)) if len(warm) else None,
            "warm_p95": p95,
        },
        "prompt_tokens_p50": float(ok["prompt_tokens"].astype(float).median())
        if len(ok)
        else None,
        "kb_test_messages": kb_test,
        "min_probability_sweep": sweep,
        "checks_at_min_probability_0.5": checks,
        "go": all(checks.values()),
    }


def write_summary(out: Path, time_limit_ms: float) -> None:
    messages = read_messages(out)
    with open(out / "totals.json", encoding="utf-8") as f:
        totals = json.load(f)
    models = {}
    for path in sorted(out.glob("answers_*.csv")):
        answers = pd.read_csv(path, dtype={"id": str, "letter": str})
        if len(answers):
            models[path.stem[len("answers_") :]] = model_summary(
                messages, answers, totals, time_limit_ms
            )
    triggers = pd.Series([m["trigger"] for m in messages]).value_counts().to_dict()
    with open(out / "setup.json", encoding="utf-8") as f:
        setup = json.load(f)
    summary = {
        "setup": setup,
        "messages": len(messages),
        "triggers": triggers,
        "kb_test_messages": sum(t["kb_test"] for t in totals.values()),
        "kb_triggered": sum(t.get("kb_triggered", 0) for t in totals.values()),
        "kb_sent": sum(t.get("kb_sent", 0) for t in totals.values()),
        "kb_off_topic_by_band": {
            band: sum(t["bands"].get(band, 0) for t in totals.values())
            for band in map(str, BANDS)
        },
        "models": models,
    }
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    lines = [
        "# Second-opinion benchmark",
        "",
        f"{summary['messages']} messages sent ({triggers}). Of "
        f"{summary['kb_test_messages']} knowledge-base test messages over all seeds, "
        f"{summary['kb_triggered']} trigger the second opinion and {summary['kb_sent']} were sent. "
        f"Knowledge-base questions flagged off-topic within 0.01 / 0.02 / 0.03 of the cutoff: "
        + " / ".join(str(v) for v in summary["kb_off_topic_by_band"].values())
        + ".",
        "",
        f"Seeds {setup['seeds']}, ood_band {setup['ood_band']}."
        + (
            f" **Quick run: a random {setup['limit']} of the knowledge-base messages that"
            " trigger were sent per seed. Fixed, broken and the net gain count only those;"
            " scale them by triggered / sent for an estimate of a full run.**"
            if setup["limit"] is not None
            else ""
        ),
        "",
        "| Model | Answered | Fixed | Broken | Net top-1 gain | Off-topic routed | Borderline rescued "
        "| Answer mix | Warm p50 / p95 ms | First call ms | Go |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in models.items():
        d = m["min_probability_sweep"]["0.5"]
        gain = d["net_top1_gain_points"]
        mix = ", ".join(f"{k} {v:.0%}" for k, v in sorted(m["answer_mix"].items()))
        ms = m["ms"]
        lines.append(
            f"| {name} | {m['answered']} | {d['fixed']} | {d['broken']} "
            f"| {'n/a' if gain is None else f'{gain:+.2f} pts'} "
            f"| {d['off_topic_routed']} of {d['off_topic_seen']} "
            f"| {d['borderline_rescued']} of {d['borderline_real_questions']} | {mix} "
            f"| {_num(ms['warm_p50'])} / {_num(ms['warm_p95'])} | {_num(ms['first_call'])} "
            f"| {'go' if m['go'] else 'no-go'} |"
        )
    lines += [
        "",
        "Fixed, broken and the gain count knowledge-base messages at min_probability 0.5.",
        "",
    ]
    for name, m in models.items():
        lines += [
            f"## {name}",
            "",
            "| min_probability | Fixed | Broken | Net gain | Off-topic routed |",
        ]
        lines.append("| --- | --- | --- | --- | --- |")
        for p, d in m["min_probability_sweep"].items():
            gain = d["net_top1_gain_points"]
            lines.append(
                f"| {p} | {d['fixed']} | {d['broken']} | {'n/a' if gain is None else f'{gain:+.2f}'} "
                f"| {d['off_topic_routed']} of {d['off_topic_seen']} |"
            )
        lines += ["", "By language (min_probability 0.5):", ""]
        for language, s in m["min_probability_sweep"]["0.5"]["by_language"].items():
            lines.append(
                f"- {language}: {s['messages']} messages, fixed {s['fixed']}, broken {s['broken']}, "
                f"rescued from off-topic {s['rescued']}"
            )
        failed = [k for k, v in m["checks_at_min_probability_0.5"].items() if not v]
        lines += ["", f"Checks failed: {', '.join(failed) if failed else 'none'}", ""]
    with open(out / "SUMMARY.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info(f"Summary written to {out}")


def _num(value) -> str:
    return "n/a" if value is None else f"{value:.0f}"


if __name__ == "__main__":
    main()
