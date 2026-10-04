"""Shared data structures for the eval framework.

Every persisted structure has a ``to_dict`` and ``from_dict`` pair so results
can be written to JSON and read back without extra dependencies. ``from_dict``
tolerates missing optional keys and ignores unknown ones, which keeps older
result files loadable as the schema grows.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 4

TIERS = ("easy", "medium", "hard")
SUITES = ("ground_truth", "edge_case")
DIMENSIONS = ("execution", "edge", "semantic", "style")

# Dimensions that are objective measurements. ``semantic`` is a judge's opinion
# and is carried alongside these, never blended into the composite.
OBJECTIVE_DIMENSIONS = ("execution", "edge", "style")

# Attempt outcomes. A failure and a bad score are different facts; ``outcome``
# records which happened. Only ``scored`` attempts are measurements.
OUTCOME_SCORED = "scored"
OUTCOME_TIMEOUT = "timeout"
OUTCOME_PROVIDER_ERROR = "provider_error"
OUTCOME_UNPARSEABLE_OUTPUT = "unparseable_output"
OUTCOME_NOT_ATTEMPTED = "not_attempted"
OUTCOMES = (
    OUTCOME_SCORED,
    OUTCOME_TIMEOUT,
    OUTCOME_PROVIDER_ERROR,
    OUTCOME_UNPARSEABLE_OUTPUT,
    OUTCOME_NOT_ATTEMPTED,
)

# Failure outcomes worth one retry with a longer budget. An unparseable answer
# or an attempt that never ran are not transient.
TRANSIENT_OUTCOMES = (OUTCOME_TIMEOUT, OUTCOME_PROVIDER_ERROR)


def is_infrastructure_failure(outcome: str) -> bool:
    """True when an attempt was not a fair measurement of the model."""
    return outcome != OUTCOME_SCORED


# Disagreement kinds produced by the scoring layer.
DISAGREEMENT_SEMANTIC = "tests_pass_semantics_fail"
DISAGREEMENT_FRAGILE = "passes_visible_fails_edges"
DISAGREEMENT_STYLE = "correct_but_unidiomatic"


def _known(cls: type, data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only keys that are real fields of ``cls``."""
    names = {f.name for f in fields(cls)}
    return {k: v for k, v in data.items() if k in names}


@dataclass
class Spec:
    """A single code-generation task plus where its files live on disk."""

    id: str = ""
    tier: str = ""
    tags: List[str] = field(default_factory=list)
    prompt: str = ""
    entrypoint: str = "solution"
    required_symbols: List[str] = field(default_factory=list)
    title: str = ""
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Spec":
        return cls(**_known(cls, data))


@dataclass
class Generation:
    """One model response for one spec prompt."""

    model_id: str = ""
    provider: str = ""
    spec_id: str = ""
    raw_text: str = ""
    code: Optional[str] = None
    extracted: bool = False
    error: Optional[str] = None
    duration_s: float = 0.0
    params: Dict[str, Any] = field(default_factory=dict)
    judge: bool = False
    outcome: str = OUTCOME_SCORED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Generation":
        return cls(**_known(cls, data))


@dataclass
class ExecutionEvidence:
    """The result of running one suite against one candidate."""

    suite: str = ""
    total: int = 0
    passed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    messages: Dict[str, str] = field(default_factory=dict)
    duration_s: float = 0.0
    returncode: Optional[int] = None
    timed_out: bool = False
    setup_error: Optional[str] = None
    stderr_tail: str = ""

    @property
    def passed_count(self) -> int:
        return len(self.passed)

    @property
    def fraction(self) -> float:
        """Passed tests over total tests; 0.0 when no tests ran."""
        if self.total <= 0:
            return 0.0
        return len(self.passed) / float(self.total)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["passed_count"] = self.passed_count
        data["fraction"] = self.fraction
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionEvidence":
        return cls(**_known(cls, data))


@dataclass
class Disagreement:
    """A flagged cross-dimension disagreement for one (model, spec) pair."""

    kind: str = ""
    dimensions: List[str] = field(default_factory=list)
    detail: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Disagreement":
        return cls(**_known(cls, data))


@dataclass
class DimensionScores:
    """The four independent quality scores for one (model, spec) pair.

    ``semantic`` is ``None`` when the judge abstained; it is excluded from
    averages rather than treated as zero.
    """

    execution: float = 0.0
    edge: float = 0.0
    style: float = 0.0
    semantic: Optional[float] = None
    semantic_rationale: Optional[str] = None
    semantic_judge: Optional[str] = None
    semantic_derived: bool = True
    style_checks: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DimensionScores":
        return cls(**_known(cls, data))


@dataclass
class EvalResult:
    """Everything known about one model's attempt at one spec."""

    model_id: str = ""
    provider: str = ""
    spec_id: str = ""
    tier: str = ""
    tags: List[str] = field(default_factory=list)
    scores: DimensionScores = field(default_factory=DimensionScores)
    composite: Optional[float] = None
    ground_truth: Optional[ExecutionEvidence] = None
    edge_case: Optional[ExecutionEvidence] = None
    extraction_ok: bool = False
    generation_duration_s: float = 0.0
    generation_error: Optional[str] = None
    outcome: str = OUTCOME_SCORED
    retry_count: int = 0
    # Which repetition of this (model, spec) pair this attempt is. Repeat 0 is
    # the only one that exists when repetition is not requested.
    repeat: int = 0
    disagreements: List[Disagreement] = field(default_factory=list)

    @property
    def scored(self) -> bool:
        return self.outcome == OUTCOME_SCORED

    @property
    def evidence(self) -> Dict[str, Optional[ExecutionEvidence]]:
        return {"ground_truth": self.ground_truth, "edge_case": self.edge_case}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "spec_id": self.spec_id,
            "tier": self.tier,
            "tags": list(self.tags),
            "scores": self.scores.to_dict(),
            "composite": self.composite,
            "ground_truth": self.ground_truth.to_dict() if self.ground_truth else None,
            "edge_case": self.edge_case.to_dict() if self.edge_case else None,
            "extraction_ok": self.extraction_ok,
            "generation_duration_s": self.generation_duration_s,
            "generation_error": self.generation_error,
            "outcome": self.outcome,
            "retry_count": self.retry_count,
            "repeat": self.repeat,
            "disagreements": [d.to_dict() for d in self.disagreements],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvalResult":
        data = dict(data)
        data["scores"] = DimensionScores.from_dict(data.get("scores") or {})
        for key in ("ground_truth", "edge_case"):
            value = data.get(key)
            data[key] = ExecutionEvidence.from_dict(value) if value else None
        data["disagreements"] = [
            Disagreement.from_dict(d) for d in (data.get("disagreements") or [])
        ]
        return cls(**_known(cls, data))


@dataclass
class RunMetadata:
    """Enough context to reproduce or re-render a run."""

    provider: str = ""
    models: List[str] = field(default_factory=list)
    judge_model: Optional[str] = None
    judge_design: Optional[str] = None
    judge_agreement: Optional[Dict[str, Any]] = None
    reference_baseline: Optional[Dict[str, Any]] = None
    corpus_count: int = 0
    tier_counts: Dict[str, int] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    thresholds: Dict[str, float] = field(default_factory=dict)
    temperature: float = 0.0
    mock: bool = False
    inconclusive: bool = False
    inconclusive_reason: Optional[str] = None
    unreliable: bool = False
    unreliable_models: List[str] = field(default_factory=list)
    unreliable_reason: Optional[str] = None
    timeout_s: Optional[float] = None
    exclusion_rate_threshold: Optional[float] = None
    # Repetition. ``repeat_count`` is k (attempts per pair), not the total
    # attempts. ``control_model`` names the deliberately weak model included to
    # measure whether the corpus discriminates; it is a control, never a peer.
    repeat_count: int = 1
    control_model: Optional[str] = None
    control_separated: Optional[bool] = None
    control_reason: Optional[str] = None
    variance_threshold: Optional[float] = None
    instability_multiplier: Optional[float] = None
    variance_guard_rule: Optional[str] = None
    unstable: bool = False
    unstable_models: List[str] = field(default_factory=list)
    unstable_reason: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_s: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunMetadata":
        return cls(**_known(cls, data))


@dataclass
class RunResults:
    """The persisted artifact: a pure input to report rendering."""

    metadata: RunMetadata = field(default_factory=RunMetadata)
    results: List[EvalResult] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "metadata": self.metadata.to_dict(),
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RunResults":
        return cls(
            metadata=RunMetadata.from_dict(data.get("metadata") or {}),
            results=[EvalResult.from_dict(r) for r in (data.get("results") or [])],
            schema_version=data.get("schema_version", SCHEMA_VERSION),
        )
