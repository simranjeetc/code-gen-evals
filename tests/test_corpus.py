"""Tests for corpus loading, validation, and prompt isolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codegen_evals import corpus
from codegen_evals.models import TIERS, Spec

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "corpus"


def _write_spec_dir(root: Path, name: str, payload: dict, with_suites: bool = True) -> Path:
    spec_dir = root / name
    spec_dir.mkdir(parents=True, exist_ok=True)
    (spec_dir / corpus.SPEC_FILENAME).write_text(json.dumps(payload), encoding="utf-8")
    (spec_dir / corpus.SOLUTION_FILENAME).write_text("def f():\n    return 1\n", encoding="utf-8")
    if with_suites:
        (spec_dir / corpus.GROUND_TRUTH_FILENAME).write_text(
            "from solution import f\n\n\ndef test_ok():\n    assert f() == 1\n", encoding="utf-8"
        )
        (spec_dir / corpus.EDGE_CASE_FILENAME).write_text(
            "from solution import f\n\n\ndef test_edge():\n    assert f() == 1\n", encoding="utf-8"
        )
    return spec_dir


# --- 2.1 spec format and validation -----------------------------------------


def test_shipped_corpus_loads():
    specs = corpus.load_corpus(CORPUS_ROOT)
    assert len(specs) >= 20


def test_shipped_corpus_is_valid():
    specs = corpus.load_corpus(CORPUS_ROOT)
    assert corpus.validate_corpus(specs) == []


def test_missing_required_field_is_reported(tmp_path):
    spec_dir = _write_spec_dir(tmp_path, "incomplete", {"id": "incomplete", "tier": "easy"})
    spec = corpus.load_spec(spec_dir)
    problems = corpus.validate_spec(spec, spec_dir)
    assert any("prompt" in problem for problem in problems)
    assert any("tags" in problem for problem in problems)


def test_invalid_tier_is_reported(tmp_path):
    spec_dir = _write_spec_dir(
        tmp_path,
        "badtier",
        {
            "id": "badtier",
            "tier": "impossible",
            "tags": ["x"],
            "prompt": "do a thing",
            "required_symbols": ["f"],
        },
    )
    spec = corpus.load_spec(spec_dir)
    problems = corpus.validate_spec(spec, spec_dir)
    assert any("invalid tier" in problem for problem in problems)


def test_id_must_match_directory_name(tmp_path):
    spec_dir = _write_spec_dir(
        tmp_path,
        "dirname",
        {
            "id": "othername",
            "tier": "easy",
            "tags": ["x"],
            "prompt": "do a thing",
            "required_symbols": ["f"],
        },
    )
    spec = corpus.load_spec(spec_dir)
    problems = corpus.validate_spec(spec, spec_dir)
    assert any("does not match directory name" in problem for problem in problems)


def test_missing_suite_files_are_reported(tmp_path):
    spec_dir = _write_spec_dir(
        tmp_path,
        "nosuites",
        {
            "id": "nosuites",
            "tier": "easy",
            "tags": ["x"],
            "prompt": "do a thing",
            "required_symbols": ["f"],
        },
        with_suites=False,
    )
    spec = corpus.load_spec(spec_dir)
    problems = corpus.validate_spec(spec, spec_dir)
    assert any("test_ground_truth.py" in problem for problem in problems)
    assert any("test_edge_cases.py" in problem for problem in problems)


def test_duplicate_ids_are_detected():
    specs = [Spec(id="same"), Spec(id="other"), Spec(id="same")]
    assert corpus.find_duplicate_ids(specs) == ["same"]
    problems = corpus.validate_corpus(specs)
    assert any("duplicate spec id" in problem for problem in problems)


def test_load_corpus_rejects_unknown_id():
    with pytest.raises(ValueError):
        corpus.load_corpus(CORPUS_ROOT, ids=["does-not-exist"])


def test_load_corpus_filters_by_tier():
    specs = corpus.load_corpus(CORPUS_ROOT, tiers=["hard"])
    assert specs
    assert all(spec.tier == "hard" for spec in specs)


def test_load_corpus_rejects_missing_root(tmp_path):
    with pytest.raises(ValueError):
        corpus.load_corpus(tmp_path / "nope")


# --- 2.5 tiers, tags, and listing -------------------------------------------


def test_minimum_twenty_specs_with_tier_balance():
    specs = corpus.load_corpus(CORPUS_ROOT)
    counts = corpus.tier_counts(specs)
    assert len(specs) >= 20
    assert counts["easy"] >= 5, counts
    assert counts["medium"] >= 5, counts
    assert counts["hard"] >= 10, counts


def test_every_spec_has_a_valid_tier_and_tags():
    for spec in corpus.load_corpus(CORPUS_ROOT):
        assert spec.tier in TIERS, spec.id
        assert spec.tags, spec.id
        assert all(isinstance(tag, str) and tag for tag in spec.tags), spec.id


def test_every_spec_declares_required_symbols_and_entrypoint():
    for spec in corpus.load_corpus(CORPUS_ROOT):
        assert spec.required_symbols, spec.id
        assert spec.entrypoint == "solution", spec.id


def test_summarise_corpus_lists_all_specs_with_tier_and_tags():
    specs = corpus.load_corpus(CORPUS_ROOT)
    summary = corpus.summarise_corpus(specs)
    assert len(summary) == len(specs)
    for entry in summary:
        assert entry["tier"] in TIERS
        assert entry["tags"]
        assert entry["id"]


def test_task_type_tags_are_varied_across_the_corpus():
    specs = corpus.load_corpus(CORPUS_ROOT)
    all_tags = {tag for spec in specs for tag in spec.tags}
    assert len(all_tags) >= 8


# --- 2.7 prompt isolation ---------------------------------------------------


def test_prompts_contain_no_test_code():
    for spec in corpus.load_corpus(CORPUS_ROOT):
        prompt = corpus.render_prompt(spec)
        assert "def test" not in prompt, spec.id
        assert "assert " not in prompt, spec.id
        assert "import " not in prompt, spec.id
        assert "pytest" not in prompt, spec.id


def test_prompts_contain_no_reference_solution_lines():
    for spec in corpus.load_corpus(CORPUS_ROOT):
        prompt = corpus.render_prompt(spec)
        for line in corpus.solution_source(spec).splitlines():
            stripped = line.strip()
            if len(stripped) < 15 or stripped.startswith(("#", "import", "from")):
                continue
            assert stripped not in prompt, (spec.id, stripped)


def test_prompts_contain_no_edge_case_test_names():
    for spec in corpus.load_corpus(CORPUS_ROOT):
        prompt = corpus.render_prompt(spec)
        assert "test_" not in prompt, spec.id


def test_prompt_includes_required_symbols():
    for spec in corpus.load_corpus(CORPUS_ROOT):
        prompt = corpus.render_prompt(spec)
        for symbol in spec.required_symbols:
            assert symbol in prompt, (spec.id, symbol)


def test_render_prompt_without_contract_is_just_the_requirement():
    spec = Spec(id="x", tier="easy", tags=["t"], prompt="Do the thing.", required_symbols=["f"])
    assert corpus.render_prompt(spec, include_contract=False) == "Do the thing."


# --- 2.1 / 2.2 suite overlap and edge-suite strength -------------------------


def _test_ids(source: str):
    import ast

    return {
        node.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test")
    }


def test_no_suite_test_id_appears_in_both_suites():
    offenders = []
    for spec in corpus.load_corpus(CORPUS_ROOT):
        ground_truth = _test_ids(corpus.load_suite_source(spec, "ground_truth"))
        edge = _test_ids(corpus.load_suite_source(spec, "edge_case"))
        overlap = ground_truth & edge
        if overlap:
            offenders.append((spec.id, sorted(overlap)))
    assert offenders == [], offenders


def test_edge_suites_are_substantial():
    """An edge suite that is thinner than the visible one is not a real filter."""
    for spec in corpus.load_corpus(CORPUS_ROOT):
        ground_truth = _test_ids(corpus.load_suite_source(spec, "ground_truth"))
        edge = _test_ids(corpus.load_suite_source(spec, "edge_case"))
        assert len(edge) >= len(ground_truth), (spec.id, len(edge), len(ground_truth))
        assert len(edge) >= 6, (spec.id, len(edge))


def test_new_hard_specs_exist():
    specs = {spec.id: spec for spec in corpus.load_corpus(CORPUS_ROOT)}
    for spec_id in (
        "template_renderer",
        "bounded_queue",
        "money_total",
        "batch_processor",
        "state_machine",
    ):
        assert spec_id in specs, spec_id
        assert specs[spec_id].tier == "hard", spec_id
