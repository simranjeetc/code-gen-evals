"""Four-dimension eval framework for code-generation model quality."""

from __future__ import annotations

from .models import SCHEMA_VERSION, DimensionScores, EvalResult, Generation, Spec

__all__ = [
    "SCHEMA_VERSION",
    "Spec",
    "Generation",
    "DimensionScores",
    "EvalResult",
]

__version__ = "0.1.0"
