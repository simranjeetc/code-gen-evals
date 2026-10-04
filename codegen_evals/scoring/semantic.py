"""LLM-as-judge semantic scoring.

The judge answers one question: does the candidate satisfy the *stated intent* of
the task? Style is scored elsewhere, so the rubric tells the judge to ignore
formatting.

The judge is **anchored to the reference solution**: it is asked to compare the
candidate against the task author's accepted answer rather than to invent an
absolute standard on every call. Absolute scoring drifts; a reference pins the
scale down. This is the design used by pairwise benchmarks (MT-Bench,
AlpacaEval). The reference is hidden from the model under test and from no one
else, so showing it to the judge leaks nothing to the subject.

Two rules are structural, not advisory:

- the judge model must differ from the model under test, and
- a judge that cannot be parsed abstains (``None``) rather than being scored.

An abstention is excluded from averages instead of being counted as zero. The
score is an opinion, marked judge-derived in the data, and never blended into the
objective-only composite.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Optional

from ..models import Spec

JUDGE_MODEL_MARKER = "semantic_judge"

RUBRIC = """TASK REQUIREMENT:
{prompt}

REFERENCE SOLUTION (an accepted answer — the standard to compare against):
```python
{reference}
```

CANDIDATE SOLUTION (judge this one):
```python
{code}
```

Decide how well the candidate satisfies the requirement's intent, using the
reference to anchor the scale rather than inventing a standard of your own.
Compare behaviour, not surface shape.

Do not reward superficial similarity: a candidate that matches the reference's
shape but not its behaviour must NOT score 1.0, and a different implementation
that is equally correct must not be penalised.

Score bands (use the whole range; do not settle on 0.5 by default):
- 1.0 — behaviourally equivalent to the reference and satisfies the requirement,
  including its edge cases.
- 0.5 — partially satisfies: the main behaviour is present, but a stated part of
  the requirement or a likely edge case is missing or wrong.
- 0.0 — does not satisfy the requirement, or is wrong in a way the tests would
  catch.

Judge only whether the candidate satisfies the requirement's intent.
Ignore style, formatting, docstrings and comments.
Return only a JSON object: {{"score": <0..1>, "rationale": "<one or two sentences>"}}"""


class JudgeVerdict:
    __slots__ = ("score", "rationale", "judge_model", "error", "raw")

    def __init__(
        self,
        score: Optional[float] = None,
        rationale: Optional[str] = None,
        judge_model: Optional[str] = None,
        error: Optional[str] = None,
        raw: str = "",
    ):
        self.score = score
        self.rationale = rationale
        self.judge_model = judge_model
        self.error = error
        self.raw = raw

    @property
    def abstained(self) -> bool:
        return self.score is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "rationale": self.rationale,
            "judge_model": self.judge_model,
            "error": self.error,
        }


def build_prompt(prompt: str, reference: str, code: str) -> str:
    """Render the reference-anchored judge prompt.

    Pure and deterministic: identical inputs produce byte-identical output, so a
    score difference between two calls is judge variance, not prompt variance.
    """
    return RUBRIC.format(
        prompt=prompt.strip(),
        reference=(reference or "").strip(),
        code=code,
    )


_JSON_OBJECT = re.compile(r"\{.*\}", re.S)


def parse_verdict(text: str) -> Optional[Dict[str, Any]]:
    """Pull ``{"score": ..., "rationale": ...}`` out of noisy judge output."""
    if not text:
        return None
    candidates = [text.strip()]
    match = _JSON_OBJECT.search(text)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or "score" not in payload:
            continue
        try:
            score = float(payload["score"])
        except (TypeError, ValueError):
            continue
        score = max(0.0, min(1.0, score))
        rationale = payload.get("rationale")
        return {"score": score, "rationale": rationale if isinstance(rationale, str) else None}
    return None


class SemanticJudge:
    """Base judge: turn (spec, code, subject_model) into a verdict."""

    judge_model = "unknown"

    def judge(
        self,
        spec: Spec,
        prompt: str,
        code: Optional[str],
        subject_model: str,
        reference: Optional[str] = None,
    ) -> JudgeVerdict:
        raise NotImplementedError

    def _interpret(self, raw_text: str) -> JudgeVerdict:
        verdict = JudgeVerdict(judge_model=self.judge_model, raw=raw_text)
        if not raw_text:
            verdict.error = "judge returned no text"
            return verdict
        parsed = parse_verdict(raw_text)
        if parsed is None:
            verdict.error = "judge output was not parseable JSON; abstaining"
            return verdict
        verdict.score = parsed["score"]
        verdict.rationale = parsed["rationale"]
        return verdict


class ProviderJudge(SemanticJudge):
    """Judge backed by a provider (any model the provider layer can reach)."""

    def __init__(self, provider, judge_model: str):
        self.provider = provider
        self.judge_model = judge_model

    def judge(
        self,
        spec: Spec,
        prompt: str,
        code: Optional[str],
        subject_model: str,
        reference: Optional[str] = None,
    ) -> JudgeVerdict:
        if subject_model == self.judge_model:
            return JudgeVerdict(
                judge_model=self.judge_model,
                error="judge model equals subject model; refusing to self-grade",
            )
        if code is None or not code.strip():
            return JudgeVerdict(
                score=0.0,
                rationale="no code was produced",
                judge_model=self.judge_model,
            )
        generation = self.provider.generate_text(
            build_prompt(prompt, reference or "", code), self.judge_model, spec_id=spec.id
        )
        if generation.error:
            return JudgeVerdict(judge_model=self.judge_model, error=generation.error)
        return self._interpret(generation.raw_text or "")


class MockJudge(SemanticJudge):
    """Deterministic offline judge for mock runs.

    Scores derive from the subject's mock variant, plus a deterministic
    "passes the tests but misses the point" flip so the disagreement machinery
    has something real to find offline.
    """

    def __init__(
        self,
        variant_lookup: Callable[[str, str], str],
        judge_model: str = "mock-judge",
        flip_rate: float = 0.25,
    ):
        self._variant_lookup = variant_lookup
        self.judge_model = judge_model
        self.flip_rate = flip_rate

    def judge(
        self,
        spec: Spec,
        prompt: str,
        code: Optional[str],
        subject_model: str,
        reference: Optional[str] = None,
    ) -> JudgeVerdict:
        import hashlib

        variant = self._variant_lookup(subject_model, spec.id)
        base = {"perfect": 1.0, "untyped": 1.0, "stub": 0.25, "empty": 0.0}.get(variant, 0.5)

        digest = hashlib.sha256(f"{subject_model}|{spec.id}|semantic".encode()).hexdigest()
        draw = int(digest[:8], 16) / float(16 ** 8)

        if variant == "perfect" and draw < self.flip_rate:
            return JudgeVerdict(
                score=0.5,
                rationale="passes the visible behaviour but the intent is only partly met",
                judge_model=self.judge_model,
            )
        return JudgeVerdict(
            score=base,
            rationale=f"mock variant '{variant}'",
            judge_model=self.judge_model,
        )
