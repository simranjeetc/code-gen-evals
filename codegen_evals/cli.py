"""Command-line entrypoints for the eval framework."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from . import config, corpus, pipeline, providers, reporting
from .models import TIERS
from .scoring import judge_agreement

EXIT_OK = 0
EXIT_PROBLEM = 1
EXIT_USAGE = 2


def _split(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _load_specs(args) -> List:
    return corpus.load_corpus(
        root=Path(args.corpus) if getattr(args, "corpus", None) else None,
        ids=_split(getattr(args, "specs", None)),
        tiers=_split(getattr(args, "tiers", None)),
    )


def _emit(payload, as_json: bool, text: str) -> None:
    print(json.dumps(payload, indent=2) if as_json else text)


def cmd_list_specs(args) -> int:
    specs = _load_specs(args)
    rows = corpus.summarise_corpus(specs)
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK

    print(f"{len(specs)} specs")
    for row in rows:
        tags = ", ".join(row["tags"])
        title = row["title"] or row["id"]
        print(f"  {row['tier']:<7} {row['id']:<22} {title:<34} [{tags}]")
    counts = corpus.tier_counts(specs)
    summary = "  ".join(f"{tier}={counts[tier]}" for tier in TIERS)
    print(f"tiers: {summary}")
    return EXIT_OK


def cmd_validate(args) -> int:
    specs = _load_specs(args)
    problems = corpus.validate_corpus(specs)
    rows = corpus.validate_soundness(specs)

    if args.json:
        print(json.dumps({"problems": problems, "soundness": rows}, indent=2))
    else:
        for row in rows:
            status = "ok" if row["ok"] else "FAIL"
            print(
                f"  {status:<4} {row['spec_id']:<22} {row['suite']:<12} "
                f"{row['passed']}/{row['total']}"
            )
            for problem in row["problems"]:
                print(f"       - {problem}")
        for problem in problems:
            print(f"  invalid {problem}")

    unsound = [row for row in rows if not row["ok"]]
    if problems or unsound:
        print(
            f"corpus validation failed: {len(problems)} structural, {len(unsound)} unsound",
            file=sys.stderr,
        )
        return EXIT_PROBLEM
    print(f"corpus valid: {len(specs)} specs, {len(rows)} suite runs, all sound")
    return EXIT_OK


def cmd_run(args) -> int:
    specs = _load_specs(args)
    models = _split(args.models) or providers.default_models(args.provider)

    weights = config.parse_weights(args.weights) if args.weights else None

    control_model = getattr(args, "control_model", None)
    if control_model and control_model not in models:
        models = list(models) + [control_model]

    agreement = None
    if args.judge_agreement:
        agreement_path = Path(args.judge_agreement)
        if not agreement_path.exists():
            print(f"judge agreement file not found: {agreement_path}", file=sys.stderr)
            return EXIT_USAGE
        try:
            agreement = json.loads(agreement_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            print(f"judge agreement file is not JSON: {error}", file=sys.stderr)
            return EXIT_USAGE

    run = pipeline.run_evaluation(
        specs=specs,
        models=models,
        provider_name=args.provider,
        judge_model=args.judge,
        weights=weights,
        temperature=args.temperature,
        concurrency=args.concurrency,
        timeout_s=args.timeout,
        suite_timeout_s=args.suite_timeout,
        use_ruff=args.ruff,
        exclusion_rate_threshold=args.exclusion_threshold,
        judge_agreement=agreement,
        repeat_count=args.repeats,
        control_model=control_model,
        progress=None if args.quiet else (lambda message: print(message, file=sys.stderr)),
        verbose=args.verbose and not args.quiet,
    )

    out = Path(args.out)
    reporting.save_results(run, out)
    reporting.write_report(run, Path(args.report_out) if args.report_out else out.with_suffix(".md"))

    aggregates = reporting.aggregate.aggregate(run.results, run.metadata.weights)["by_model"]
    summary = {
        "results_file": str(out),
        "provider": run.metadata.provider,
        "models": run.metadata.models,
        "judge_model": run.metadata.judge_model,
        "repeats": run.metadata.repeat_count,
        "control_model": run.metadata.control_model,
        "evaluations": len(run.results),
        "duration_s": round(run.metadata.duration_s, 2),
        "inconclusive": run.metadata.inconclusive,
        "inconclusive_reason": run.metadata.inconclusive_reason,
        "unreliable": run.metadata.unreliable,
        "unreliable_reason": run.metadata.unreliable_reason,
        "unreliable_models": run.metadata.unreliable_models,
        "unstable": run.metadata.unstable,
        "unstable_reason": run.metadata.unstable_reason,
        "unstable_models": run.metadata.unstable_models,
        "control_separated": run.metadata.control_separated,
        "control_reason": run.metadata.control_reason,
        "composites": {
            model_id: _round(stats["composite"])
            for model_id, stats in aggregates.items()
        },
        "stability": {
            model_id: {
                "mean": _round((stats.get("stability") or {}).get("mean")),
                "sd": _round((stats.get("stability") or {}).get("sd")),
                "spec_sd": _round((stats.get("stability") or {}).get("spec_sd")),
                "range": _round((stats.get("stability") or {}).get("range")),
                "pairs_measured": (stats.get("stability") or {}).get("pairs_measured", 0),
                "measured": (stats.get("stability") or {}).get("measured", False),
            }
            for model_id, stats in aggregates.items()
        },
        "excluded": {
            model_id: stats.get("excluded", 0) for model_id, stats in aggregates.items()
        },
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"results written to {out}")
        for model_id, composite in summary["composites"].items():
            marker = ""
            if run.metadata.inconclusive:
                marker = " (inconclusive)"
            elif model_id in run.metadata.unreliable_models:
                marker = " (unreliable)"
            elif model_id in run.metadata.unstable_models:
                marker = " (unstable)"
            if model_id == run.metadata.control_model:
                marker += " [control]"
            stability = summary["stability"].get(model_id, {})
            if stability.get("measured"):
                spread_text = (
                    f" sd={stability['sd']:.3f} maxspec_sd={stability['spec_sd']:.3f}"
                )
            else:
                spread_text = " sd=not measured"
            excluded = summary["excluded"].get(model_id, 0)
            tail = f" excluded={excluded}" if excluded else ""
            print(f"  {model_id:<42} composite={composite}{spread_text}{tail}{marker}")
        print(f"repeats: {run.metadata.repeat_count}")
        if run.metadata.control_reason:
            print(f"CONTROL: {run.metadata.control_reason}")
        if run.metadata.inconclusive:
            print(f"INCONCLUSIVE: {run.metadata.inconclusive_reason}", file=sys.stderr)
        if run.metadata.unreliable:
            print(f"UNRELIABLE: {run.metadata.unreliable_reason}", file=sys.stderr)
        if run.metadata.unstable:
            print(f"UNSTABLE: {run.metadata.unstable_reason}", file=sys.stderr)

    return EXIT_PROBLEM if (run.metadata.inconclusive or run.metadata.unreliable or run.metadata.unstable) else EXIT_OK


def cmd_judge_agreement(args) -> int:
    specs = _load_specs(args)
    judge_models = _split(args.judges) or list(config.DEFAULT_AGREEMENT_JUDGES)
    judge_models = list(dict.fromkeys(judge_models))
    if len(judge_models) < 2:
        print(
            "measuring judge agreement needs at least two distinct judge models",
            file=sys.stderr,
        )
        return EXIT_USAGE

    provider = providers.build_provider(
        args.provider, specs=specs, temperature=args.temperature, timeout_s=args.timeout
    )
    judges = [
        (
            model,
            pipeline.build_judge(args.provider, provider, model, args.temperature, args.timeout),
        )
        for model in judge_models
    ]

    result = judge_agreement.measure(specs, judges)

    out = Path(args.out) if getattr(args, "out", None) else None
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2))
        return EXIT_OK

    if result["n"]:
        print(f"judge agreement over {result['n']} comparable reference(s):")
        print(f"  judges: {', '.join(result['judges'])}")
        print(f"  exact-match rate: {result['exact_match_rate']:.2f}")
        print(f"  mean absolute difference: {result['mean_absolute_difference']:.3f}")
    else:
        print("no comparable judge scores; agreement is unmeasured")
    if out is not None:
        print(f"written to {out}")
    return EXIT_OK


def _round(value, digits: int = 3):
    return None if value is None else round(value, digits)


def cmd_report(args) -> int:
    path = Path(args.input)
    if not path.exists():
        print(f"results file not found: {path}", file=sys.stderr)
        return EXIT_PROBLEM

    run = reporting.load_results(path)
    weights = config.parse_weights(args.weights) if args.weights else None
    out = Path(args.out)
    reporting.write_report(run, out, weights=weights)

    if args.json:
        print(json.dumps({"report": str(out), "results_file": str(path)}, indent=2))
    else:
        print(f"report written to {out}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codegen-evals",
        description="Four-dimension eval framework for code-generation model quality.",
    )
    subparsers = parser.add_subparsers(dest="command")

    def add_selector_flags(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--specs", "--ids", dest="specs", help="comma-separated spec ids")
        sub.add_argument("--tiers", help="comma-separated tiers (easy,medium,hard)")
        sub.add_argument("--corpus", help="path to the corpus directory")

    list_specs = subparsers.add_parser("list-specs", help="list specs in the corpus")
    add_selector_flags(list_specs)
    list_specs.add_argument("--json", action="store_true", help="emit JSON")
    list_specs.set_defaults(func=cmd_list_specs)

    validate = subparsers.add_parser(
        "validate", help="check the corpus is sound by running every reference"
    )
    add_selector_flags(validate)
    validate.add_argument("--json", action="store_true", help="emit JSON")
    validate.set_defaults(func=cmd_validate)

    run = subparsers.add_parser("run", help="evaluate models against the corpus")
    add_selector_flags(run)
    run.add_argument(
        "--provider",
        default="mock",
        choices=list(providers.PROVIDER_NAMES),
        help="which backend to generate code with",
    )
    run.add_argument("--models", help="comma-separated model ids (default: provider bank)")
    run.add_argument("--judge", help="model id for the semantic judge")
    run.add_argument(
        "--judge-agreement",
        help="path to a judge-agreement JSON to record with the run",
    )
    run.add_argument("--weights", help="comma-separated key=value composite weights")
    run.add_argument("--out", default="reports/results.json", help="results file path")
    run.add_argument("--report-out", help="report path (default: alongside --out)")
    run.add_argument(
        "--temperature", type=float, default=config.DEFAULT_TEMPERATURE
    )
    run.add_argument(
        "--concurrency", type=int, default=config.DEFAULT_CONCURRENCY
    )
    run.add_argument(
        "--timeout", type=float, default=config.DEFAULT_TIMEOUT_S, help="per-generation timeout"
    )
    run.add_argument(
        "--suite-timeout",
        type=float,
        default=config.DEFAULT_SUITE_TIMEOUT_S,
        help="per-suite execution timeout",
    )
    run.add_argument(
        "--exclusion-threshold",
        type=float,
        default=config.DEFAULT_EXCLUSION_RATE_THRESHOLD,
        help="infrastructure-failure rate above which a model is flagged unreliable",
    )
    run.add_argument("--ruff", action="store_true", help="blend ruff into the style score")
    run.add_argument(
        "--repeats",
        type=int,
        default=config.DEFAULT_REPEAT_COUNT,
        help="attempts per (model, spec) pair; >1 measures repeat stability",
    )
    run.add_argument(
        "--control-model",
        default=None,
        help=(
            "deliberately weak model to measure whether the corpus discriminates "
            f"(suggested: {config.DEFAULT_CONTROL_MODEL}); omitted means the "
            "question is left unmeasured"
        ),
    )
    run.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="log one line per attempt in addition to the per-model summary",
    )
    run.add_argument("--quiet", action="store_true", help="suppress progress output")
    run.add_argument("--json", action="store_true", help="emit a JSON summary")
    run.set_defaults(func=cmd_run)

    agreement = subparsers.add_parser(
        "judge-agreement",
        help="measure agreement between two judge models over the reference solutions",
    )
    add_selector_flags(agreement)
    agreement.add_argument(
        "--provider",
        default="opencode",
        choices=list(providers.PROVIDER_NAMES),
        help="which backend the judge models run through",
    )
    agreement.add_argument(
        "--judges",
        help="comma-separated judge model ids (default: the configured agreement bank)",
    )
    agreement.add_argument("--temperature", type=float, default=config.DEFAULT_TEMPERATURE)
    agreement.add_argument("--timeout", type=float, default=config.DEFAULT_TIMEOUT_S)
    agreement.add_argument("--out", help="write the agreement JSON here (for run --judge-agreement)")
    agreement.add_argument("--json", action="store_true", help="emit JSON")
    agreement.set_defaults(func=cmd_judge_agreement)

    report = subparsers.add_parser("report", help="render a Markdown report")
    report.add_argument("--in", dest="input", default="reports/results.json")
    report.add_argument("--out", default="reports/report.md")
    report.add_argument("--weights", help="override composite weights for rendering")
    report.add_argument("--json", action="store_true", help="emit a JSON summary")
    report.set_defaults(func=cmd_report)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return args.func(args)
    except providers.ProviderConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return EXIT_USAGE
    except (ValueError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
