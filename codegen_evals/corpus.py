"""Corpus loading, validation, and prompt rendering.

The corpus lives in ``corpus/<spec-id>/`` with a ``spec.json`` plus the
reference solution and the two hidden suites. The model only ever sees the
rendered prompt, never the tests or the reference.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import SUITES, TIERS, Spec

SPEC_FILENAME = "spec.json"
SOLUTION_FILENAME = "solution.py"
GROUND_TRUTH_FILENAME = "test_ground_truth.py"
EDGE_CASE_FILENAME = "test_edge_cases.py"

REQUIRED_FIELDS = ("id", "tier", "tags", "prompt", "required_symbols")


def default_corpus_root() -> Path:
    """The repository's ``corpus/`` directory (two levels above this module)."""
    return Path(__file__).resolve().parent.parent / "corpus"


def spec_file_paths(spec_dir: Path) -> Dict[str, Path]:
    return {
        "spec": spec_dir / SPEC_FILENAME,
        "solution": spec_dir / SOLUTION_FILENAME,
        "ground_truth": spec_dir / GROUND_TRUTH_FILENAME,
        "edge_case": spec_dir / EDGE_CASE_FILENAME,
    }


def load_spec(spec_dir: Path) -> Spec:
    """Load one spec from its directory. Raises ``ValueError`` if malformed."""
    spec_dir = Path(spec_dir)
    paths = spec_file_paths(spec_dir)
    if not paths["spec"].exists():
        raise ValueError(f"{spec_dir}: missing {SPEC_FILENAME}")
    with paths["spec"].open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError(f"{spec_dir}: {SPEC_FILENAME} must contain a JSON object")
    spec = Spec.from_dict(raw)
    spec.path = str(spec_dir)
    return spec


def validate_spec(spec: Spec, spec_dir: Optional[Path] = None) -> List[str]:
    """Return a list of problems with one spec. Empty list means valid."""
    problems: List[str] = []
    where = spec.id or (str(spec_dir) if spec_dir else "<unknown>")

    for field_name in REQUIRED_FIELDS:
        value = getattr(spec, field_name, None)
        if value is None or value == "" or value == []:
            problems.append(f"{where}: missing required field '{field_name}'")

    if spec.tier and spec.tier not in TIERS:
        problems.append(
            f"{where}: invalid tier '{spec.tier}' (expected one of {', '.join(TIERS)})"
        )
    if spec.tags and not isinstance(spec.tags, list):
        problems.append(f"{where}: 'tags' must be a list")
    if spec.required_symbols and not isinstance(spec.required_symbols, list):
        problems.append(f"{where}: 'required_symbols' must be a list")

    if spec_dir is not None:
        if spec.id and spec.id != Path(spec_dir).name:
            problems.append(
                f"{where}: spec id does not match directory name '{Path(spec_dir).name}'"
            )
        for key, filename in (
            ("solution", SOLUTION_FILENAME),
            ("ground_truth", GROUND_TRUTH_FILENAME),
            ("edge_case", EDGE_CASE_FILENAME),
        ):
            if not (Path(spec_dir) / filename).exists():
                problems.append(f"{where}: missing {filename}")
    return problems


def find_duplicate_ids(specs: Sequence[Spec]) -> List[str]:
    """Return ids that appear more than once, in first-seen order."""
    seen: Dict[str, int] = {}
    for spec in specs:
        seen[spec.id] = seen.get(spec.id, 0) + 1
    return [spec_id for spec_id, count in seen.items() if count > 1]


def validate_corpus(specs: Sequence[Spec]) -> List[str]:
    """Validate a loaded corpus as a whole."""
    problems: List[str] = []
    for spec in specs:
        spec_dir = Path(spec.path) if spec.path else None
        problems.extend(validate_spec(spec, spec_dir))
    for spec_id in find_duplicate_ids(specs):
        problems.append(f"duplicate spec id '{spec_id}'")
    return problems


def load_corpus(
    root: Optional[Path] = None,
    ids: Optional[Iterable[str]] = None,
    tiers: Optional[Iterable[str]] = None,
) -> List[Spec]:
    """Load and filter the corpus.

    ``ids`` and ``tiers`` are optional selectors; ``None`` means "all".
    Raises ``ValueError`` if a requested id or tier selects nothing.
    """
    root = Path(root) if root is not None else default_corpus_root()
    if not root.is_dir():
        raise ValueError(f"corpus root not found: {root}")

    wanted_ids = set(ids) if ids is not None else None
    wanted_tiers = set(tiers) if tiers is not None else None

    specs: List[Spec] = []
    for spec_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        if not (spec_dir / SPEC_FILENAME).exists():
            continue
        spec = load_spec(spec_dir)
        if wanted_ids is not None and spec.id not in wanted_ids:
            continue
        if wanted_tiers is not None and spec.tier not in wanted_tiers:
            continue
        specs.append(spec)

    if wanted_ids is not None:
        found = {s.id for s in specs}
        missing = sorted(wanted_ids - found)
        if missing:
            raise ValueError(f"unknown spec id(s): {', '.join(missing)}")

    if not specs:
        raise ValueError("no specs selected")

    return specs


def tier_counts(specs: Sequence[Spec]) -> Dict[str, int]:
    counts = {tier: 0 for tier in TIERS}
    for spec in specs:
        counts[spec.tier] = counts.get(spec.tier, 0) + 1
    return counts


def render_prompt(spec: Spec, include_contract: bool = True) -> str:
    """Render the model-facing prompt.

    Only the requirement plus the deliverable contract is included. Reference
    solutions, test source, and test names are never part of a prompt.
    """
    parts = [spec.prompt.strip()]
    if include_contract:
        symbols = ", ".join(spec.required_symbols)
        parts.append(
            "\nProvide a complete Python module that defines: "
            f"{symbols}. Standard library only. Do not include tests."
        )
    return "\n".join(parts)


def load_suite_source(spec: Spec, suite: str) -> str:
    """Read a suite's source from disk (used by the execution layer)."""
    if not spec.path:
        raise ValueError(f"spec '{spec.id}' has no path")
    paths = spec_file_paths(Path(spec.path))
    if suite == "ground_truth":
        target = paths["ground_truth"]
    elif suite == "edge_case":
        target = paths["edge_case"]
    else:
        raise ValueError(f"unknown suite '{suite}'")
    return target.read_text(encoding="utf-8")


def solution_source(spec: Spec) -> str:
    """Read the reference solution for a spec."""
    if not spec.path:
        raise ValueError(f"spec '{spec.id}' has no path")
    return spec_file_paths(Path(spec.path))["solution"].read_text(encoding="utf-8")


def suite_filename(suite: str) -> str:
    if suite == "ground_truth":
        return GROUND_TRUTH_FILENAME
    if suite == "edge_case":
        return EDGE_CASE_FILENAME
    raise ValueError(f"unknown suite '{suite}'")


def summarise_corpus(specs: Sequence[Spec]) -> List[Dict[str, Any]]:
    """Plain-data view of the corpus for ``list-specs``."""
    return [
        {
            "id": spec.id,
            "title": spec.title,
            "tier": spec.tier,
            "tags": list(spec.tags),
            "required_symbols": list(spec.required_symbols),
        }
        for spec in specs
    ]


def check_spec_soundness(
    spec: Spec,
    timeout_s: Optional[float] = None,
    python_executable: Optional[str] = None,
) -> List[str]:
    """Run a spec's reference against both suites.

    Returns a list of problem descriptions; an empty list means the spec is
    sound. The execution layer is imported lazily so that loading the corpus
    never pulls in subprocess machinery.
    """
    from . import execution

    if timeout_s is None:
        timeout_s = execution.DEFAULT_TIMEOUT_S

    problems: List[str] = []
    reference = solution_source(spec)
    for suite in SUITES:
        evidence = execution.run_suite(
            spec,
            reference,
            suite,
            timeout_s=timeout_s,
            python_executable=python_executable,
        )
        for problem in execution.problems_for(evidence):
            problems.append(f"{spec.id}/{suite}: {problem}")
    return problems


def validate_soundness(
    specs: Sequence[Spec],
    timeout_s: Optional[float] = None,
    python_executable: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Self-validate the whole corpus against its reference solutions.

    Returns one row per (spec, suite) with ``ok`` and any ``problems``, so the
    CLI can print per-spec detail rather than a single pass/fail.
    """
    from . import execution

    if timeout_s is None:
        timeout_s = execution.DEFAULT_TIMEOUT_S

    rows: List[Dict[str, Any]] = []
    for spec in specs:
        reference = solution_source(spec)
        for suite in SUITES:
            evidence = execution.run_suite(
                spec,
                reference,
                suite,
                timeout_s=timeout_s,
                python_executable=python_executable,
            )
            problems = execution.problems_for(evidence)
            rows.append(
                {
                    "spec_id": spec.id,
                    "suite": suite,
                    "ok": not problems,
                    "total": evidence.total,
                    "passed": len(evidence.passed),
                    "problems": problems,
                }
            )
    return rows
