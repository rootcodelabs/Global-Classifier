"""
Output in the Triton v2 format. TOP_K_PREDICTIONS is exactly what today's
post-processing returns and classify.yml parses; DECISION is new.
"""

import json
from typing import Optional

from embedding_classifier.gate import (
    OUT_OF_DISTRIBUTION,
    Decision,
    GateParams,
    confidences,
    ranking,
)
from embedding_classifier.scoring import Scores
from embedding_classifier.store import Agency

TOP_K_PREDICTIONS = "TOP_K_PREDICTIONS"
DECISION = "DECISION"
OOD_AGENCY_ID = 0
OOD_AGENCY_NAME = "out_of_distribution"
# Above every agency's, so a caller that picks the highest confidence instead
# of the first entry also gets off-topic; classify.yml's network filter gives
# its own out_of_distribution entry the same
OOD_CONFIDENCE = 1.0


def predictions(
    scores: Scores,
    decisions: list[Decision],
    agencies: list[Agency],
    params: GateParams,
    top_k: Optional[int] = None,
) -> list[list[dict]]:
    """
    One prediction list per message: up to top_k agencies, best first, each
    {agency_id, agency_name, confidence}. An off-topic message also gets the
    out_of_distribution entry first, with confidence 1.0, so it comes first by
    confidence too.
    """
    top_k = min(top_k or params.top_k, len(agencies))
    order = ranking(scores.fused)
    confidence = confidences(scores.fused, params.temperature)
    results = []
    for i, decision in enumerate(decisions):
        items = [
            {
                "agency_id": agencies[a].agency_id,
                "agency_name": agencies[a].agency_name,
                "confidence": float(confidence[i, a]),
            }
            for a in order[i, :top_k]
        ]
        if decision.decision == OUT_OF_DISTRIBUTION:
            items.insert(
                0,
                {
                    "agency_id": OOD_AGENCY_ID,
                    "agency_name": OOD_AGENCY_NAME,
                    "confidence": OOD_CONFIDENCE,
                },
            )
        results.append(items)
    return results


def decision_records(decisions: list[Decision], agencies: list[Agency]) -> list[dict]:
    return [
        {
            "decision": d.decision,
            "margin": d.margin,
            "top_similarity": d.top_similarity,
            "candidates": [agencies[a].agency_id for a in d.candidates],
        }
        for d in decisions
    ]


def infer_outputs(
    prediction_lists: list[list[dict]], decisions: list[dict]
) -> list[dict]:
    """
    The "outputs" of a Triton v2 inference response. Serialised with
    json.dumps defaults, as today's post-processing does.
    """
    return [
        {
            "name": TOP_K_PREDICTIONS,
            "datatype": "BYTES",
            "shape": [1],
            "data": [json.dumps(prediction_lists)],
        },
        {
            "name": DECISION,
            "datatype": "BYTES",
            "shape": [1],
            "data": [json.dumps(decisions)],
        },
    ]
