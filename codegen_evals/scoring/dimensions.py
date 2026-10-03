"""Execution and edge-case dimension scores."""

from __future__ import annotations

from typing import Optional

from ..models import ExecutionEvidence


def _fraction(evidence: Optional[ExecutionEvidence]) -> float:
    if evidence is None:
        return 0.0
    return max(0.0, min(1.0, evidence.fraction))


def execution_score(
    ground_truth: Optional[ExecutionEvidence], extraction_ok: bool = True
) -> float:
    """Fraction of ground-truth tests passed; 0.0 when nothing usable ran.

    A response with no extractable code scores 0.0 rather than being skipped, so
    a model that fails to answer is penalised exactly like one that answers
    wrongly.
    """
    if not extraction_ok:
        return 0.0
    return _fraction(ground_truth)


def edge_score(edge_case: Optional[ExecutionEvidence], extraction_ok: bool = True) -> float:
    """Fraction of hidden edge-case tests passed; independent of ground truth."""
    if not extraction_ok:
        return 0.0
    return _fraction(edge_case)


def execution_and_edge(
    ground_truth: Optional[ExecutionEvidence],
    edge_case: Optional[ExecutionEvidence],
    extraction_ok: bool = True,
):
    return (
        execution_score(ground_truth, extraction_ok),
        edge_score(edge_case, extraction_ok),
    )
