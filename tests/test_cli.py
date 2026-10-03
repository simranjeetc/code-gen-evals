"""Tests for the command-line surface and exit codes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from codegen_evals import cli, config, pipeline
from codegen_evals.models import DimensionScores, EvalResult, RunMetadata, RunResults

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_help_lists_all_four_commands(capsys):
    exit_code = cli.main([])
    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_USAGE
    for command in ("list-specs", "validate", "run", "report"):
        assert command in output


def test_run_help_lists_the_documented_options(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["run", "--help"])
    assert caught.value.code == 0
    output = capsys.readouterr().out
    for option in ("--specs", "--tiers", "--models", "--provider", "--weights", "--out", "--json"):
        assert option in output


def test_list_specs_prints_all_specs_with_tier_and_tags(capsys):
    exit_code = cli.main(["list-specs"])
    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_OK
    assert "20 specs" in output
    assert "easy=5" in output
    assert "medium=5" in output
    assert "hard=10" in output
    assert "fizzbuzz" in output
    assert "concurrency" in output


def test_list_specs_json(capsys):
    exit_code = cli.main(["list-specs", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == cli.EXIT_OK
    assert len(payload) == 20
    assert all({"id", "tier", "tags"} <= set(row) for row in payload)


def test_list_specs_respects_tier_filter(capsys):
    exit_code = cli.main(["list-specs", "--tiers", "hard", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == cli.EXIT_OK
    assert len(payload) == 10
    assert all(row["tier"] == "hard" for row in payload)


def test_list_specs_respects_spec_filter(capsys):
    exit_code = cli.main(["list-specs", "--specs", "fizzbuzz,word_freq", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == cli.EXIT_OK
    assert {row["id"] for row in payload} == {"fizzbuzz", "word_freq"}


def test_unknown_spec_id_is_a_usage_error(capsys):
    exit_code = cli.main(["list-specs", "--specs", "nope"])
    assert exit_code == cli.EXIT_USAGE
    assert "unknown spec id" in capsys.readouterr().err


def test_validate_passes_on_a_subset(capsys):
    exit_code = cli.main(["validate", "--specs", "fizzbuzz,json_diff"])
    output = capsys.readouterr().out
    assert exit_code == cli.EXIT_OK
    assert "all sound" in output


def test_validate_fails_when_a_reference_is_broken(tmp_path, capsys):
    spec_dir = tmp_path / "corpus" / "broken"
    spec_dir.mkdir(parents=True)
    (spec_dir / "spec.json").write_text(
        json.dumps(
            {
                "id": "broken",
                "tier": "easy",
                "tags": ["testing"],
                "prompt": "return 1",
                "required_symbols": ["f"],
            }
        )
    )
    (spec_dir / "solution.py").write_text("def f():\n    return 2\n")
    (spec_dir / "test_ground_truth.py").write_text(
        "from solution import f\n\n\ndef test_f():\n    assert f() == 1\n"
    )
    (spec_dir / "test_edge_cases.py").write_text(
        "from solution import f\n\n\ndef test_f_edge():\n    assert f() == 1\n"
    )

    exit_code = cli.main(["validate", "--corpus", str(tmp_path / "corpus")])
    assert exit_code == cli.EXIT_PROBLEM
    assert "corpus validation failed" in capsys.readouterr().err


def test_run_mock_writes_results_and_report(tmp_path, capsys):
    results = tmp_path / "results.json"
    exit_code = cli.main(
        [
            "run",
            "--provider",
            "mock",
            "--specs",
            "fizzbuzz,json_diff",
            "--models",
            "mock-strong,mock-weak",
            "--out",
            str(results),
            "--quiet",
        ]
    )
    assert exit_code == cli.EXIT_OK
    assert results.exists()
    payload = json.loads(results.read_text())
    assert payload["schema_version"] == 1
    assert len(payload["results"]) == 4  # 2 models x 2 specs
    assert payload["metadata"]["provider"] == "mock"
    assert payload["metadata"]["mock"] is True
    assert {result["model_id"] for result in payload["results"]} == {"mock-strong", "mock-weak"}
    assert results.with_suffix(".md").exists()


def test_run_emits_json_summary(tmp_path, capsys):
    exit_code = cli.main(
        [
            "run",
            "--provider",
            "mock",
            "--specs",
            "fizzbuzz,json_diff,rate_limiter",
            "--models",
            "mock-strong,mock-weak",
            "--out",
            str(tmp_path / "results.json"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == cli.EXIT_OK
    assert set(payload["composites"]) == {"mock-strong", "mock-weak"}
    assert payload["inconclusive"] is False


def test_run_rejects_invalid_provider(capsys):
    with pytest.raises(SystemExit) as caught:
        cli.main(["run", "--provider", "not-a-provider"])
    assert caught.value.code == cli.EXIT_USAGE


def test_run_rejects_unknown_weight_key(tmp_path, capsys):
    exit_code = cli.main(
        [
            "run",
            "--provider",
            "mock",
            "--specs",
            "fizzbuzz",
            "--weights",
            "nonsense=1",
            "--out",
            str(tmp_path / "results.json"),
        ]
    )
    assert exit_code == cli.EXIT_USAGE
    assert "unknown dimension" in capsys.readouterr().err


def test_inconclusive_run_exits_non_zero_but_still_writes_results(tmp_path, monkeypatch, capsys):
    uniform = [
        EvalResult(
            model_id=model,
            provider="mock",
            spec_id="fizzbuzz",
            tier="easy",
            tags=["algorithms"],
            scores=DimensionScores(1.0, 1.0, 1.0, 1.0),
        )
        for model in ("mock-strong", "mock-weak")
    ]
    fake_run = RunResults(
        metadata=RunMetadata(
            provider="mock",
            models=["mock-strong", "mock-weak"],
            weights=dict(config.DEFAULT_WEIGHTS),
            thresholds=dict(config.DEFAULT_THRESHOLDS),
            mock=True,
            inconclusive=True,
            inconclusive_reason="every model scored perfectly",
        ),
        results=uniform,
    )
    monkeypatch.setattr(pipeline, "run_evaluation", lambda **kwargs: fake_run)

    results = tmp_path / "results.json"
    exit_code = cli.main(
        ["run", "--provider", "mock", "--specs", "fizzbuzz", "--out", str(results), "--quiet"]
    )
    assert exit_code == cli.EXIT_PROBLEM
    assert results.exists()
    assert "INCONCLUSIVE" in capsys.readouterr().err


def test_run_rejects_judge_that_is_also_a_subject(tmp_path, capsys):
    exit_code = cli.main(
        [
            "run",
            "--provider",
            "mock",
            "--specs",
            "fizzbuzz",
            "--models",
            "mock-strong",
            "--judge",
            "mock-strong",
            "--out",
            str(tmp_path / "results.json"),
        ]
    )
    assert exit_code == cli.EXIT_USAGE
    assert "must be a" in capsys.readouterr().err


def test_report_command_renders_from_results(tmp_path, capsys):
    results = tmp_path / "results.json"
    cli.main(
        [
            "run",
            "--provider",
            "mock",
            "--specs",
            "fizzbuzz",
            "--models",
            "mock-strong,mock-weak",
            "--out",
            str(results),
            "--quiet",
        ]
    )
    out = tmp_path / "report.md"
    exit_code = cli.main(["report", "--in", str(results), "--out", str(out)])
    assert exit_code == cli.EXIT_OK
    assert "Code-generation model evaluation" in out.read_text()


def test_report_command_missing_input_is_a_problem(tmp_path, capsys):
    exit_code = cli.main(["report", "--in", str(tmp_path / "nope.json"), "--out", str(tmp_path / "r.md")])
    assert exit_code == cli.EXIT_PROBLEM
    assert "not found" in capsys.readouterr().err


def test_report_can_override_weights(tmp_path):
    results = tmp_path / "results.json"
    cli.main(
        [
            "run",
            "--provider",
            "mock",
            "--specs",
            "fizzbuzz",
            "--models",
            "mock-strong,mock-weak",
            "--out",
            str(results),
            "--quiet",
        ]
    )
    out = tmp_path / "report.md"
    exit_code = cli.main(
        ["report", "--in", str(results), "--out", str(out), "--weights", "style=1.0,execution=0"]
    )
    assert exit_code == cli.EXIT_OK
    assert "style" in out.read_text()


def test_makefile_targets_exist():
    makefile = (REPO_ROOT / "Makefile").read_text()
    for target in ("install", "validate", "run-mock", "report", "test", "quickstart"):
        assert f"{target}:" in makefile
