"""
Check a dataset version for the questions the classifier can't learn from as
written (no clue to the agency, topics two agencies share, labels that may be
wrong), and write a report for people who know the agencies to review:
dataset_check.md and dataset_check.csv. See embedding_classifier/dataset_check.py.

Example, from src/embedding-classifier, with a dataset version's
aggregated_dataset.csv (datasets/{id}/aggregated_dataset.csv in S3):
    python -m tools.dataset_check --csv aggregated_dataset.csv --out check/ --cache cache/
"""

import argparse
import logging
from collections import Counter
from pathlib import Path

from embedding_classifier.content import clean_questions, read_aggregated_dataset
from embedding_classifier.dataset_check import CheckParams, check, write_report
from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import Encoder, get_model
from embedding_classifier.store import QUESTION, embed_rows, rows_from_frame

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def main() -> None:
    defaults = CheckParams()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model", default="multilingual-e5-large-instruct")
    parser.add_argument(
        "--cache", type=Path, help="Embedding cache folder (default: <out>/cache)"
    )
    parser.add_argument("--threads", type=int)
    parser.add_argument("--folds", type=int, default=defaults.folds)
    parser.add_argument("--neighbours", type=int, default=defaults.neighbours)
    parser.add_argument(
        "--no-clue-min-agencies", type=int, default=defaults.no_clue_min_agencies
    )
    parser.add_argument(
        "--no-clue-max-words", type=int, default=defaults.no_clue_max_words
    )
    parser.add_argument("--min-examples", type=int, default=defaults.min_examples)
    args = parser.parse_args()

    questions, warnings = clean_questions(read_aggregated_dataset(str(args.csv)))
    for warning in warnings:
        logger.info(warning)
    names = dict(zip(questions["agency_id"].astype(str), questions["agency_name"]))
    rows = rows_from_frame(questions, QUESTION, names, args.csv.name)
    vectors = embed_rows(
        Encoder(get_model(args.model), threads=args.threads),
        rows,
        EmbeddingCache(args.cache or args.out / "cache"),
    )
    params = CheckParams(
        folds=args.folds,
        neighbours=args.neighbours,
        no_clue_min_agencies=args.no_clue_min_agencies,
        no_clue_max_words=args.no_clue_max_words,
        min_examples=args.min_examples,
    )
    result = check(questions, vectors, params)
    write_report(result, args.out, title=args.csv.name)
    counts = Counter(result.questions["cause"])
    logger.info(
        f"{len(questions)} questions, cross-validated top-1 {counts.get('', 0) / len(questions):.3f}; "
        + ", ".join(f"{c} {n}" for c, n in sorted(counts.items()) if c)
        + f"; report in {args.out}"
    )


if __name__ == "__main__":
    main()
