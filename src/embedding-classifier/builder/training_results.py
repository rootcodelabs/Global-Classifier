"""
The quality report in the shape the GUI's TrainingResults screen renders
(data_models.training_results), with every field meaning what the trainer
makes it mean, so old and new rows compare like for like.
"""

import numpy as np

# Same weights as the trainer's combined score
PRECISION_WEIGHT = 0.7
F1_WEIGHT = 0.3


def training_results(builds: list[tuple[str, str, dict]], s3_folder: str) -> list[dict]:
    """
    One entry per embedding model built; never empty, since the screen
    crashes on an empty list.

    Args:
        builds: (model key, Hugging Face id, quality report) per model
        s3_folder: The build's folder, models/indexes/{model_id}/
    """
    if not builds:
        raise ValueError("No build to report")
    return [entry(key, hf_id, report, s3_folder) for key, hf_id, report in builds]


def entry(key: str, hf_id: str, report: dict, s3_folder: str) -> dict:
    metrics = report["metrics"]
    agencies = metrics["per_agency"]
    precision = [a["precision"] for a in agencies]
    f1 = [a["f1"] for a in agencies]
    avg_precision = float(np.mean(precision)) if precision else 0.0
    avg_f1 = float(np.mean(f1)) if f1 else 0.0
    gate = report.get("gate_params") or report.get("calibration_on_eval_collection", {})
    return {
        "variant": {
            "name": key,
            "base_model": key,
            "full_model_name": hf_id,
            "ood_method": "similarity_cutoff",
            "type": "embedding_index",
            "uncertainty_strategy": "inject_class",
            "human_handoff_threshold": gate.get("route_margin"),
            "confidence_scaling": False,
        },
        "model_path": s3_folder,
        # Positional, as the screen reads it: names, per-agency precision, per-agency F1
        "metrics": [[a["agency_name"] for a in agencies], precision, f1],
        # The trainer's avg_accuracy is mean per-agency precision; keep that meaning
        "avg_accuracy": avg_precision,
        "avg_f1": avg_f1,
        "combined_score": PRECISION_WEIGHT * avg_precision + F1_WEIGHT * avg_f1,
        "index_metrics": {
            "top1": metrics["top1"],
            "top3": metrics["top3"],
            "top5": metrics["top5"],
            "routed_share": metrics["routed_share"],
            "routed_accuracy": metrics["routed_accuracy"],
            "real_wrongly_flagged": metrics["real_wrongly_flagged"],
            "off_topic_caught": metrics["off_topic_caught"],
            "decision_mix": metrics["decision_mix"],
            "test_questions": metrics["test_questions"],
            "gate": report["gate"],
            "weak_agencies": report["weak_agencies"],
            "warnings": report["warnings"],
        },
    }
