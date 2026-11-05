"""
Build an index from a dataset's questions (and agency content, once it is
kept): clean, split, embed, evaluate through a temporary collection, apply the
quality gate, then create the final collection and the manifest.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from embedding_classifier import classifier_layer, evaluation
from embedding_classifier.artifact import build_manifest, collection_name
from embedding_classifier.calibration import calibrate
from embedding_classifier.classifier_layer import ClassifierLayer, LayerParams
from embedding_classifier.content import clean_questions
from embedding_classifier.embedding_cache import EmbeddingCache
from embedding_classifier.encoder import EmbeddingModel
from embedding_classifier.gate import (
    CLARIFY,
    OUT_OF_DISTRIBUTION,
    ROUTE,
    decide,
    margins,
    ranking,
)
from embedding_classifier.keywords import KeywordVectorizer
from embedding_classifier.scoring import METHOD, Scores, ScoringParams, score
from embedding_classifier.store import (
    QUESTION,
    Row,
    agencies_from_frame,
    count_by_agency,
    embed_rows,
    rows_from_frame,
)
from embedding_classifier.vector_store import IndexStore

logger = logging.getLogger(__name__)

GATE_CONFIG_FILE = Path(__file__).with_name("quality_gate.json")
SCORING_CONFIG_FILE = Path(__file__).with_name("scoring.json")
SPLIT_SEED = 0
REPORT = "report"
ENFORCE = "enforce"


@dataclass(frozen=True)
class GateConfig:
    mode: str = REPORT
    min_top3: float = 0.85
    max_top1_regression: float = 0.02
    max_routed_regression: float = 0.05
    max_real_wrongly_flagged: float = 0.08
    weak_agency_recall: float = 0.2
    weak_agency_min_test_questions: int = 20

    @classmethod
    def load(cls, path: Path = GATE_CONFIG_FILE) -> "GateConfig":
        with open(path, encoding="utf-8") as f:
            config = cls(**json.load(f))
        if config.mode not in (REPORT, ENFORCE):
            raise ValueError(f"Unknown quality gate mode {config.mode!r}")
        return config


@dataclass(frozen=True)
class ScoringConfig:
    """
    classifier_layer: add the classifier layer
        (embedding_classifier/classifier_layer.py) on top of the
        nearest-neighbour search
    classifier_c: its regression's inverse regularisation strength
    """

    classifier_layer: bool = False
    classifier_c: float = LayerParams.c

    @classmethod
    def load(cls, path: Path = SCORING_CONFIG_FILE) -> "ScoringConfig":
        with open(path, encoding="utf-8") as f:
            return cls(**json.load(f))

    def layer_params(self) -> Optional[LayerParams]:
        """What build_index takes: None when the layer is off."""
        return LayerParams(c=self.classifier_c) if self.classifier_layer else None


@dataclass
class BuildResult:
    """passed is False only when the gate failed in enforce mode."""

    report: dict
    passed: bool
    manifest: Optional[dict] = None
    keywords: Optional[KeywordVectorizer] = None
    collection: Optional[str] = None
    agency_names: list[str] = field(default_factory=list)
    layer: Optional[ClassifierLayer] = None


def split_questions(
    questions: pd.DataFrame, seed: int = SPLIT_SEED
) -> dict[str, np.ndarray]:
    """Per agency: 10% test and 10% calibration (at least one each), the rest stored."""
    rng = np.random.default_rng(seed)
    parts = {"store": [], "calibration": [], "test": []}
    for _, group in questions.groupby("agency_id", sort=True):
        rows = rng.permutation(group.index.to_numpy())
        n_test = max(1, round(len(rows) * 0.1))
        n_calibration = max(1, round(len(rows) * 0.1))
        parts["test"].extend(rows[:n_test])
        parts["calibration"].extend(rows[n_test : n_test + n_calibration])
        parts["store"].extend(rows[n_test + n_calibration :])
    return {name: np.array(rows, dtype=int) for name, rows in parts.items()}


def build_index(
    *,
    model_id,
    questions: pd.DataFrame,
    model: EmbeddingModel,
    encoder,
    store: IndexStore,
    gate_config: GateConfig,
    dataset: dict,
    content: list[Row] = (),
    off_topic: list[str] = (),
    cache: Optional[EmbeddingCache] = None,
    scoring: ScoringParams = ScoringParams(),
    baseline: Optional[dict] = None,
    warnings: list[str] = (),
    builder_commit: str = "",
    collection: Optional[str] = None,
    layer_params: Optional[LayerParams] = None,
) -> BuildResult:
    """
    Build one index.

    Args:
        model_id: The data model's id; names the collection gc_index_{model_id}
        questions: Columns agency_id, agency_name, text
        model: Embedding model and pinned revision
        encoder: Encoder for that model
        store: Where collections are created
        gate_config: Quality gate thresholds and mode
        dataset: {id, major, minor} for the manifest
        content: Title and passage rows, stored with every split
        off_topic: Off-topic messages to measure detection on
        cache: Embedding cache
        baseline: Golden-set metrics of the current production index, for the regression checks
        warnings: Warnings from earlier steps, carried into the report
        collection: The final collection's name; gc_index_{model_id} by default
        layer_params: Train the classifier layer with these settings; None
            builds without it
    """
    report_warnings = list(warnings)
    cleaned, cleaning_warnings = clean_questions(questions)
    report_warnings += cleaning_warnings
    agencies = agencies_from_frame(cleaned)
    if not agencies:
        raise ValueError("No agency has enough questions to build an index")
    if len(agencies) == 1:
        # Still useful: messages route to it unless they are off-topic
        report_warnings.append(
            f"Only one agency ({agencies[0].agency_name}): every message that isn't "
            "off-topic routes to it"
        )
    keys = [a.key for a in agencies]
    names = {a.key: a.agency_name for a in agencies}
    position = {key: i for i, key in enumerate(keys)}
    content = list(content)
    use_layer = layer_params is not None and len(agencies) > 1
    if layer_params is not None and not use_layer:
        report_warnings.append(
            "The classifier layer needs at least two agencies; built without it"
        )

    split = split_questions(cleaned)
    question_rows = rows_from_frame(
        cleaned, QUESTION, names, f"dataset {dataset.get('id')}"
    )
    question_vectors = embed_rows(encoder, question_rows, cache)
    content_vectors = embed_rows(encoder, content, cache)
    off_topic_vectors = embed_rows(
        encoder, [Row("", "", "offtopic", t) for t in off_topic], cache
    )

    def rows_of(part: str) -> list[Row]:
        return [question_rows[i] for i in split[part]]

    def truth_of(part: str) -> np.ndarray:
        return np.array([position[question_rows[i].agency_key] for i in split[part]])

    def truth_of_rows(rows: list[Row]) -> np.ndarray:
        return np.array([position[row.agency_key] for row in rows])

    def messages(part: str):
        return question_vectors[split[part]], [row.text for row in rows_of(part)]

    # Evaluate through Qdrant, the same path that serves
    eval_rows = rows_of("store") + content
    eval_dense = np.vstack([question_vectors[split["store"]], content_vectors])
    eval_keywords = KeywordVectorizer.fit([row.text for row in eval_rows])
    eval_keyword_vectors = eval_keywords.transform([r.text for r in eval_rows])
    eval_collection = f"gc_eval_{model_id}"

    def scored(
        collection: str,
        keywords: KeywordVectorizer,
        vectors,
        texts,
        layer: Optional[ClassifierLayer] = None,
    ) -> Scores:
        keyword_vectors = keywords.transform(texts)
        result = score(store, collection, keys, vectors, keyword_vectors, scoring)
        return result if layer is None else layer.apply(result, keyword_vectors)

    # The classifier layer learns from the rows the collection stores; its
    # weights are chosen on the calibration split
    eval_layer, layer_top1 = None, None
    if use_layer:
        eval_layer = classifier_layer.fit(
            eval_keyword_vectors, truth_of_rows(eval_rows), len(keys), layer_params
        )

    store.delete_collection(eval_collection)
    try:
        store.create_collection(
            eval_collection, eval_rows, eval_dense, eval_keyword_vectors
        )
        if use_layer:
            vectors, texts = messages("calibration")
            eval_layer, layer_top1 = classifier_layer.choose_weights(
                eval_layer,
                scored(eval_collection, eval_keywords, vectors, texts),
                eval_keywords.transform(texts),
                truth_of("calibration"),
            )
        calibration_scores = scored(
            eval_collection, eval_keywords, *messages("calibration"), eval_layer
        )
        gate_params, calibration_warnings = calibrate(
            calibration_scores, truth_of("calibration")
        )
        test_scores = scored(
            eval_collection, eval_keywords, *messages("test"), eval_layer
        )
        off_topic_scores = (
            scored(
                eval_collection,
                eval_keywords,
                off_topic_vectors,
                list(off_topic),
                eval_layer,
            )
            if off_topic
            else None
        )
    finally:
        store.delete_collection(eval_collection)
    report_warnings += calibration_warnings

    metrics = measure(
        test_scores, truth_of("test"), gate_params, off_topic_scores, agencies
    )
    checks = gate_checks(metrics, gate_config, baseline)
    failed = [c for c in checks if c["status"] == "failed"]
    weak = [
        f"{a['agency_name']} ({a['agency_id']}): recall {a['recall']:.2f} on {a['test_questions']} test questions"
        for a in metrics["per_agency"]
        if a["test_questions"] >= gate_config.weak_agency_min_test_questions
        and a["recall"] < gate_config.weak_agency_recall
    ]
    passed = not failed or gate_config.mode == REPORT
    report = {
        "model_id": model_id,
        "embedding_model": model.hf_id,
        "embedding_model_revision": model.revision,
        "dataset": dataset,
        "questions": {
            "kept": int(len(cleaned)),
            "store": int(len(split["store"])),
            "calibration": int(len(split["calibration"])),
            "test": int(len(split["test"])),
        },
        "content_rows": len(content),
        "scoring": scoring_report(eval_layer, layer_top1),
        "gate": {
            "mode": gate_config.mode,
            "passed": not failed,
            "deployable": passed,
            "checks": checks,
        },
        "metrics": metrics,
        "calibration_on_eval_collection": gate_params_dict(gate_params),
        "weak_agencies": weak,
        "warnings": report_warnings,
    }
    if not passed:
        logger.warning(
            f"Build {model_id} failed the quality gate: {[c['check'] for c in failed]}"
        )
        return BuildResult(report=report, passed=False)

    # Final index: the stored and test questions plus content; calibration stays held out
    final_rows = rows_of("store") + rows_of("test") + content
    final_dense = np.vstack(
        [
            question_vectors[split["store"]],
            question_vectors[split["test"]],
            content_vectors,
        ]
    )
    keywords = KeywordVectorizer.fit([row.text for row in final_rows])
    final_keyword_vectors = keywords.transform([r.text for r in final_rows])
    final_layer = None
    if use_layer:
        final_layer = classifier_layer.fit(
            final_keyword_vectors,
            truth_of_rows(final_rows),
            len(keys),
            layer_params,
            weights=eval_layer.weights,
            knn_scale=eval_layer.knn_scale,
        )
    collection = collection or collection_name(model_id)
    store.delete_collection(collection)
    try:
        store.create_collection(
            collection, final_rows, final_dense, final_keyword_vectors
        )
        final_gate, _ = calibrate(
            scored(collection, keywords, *messages("calibration"), final_layer),
            truth_of("calibration"),
        )
    except Exception:
        store.delete_collection(collection)
        raise

    manifest = build_manifest(
        model_id=model_id,
        model=model,
        dim=int(final_dense.shape[1]),
        collection=collection,
        points=len(final_rows),
        scoring=scoring,
        gate=final_gate,
        keywords=keywords,
        agencies=agencies,
        counts=count_by_agency(final_rows),
        dataset=dataset,
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        builder_commit=builder_commit,
        layer=final_layer,
    )
    report["gate_params"] = gate_params_dict(final_gate)
    return BuildResult(
        report,
        True,
        manifest,
        keywords,
        collection,
        [a.agency_name for a in agencies],
        final_layer,
    )


def scoring_report(layer: Optional[ClassifierLayer], top1: Optional[dict]) -> dict:
    """How the build scores; with a classifier layer, its weights and each part's calibration top-1."""
    if layer is None:
        return {"method": METHOD}
    return {
        "method": classifier_layer.METHOD,
        **layer.describe(),
        "calibration_top1": top1,
    }


def measure(
    scores: Scores, truth: np.ndarray, gate_params, off_topic_scores, agencies
) -> dict:
    """What the quality gate and the report need, measured on the test split."""
    order = ranking(scores.fused)
    correct = order[:, 0] == truth
    margin = margins(scores.fused)
    decisions = [d.decision for d in decide(scores, gate_params)]
    per = evaluation.per_agency(order[:, 0], truth, len(agencies))
    routed = evaluation.routed(margin, correct, gate_params.route_margin)
    return {
        **evaluation.topk_accuracy(scores.fused, truth),
        "routed_share": routed["share"],
        "routed_accuracy": None if np.isnan(routed["accuracy"]) else routed["accuracy"],
        "routed_at_90_share": evaluation.coverage_at(margin, correct, 0.9),
        "real_wrongly_flagged": float(
            np.mean(scores.top_similarity < gate_params.ood_cutoff)
        ),
        "off_topic_caught": (
            float(np.mean(off_topic_scores.top_similarity < gate_params.ood_cutoff))
            if off_topic_scores is not None
            else None
        ),
        "decision_mix": {
            d: float(np.mean([x == d for x in decisions]))
            for d in (ROUTE, CLARIFY, OUT_OF_DISTRIBUTION)
        },
        "test_questions": int(len(truth)),
        "per_agency": [
            {
                "agency_id": a.agency_id,
                "agency_name": a.agency_name,
                "test_questions": int(np.sum(truth == i)),
                "precision": per["precision"][i],
                "recall": per["recall"][i],
                "f1": per["f1"][i],
            }
            for i, a in enumerate(agencies)
        ],
    }


def gate_checks(
    metrics: dict, config: GateConfig, baseline: Optional[dict]
) -> list[dict]:
    """
    The quality gate's checks. With no golden set yet, top-3 is measured on the
    test split and the regression checks are skipped.
    """

    def check(name, value, rule, ok, skipped_reason=None):
        status = "skipped" if skipped_reason else ("passed" if ok else "failed")
        return {
            "check": name,
            "value": value,
            "rule": rule,
            "status": status,
            "note": skipped_reason,
        }

    top1, routed = metrics["top1"], metrics["routed_share"]
    checks = [
        check(
            "top3",
            metrics["top3"],
            f">= {config.min_top3}",
            metrics["top3"] >= config.min_top3,
        ),
        check(
            "real_wrongly_flagged",
            metrics["real_wrongly_flagged"],
            f"<= {config.max_real_wrongly_flagged}",
            metrics["real_wrongly_flagged"] <= config.max_real_wrongly_flagged,
        ),
    ]
    no_baseline = (
        None if baseline else "no golden-set baseline from a production index yet"
    )
    checks.append(
        check(
            "top1_regression",
            None if no_baseline else baseline["top1"] - top1,
            f"<= {config.max_top1_regression}",
            bool(baseline) and baseline["top1"] - top1 <= config.max_top1_regression,
            no_baseline,
        )
    )
    checks.append(
        check(
            "routed_regression",
            None if no_baseline else baseline["routed_share"] - routed,
            f"<= {config.max_routed_regression}",
            bool(baseline)
            and baseline["routed_share"] - routed <= config.max_routed_regression,
            no_baseline,
        )
    )
    return checks


def gate_params_dict(params) -> dict:
    return {
        "ood_cutoff": params.ood_cutoff,
        "route_margin": params.route_margin,
        "temperature": params.temperature,
    }
