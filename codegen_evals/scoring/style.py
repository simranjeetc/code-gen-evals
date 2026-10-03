"""Deterministic static style scoring.

Every check is computed from the candidate source with ``ast`` and ``tokenize``
from the standard library, so the same source always produces the same score on
any machine. ``ruff`` is optional and opt-in: auto-enabling it would make scores
depend on what happens to be installed.

The score is a weighted average of independent checks, each in [0, 1]. Per-check
outcomes are returned so a low style score can be explained rather than asserted.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Tuple

CORE_WEIGHTS: Dict[str, float] = {
    "parseable": 0.10,
    "annotations": 0.25,
    "docstrings": 0.15,
    "naming": 0.15,
    "line_length": 0.15,
    "complexity": 0.10,
    "bare_except": 0.10,
}

MAX_LINE_LENGTH = 100
MAX_COMPLEXITY = 10
RUFF_BLEND = 0.2


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _functions(tree: ast.AST) -> List[ast.AST]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def _annotated(node: ast.AST) -> bool:
    arguments = node.args
    named = list(arguments.args) + list(arguments.kwonlyargs) + list(arguments.posonlyargs)
    if any(arg.annotation is None for arg in named):
        return False
    if arguments.vararg is not None and arguments.vararg.annotation is None:
        return False
    if arguments.kwarg is not None and arguments.kwarg.annotation is None:
        return False
    return node.returns is not None


def _complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler)):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(0, len(child.values) - 1)
        elif isinstance(child, ast.IfExp):
            score += 1
        elif isinstance(child, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            score += sum(len(generator.ifs) for generator in child.generators)
    return score


def _ratio(passed: int, total: int) -> float:
    return 1.0 if total <= 0 else passed / float(total)


def _bare_except(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            return True
    return False


def run_ruff(source: str, timeout_s: float = 30.0) -> Optional[Dict[str, Any]]:
    """Return a ruff summary, or ``None`` when ruff is unavailable or fails."""
    executable = shutil.which("ruff")
    if not executable:
        return None
    try:
        completed = subprocess.run(
            [executable, "check", "--output-format=json", "--stdin-filename", "solution.py", "-"],
            input=source,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        findings = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        return None
    rules = sorted({finding.get("code", "?") for finding in findings})
    return {"findings": len(findings), "rules": rules}


def analyze_style(
    source: Optional[str],
    use_ruff: bool = False,
    ruff_runner=run_ruff,
) -> Tuple[float, Dict[str, Any]]:
    """Score ``source`` for style.

    Returns ``(score, details)`` where ``details["checks"]`` maps each check name
    to its 0-1 outcome and ``details["notes"]`` lists human-readable reasons.
    """
    details: Dict[str, Any] = {"checks": {}, "notes": [], "ruff": None}

    if not source or not source.strip():
        details["checks"] = {name: 0.0 for name in CORE_WEIGHTS}
        details["notes"].append("no code to score")
        return 0.0, details

    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        details["checks"] = {name: 0.0 for name in CORE_WEIGHTS}
        details["notes"].append(f"source does not parse: {error}")
        return 0.0, details

    checks: Dict[str, float] = {}
    notes: List[str] = []

    checks["parseable"] = 1.0
    details["checks"]["parseable"] = 1.0

    functions = _functions(tree)
    public = [node for node in functions if _is_public(node.name)]

    if not public:
        checks["annotations"] = 1.0
        checks["docstrings"] = 1.0
        notes.append("no public functions to check for annotations or docstrings")
    else:
        annotated = sum(1 for node in public if _annotated(node))
        checks["annotations"] = _ratio(annotated, len(public))
        if checks["annotations"] < 1.0:
            notes.append(
                f"{len(public) - annotated}/{len(public)} public functions are not fully annotated"
            )

        documented = sum(1 for node in public if ast.get_docstring(node))
        checks["docstrings"] = _ratio(documented, len(public))
        if checks["docstrings"] < 1.0:
            notes.append(
                f"{len(public) - documented}/{len(public)} public functions have no docstring"
            )

    snake = sum(1 for node in public if node.name == node.name.lower())
    checks["naming"] = _ratio(snake, len(public)) if public else 1.0
    if public and checks["naming"] < 1.0:
        notes.append("some public function names are not snake_case")

    lines = source.splitlines()
    long_lines = [index for index, line in enumerate(lines, 1) if len(line) > MAX_LINE_LENGTH]
    checks["line_length"] = _ratio(len(lines) - len(long_lines), len(lines))
    if long_lines:
        notes.append(f"{len(long_lines)} line(s) exceed {MAX_LINE_LENGTH} characters")

    if not functions:
        checks["complexity"] = 1.0
    else:
        worst = max(functions, key=_complexity)
        worst_value = _complexity(worst)
        details["max_complexity"] = worst_value
        checks["complexity"] = 1.0 if worst_value <= MAX_COMPLEXITY else MAX_COMPLEXITY / worst_value
        if worst_value > MAX_COMPLEXITY:
            notes.append(f"{worst.name} has cyclomatic complexity {worst_value}")

    if _bare_except(tree):
        checks["bare_except"] = 0.0
        notes.append("contains a bare 'except:'")
    else:
        checks["bare_except"] = 1.0

    details["checks"] = checks
    details["notes"] = notes

    core = sum(CORE_WEIGHTS[name] * checks[name] for name in CORE_WEIGHTS)

    if use_ruff:
        summary = ruff_runner(source)
        details["ruff"] = summary
        if summary is None:
            notes.append("ruff requested but unavailable; core score used")
        else:
            ruff_score = 1.0 if summary["findings"] == 0 else 0.0
            details["checks"]["ruff"] = ruff_score
            core = (1.0 - RUFF_BLEND) * core + RUFF_BLEND * ruff_score
            if summary["findings"]:
                notes.append(f"ruff reported {summary['findings']} finding(s): {summary['rules']}")

    return max(0.0, min(1.0, core)), details
