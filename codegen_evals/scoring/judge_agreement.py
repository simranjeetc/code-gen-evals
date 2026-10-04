"""Measure agreement between two judge models over the reference solutions.

The references are the only known-correct set, so disagreement there is a pure
judge artefact rather than a judgement call about ambiguous code. Two judges
scoring them measures **stability**, not correctness: two judges from the same
vendor can share a bias and agree. Correctness needs a human, which is out of
scope for this measurement and disclosed as such.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from .. import corpus
from .semantic import SemanticJudge

EXACT_TOLERANCE = 1e-9


def measure(
    specs: Sequence[Any],
    judges: Sequence[Tuple[str, SemanticJudge]],
) -> Dict[str, Any]:
    """Score every reference with every judge and summarise agreement.

    ``judges`` is a sequence of ``(name, judge)`` pairs; at least two distinct
    judges are required for the figure to mean anything. Each judge is asked to
    score the reference *as the candidate*, with the reference also supplied as
    the anchor, so a well-behaved judge should score it 1.0.
    """
    if len(judges) < 2:
        raise ValueError("judge agreement needs at least two judges")

    per_spec: List[Dict[str, Any]] = []
    for spec in specs:
        try:
            reference = corpus.solution_source(spec)
        except (OSError, ValueError):
            reference = ""
        prompt = corpus.render_prompt(spec)
        scores: List[Any] = []
        errors: List[Any] = []
        for _, judge in judges:
            verdict = judge.judge(
                spec,
                prompt,
                reference,
                subject_model="reference",
                reference=reference,
            )
            scores.append(verdict.score)
            errors.append(verdict.error)
        per_spec.append({"spec_id": spec.id, "scores": scores, "errors": errors})

    comparable = [row for row in per_spec if all(score is not None for score in row["scores"])]
    n = len(comparable)
    if n:
        exact = (
            sum(
                1
                for row in comparable
                if abs(row["scores"][0] - row["scores"][1]) < EXACT_TOLERANCE
            )
            / float(n)
        )
        mad = (
            sum(abs(row["scores"][0] - row["scores"][1]) for row in comparable)
            / float(n)
        )
    else:
        exact = None
        mad = None

    return {
        "judges": [name for name, _ in judges],
        "specs_total": len(per_spec),
        "n": n,
        "exact_match_rate": exact,
        "mean_absolute_difference": mad,
        "per_spec": per_spec,
    }
