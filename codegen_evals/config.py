"""Default configuration: model bank, judge, weights, thresholds, runtime."""

from __future__ import annotations

from typing import Dict, List

# Subjects. Deliberately excludes premium models; a model is only ever
# evaluated because it is named in config or on the command line.
DEFAULT_MODEL_BANK: List[str] = [
    "opencode-go/deepseek-v4-pro",
    "opencode-go/deepseek-v4.1-flash",
    "opencode-go/mimo-v2.6-flash",
    "opencode-go/longcat-2.5-preview-free",
]

# Must never also appear as a subject: the judge may not grade its own output.
DEFAULT_JUDGE_MODEL = "opencode-go/glm-5.3-flash"

# The offline bank. Skills are explicit so mock runs are predictable rather
# than accidentally bunched.
MOCK_MODELS: List[str] = ["mock-strong", "mock-mid", "mock-weak"]
MOCK_SKILLS: Dict[str, float] = {
    "mock-strong": 0.85,
    "mock-mid": 0.60,
    "mock-weak": 0.30,
}

DEFAULT_WEIGHTS: Dict[str, float] = {
    "execution": 0.4,
    "edge": 0.25,
    "semantic": 0.25,
    "style": 0.1,
}

DEFAULT_THRESHOLDS: Dict[str, float] = {"high": 0.8, "low": 0.6}

DEFAULT_TEMPERATURE = 0.0
DEFAULT_CONCURRENCY = 4
DEFAULT_TIMEOUT_S = 180.0
DEFAULT_SUITE_TIMEOUT_S = 60.0

DEFAULT_AGENT = "codegen-eval"
DEFAULT_JUDGE_AGENT = "codegen-judge"

RESULTS_SCHEMA_NAME = "codegen-evals/results"


def parse_weights(value: str) -> Dict[str, float]:
    """Parse ``"execution=0.4,edge=0.25"`` into a weights dict."""
    weights: Dict[str, float] = {}
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise ValueError(f"invalid weight '{chunk}': expected key=value")
        key, raw = chunk.split("=", 1)
        weights[key.strip()] = float(raw)
    return weights
