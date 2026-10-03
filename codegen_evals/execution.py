"""Isolated execution of candidate code against spec suites.

Each candidate is written to a fresh temporary directory as ``solution.py``
alongside the suite under test, then run in a separate interpreter under a
wall-clock timeout. Results are read back from pytest's built-in JUnit XML
output so no extra dependency is needed.

This is *not* an adversarial sandbox. See ``docs/execution.md``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from .corpus import EDGE_CASE_FILENAME, GROUND_TRUTH_FILENAME, SOLUTION_FILENAME
from .models import SUITES, ExecutionEvidence

DEFAULT_TIMEOUT_S = 60.0
MESSAGE_LIMIT = 500
STDERR_LIMIT = 2000

SUITE_FILENAMES = {
    "ground_truth": GROUND_TRUTH_FILENAME,
    "edge_case": EDGE_CASE_FILENAME,
}


def _test_id(testcase: ET.Element) -> str:
    classname = testcase.get("classname") or ""
    name = testcase.get("name") or "unknown"
    return f"{classname}::{name}" if classname else name


def parse_junit_xml(xml_text: str, suite: str) -> ExecutionEvidence:
    """Turn a JUnit XML document into structured per-test evidence."""
    evidence = ExecutionEvidence(suite=suite)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as error:
        evidence.setup_error = f"unparseable JUnit XML: {error}"
        return evidence

    testcases = root.iter("testcase")
    for testcase in testcases:
        evidence.total += 1
        test_id = _test_id(testcase)
        failure = testcase.find("failure")
        error = testcase.find("error")
        skipped = testcase.find("skipped")
        if failure is not None or error is not None:
            node = failure if failure is not None else error
            message = (node.get("message") or "").strip()
            body = (node.text or "").strip()
            evidence.failed.append(test_id)
            evidence.messages[test_id] = (message or body)[:MESSAGE_LIMIT]
        elif skipped is not None:
            evidence.failed.append(test_id)
            evidence.messages[test_id] = "skipped"
        else:
            evidence.passed.append(test_id)
    return evidence


def run_suite(
    spec,
    candidate_code: str,
    suite: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    python_executable: Optional[str] = None,
) -> ExecutionEvidence:
    """Run one suite against one candidate in a temporary directory."""
    if suite not in SUITES:
        raise ValueError(f"unknown suite '{suite}': expected one of {', '.join(SUITES)}")
    if not spec.path:
        raise ValueError(f"spec '{spec.id}' has no path")

    python = python_executable or sys.executable
    spec_dir = Path(spec.path)
    suite_path = spec_dir / SUITE_FILENAMES[suite]
    evidence = ExecutionEvidence(suite=suite)

    if not suite_path.exists():
        evidence.setup_error = f"missing suite file: {suite_path.name}"
        return evidence

    workdir = Path(tempfile.mkdtemp(prefix=f"codegen-eval-{spec.id}-"))
    started = time.monotonic()
    try:
        (workdir / SOLUTION_FILENAME).write_text(candidate_code, encoding="utf-8")
        shutil.copy(suite_path, workdir / SUITE_FILENAMES[suite])
        report_path = workdir / "report.xml"

        command = [
            python,
            "-m",
            "pytest",
            SUITE_FILENAMES[suite],
            f"--junitxml={report_path}",
            "-p",
            "no:cacheprovider",
            "-q",
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            evidence.returncode = completed.returncode
            evidence.stderr_tail = (completed.stderr or "")[-STDERR_LIMIT:]
        except subprocess.TimeoutExpired:
            evidence.timed_out = True
            evidence.setup_error = f"timed out after {timeout_s:g}s"
            evidence.duration_s = time.monotonic() - started
            return evidence

        if report_path.exists():
            parsed = parse_junit_xml(report_path.read_text(encoding="utf-8"), suite)
            evidence.total = parsed.total
            evidence.passed = parsed.passed
            evidence.failed = parsed.failed
            evidence.messages = parsed.messages
            evidence.setup_error = parsed.setup_error
        else:
            evidence.setup_error = "no JUnit report produced (collection or import error)"

        evidence.duration_s = time.monotonic() - started
        return evidence
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def run_spec(
    spec,
    candidate_code: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    python_executable: Optional[str] = None,
):
    """Run both suites against one candidate and return them separately."""
    ground_truth = run_suite(
        spec, candidate_code, "ground_truth", timeout_s=timeout_s, python_executable=python_executable
    )
    edge_case = run_suite(
        spec, candidate_code, "edge_case", timeout_s=timeout_s, python_executable=python_executable
    )
    return ground_truth, edge_case


def problems_for(evidence: ExecutionEvidence) -> List[str]:
    """Human-readable reasons a suite run is not a clean pass."""
    problems: List[str] = []
    if evidence.timed_out:
        problems.append("timed out")
    if evidence.setup_error:
        problems.append(evidence.setup_error)
    if evidence.total == 0 and not evidence.setup_error:
        problems.append("no tests collected")
    for test_id in evidence.failed:
        problems.append(f"{test_id}: {evidence.messages.get(test_id, 'failed')}")
    return problems
