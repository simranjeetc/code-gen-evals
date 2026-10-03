"""Cross-dimension disagreement detection.

The point of scoring four dimensions separately is to be able to say *how* two
models differ, not just which one scored higher. Disagreements are the cases
where the dimensions tell different stories.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import (
    DISAGREEMENT_FRAGILE,
    DISAGREEMENT_SEMANTIC,
    DISAGREEMENT_STYLE,
    Disagreement,
    DimensionScores,
)

DEFAULT_HIGH = 0.8
DEFAULT_LOW = 0.6


def detect(
    scores: DimensionScores,
    high: float = DEFAULT_HIGH,
    low: float = DEFAULT_LOW,
) -> List[Disagreement]:
    """Flag disagreements for one (model, spec) pair."""
    found: List[Disagreement] = []
    semantic = scores.semantic

    if scores.execution >= high and semantic is not None and semantic < low:
        found.append(
            Disagreement(
                kind=DISAGREEMENT_SEMANTIC,
                dimensions=["execution", "semantic"],
                detail="passes the ground-truth tests but the judge says the intent is not met",
                evidence={"execution": scores.execution, "semantic": semantic},
            )
        )

    if scores.execution >= high and scores.edge < low:
        found.append(
            Disagreement(
                kind=DISAGREEMENT_FRAGILE,
                dimensions=["execution", "edge"],
                detail="passes the visible tests but breaks on the hidden edge cases",
                evidence={"execution": scores.execution, "edge": scores.edge},
            )
        )

    if scores.execution >= high and (semantic is None or semantic >= high) and scores.style < low:
        found.append(
            Disagreement(
                kind=DISAGREEMENT_STYLE,
                dimensions=["execution", "style"],
                detail="behaviour is right but the code is not idiomatic",
                evidence={
                    "execution": scores.execution,
                    "semantic": semantic,
                    "style": scores.style,
                    "failing_checks": {
                        name: value
                        for name, value in (scores.style_checks or {}).items()
                        if isinstance(value, (int, float)) and value < 1.0
                    },
                },
            )
        )

    return found


def thresholds_from_config(config) -> Dict[str, float]:
    return {
        "high": config.DEFAULT_THRESHOLDS["high"],
        "low": config.DEFAULT_THRESHOLDS["low"],
    }


def summarise(disagreements) -> Dict[str, int]:
    """Count disagreements by kind across a run."""
    counts: Dict[str, int] = {}
    for item in disagreements:
        counts[item.kind] = counts.get(item.kind, 0) + 1
    return counts
