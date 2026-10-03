"""Tests for providers, code extraction, and provider selection."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from codegen_evals import config, corpus, providers
from codegen_evals.providers import base, mock, opencode, public_api

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "corpus"


def _specs():
    return corpus.load_corpus(CORPUS_ROOT)


# --- 3.1 base contract -------------------------------------------------------


class RecordingProvider(base.Provider):
    name = "recording"

    def __init__(self, result="", error=None, **kwargs):
        super().__init__(**kwargs)
        self._result = result
        self._error = error
        self.seen = []

    def _invoke(self, prompt, model_id, spec_id=""):
        self.seen.append((prompt, model_id, spec_id))
        if self._error is not None:
            raise self._error
        return self._result, {"custom": 1}


def test_generate_records_metadata_and_extracts_code():
    provider = RecordingProvider(result="```python\nx = 1\n```", temperature=0.25)
    generation = provider.generate("prompt", "model-a", spec_id="s1")
    assert generation.provider == "recording"
    assert generation.model_id == "model-a"
    assert generation.spec_id == "s1"
    assert generation.code == "x = 1\n"
    assert generation.extracted is True
    assert generation.error is None
    assert generation.params["temperature"] == 0.25
    assert generation.params["custom"] == 1
    assert generation.duration_s >= 0.0


def test_generate_contains_a_raised_exception():
    provider = RecordingProvider(error=RuntimeError("boom"))
    generation = provider.generate("prompt", "model-a")
    assert generation.extracted is False
    assert generation.code is None
    assert generation.error is not None
    assert "RuntimeError" in generation.error
    assert "boom" in generation.error


def test_generate_records_extraction_failure_without_raising():
    provider = RecordingProvider(result="I will not give you code.")
    generation = provider.generate("prompt", "model-a")
    assert generation.extracted is False
    assert generation.code is None
    assert "no fenced code block" in generation.error


def test_spec_id_reaches_invoke():
    provider = RecordingProvider(result="```python\npass\n```")
    provider.generate("p", "m", spec_id="abc")
    assert provider.seen[-1] == ("p", "m", "abc")


# --- 3.2 code extraction ----------------------------------------------------


def test_extracts_python_fence():
    code, language = base.extract_code("blah\n```python\nx = 1\n```\ntrailing")
    assert code == "x = 1\n"
    assert language == "python"


def test_extracts_py_alias():
    code, _ = base.extract_code("```py\ny = 2\n```")
    assert code == "y = 2\n"


def test_extracts_python3_alias():
    code, _ = base.extract_code("```python3\nz = 3\n```")
    assert code == "z = 3\n"


def test_falls_back_to_untagged_fence():
    code, language = base.extract_code("```\nw = 4\n```")
    assert code == "w = 4\n"
    assert language == ""


def test_prefers_the_first_python_block_among_many():
    text = "```python\nfirst = 1\n```\n```python\nsecond = 2\n```"
    code, _ = base.extract_code(text)
    assert code == "first = 1\n"


def test_python_block_wins_over_earlier_untagged_block():
    text = "```\nuntagged = 1\n```\n```python\npythonish = 2\n```"
    code, _ = base.extract_code(text)
    assert code == "pythonish = 2\n"


def test_non_python_fence_is_rejected():
    code, language = base.extract_code("```javascript\nvar x = 1;\n```")
    assert code is None
    assert language is None


def test_no_fence_returns_nothing():
    assert base.extract_code("just prose") == (None, None)


def test_empty_input_returns_nothing():
    assert base.extract_code("") == (None, None)


def test_unterminated_fence_is_still_usable():
    code, _ = base.extract_code("```python\nx = 1\ny = 2")
    assert code == "x = 1\ny = 2\n"


def test_empty_fenced_block_extracts_empty_code():
    code, _ = base.extract_code("```python\n```")
    assert code == ""


def test_code_ends_with_a_newline():
    code, _ = base.extract_code("```python\nx = 1\n```")
    assert code.endswith("\n")


# --- 3.3 mock provider ------------------------------------------------------


def _mock_provider():
    specs = _specs()
    return providers.build_provider("mock", specs=specs)


def test_mock_is_deterministic():
    provider = _mock_provider()
    first = provider.generate("p", "mock-mid", spec_id="fizzbuzz")
    second = provider.generate("p", "mock-mid", spec_id="fizzbuzz")
    assert first.code == second.code
    assert first.params["variant"] == second.params["variant"]


def test_mock_uses_the_configured_skill_table():
    provider = _mock_provider()
    assert provider.skill_for("mock-strong") == config.MOCK_SKILLS["mock-strong"]
    assert provider.skill_for("mock-mid") == config.MOCK_SKILLS["mock-mid"]
    assert provider.skill_for("mock-weak") == config.MOCK_SKILLS["mock-weak"]


def test_mock_skill_ordering_produces_more_perfect_code_for_stronger_models():
    provider = _mock_provider()
    spec_ids = [spec.id for spec in _specs()]

    def perfect_count(model_id):
        return sum(1 for spec_id in spec_ids if provider.variant_for(model_id, spec_id) == "perfect")

    strong = perfect_count("mock-strong")
    mid = perfect_count("mock-mid")
    weak = perfect_count("mock-weak")
    assert strong >= mid >= weak
    assert strong > weak


def test_mock_does_not_collapse_to_one_variant_for_a_model():
    provider = _mock_provider()
    variants = {provider.variant_for("mock-mid", spec.id) for spec in _specs()}
    assert len(variants) > 1


def test_mock_variants_cover_all_kinds_across_the_bank():
    provider = _mock_provider()
    seen = set()
    for model_id in config.MOCK_MODELS:
        for spec in _specs():
            seen.add(provider.variant_for(model_id, spec.id))
    assert seen == set(mock.VARIANTS)


def test_mock_produces_runnable_python_for_every_variant():
    provider = _mock_provider()
    for spec in _specs():
        for model_id in config.MOCK_MODELS:
            generation = provider.generate("p", model_id, spec_id=spec.id)
            assert generation.extracted is True
            if generation.code:
                compile(generation.code, f"{spec.id}-{model_id}", "exec")


def test_strip_annotations_removes_annotations_and_docstrings():
    source = 'def f(x: int) -> int:\n    """Doc."""\n    return x + 1\n'
    stripped = mock.strip_annotations_and_docstrings(source)
    assert "int" not in stripped
    assert "Doc." not in stripped
    namespace = {}
    exec(stripped, namespace)
    assert namespace["f"](1) == 2


def test_build_stub_defines_every_symbol():
    stub = mock.build_stub(["f", "LRUCache"])
    namespace = {}
    exec(stub, namespace)
    assert namespace["f"]() is None
    assert namespace["LRUCache"]()  # instantiable


def test_stub_handles_missing_symbols_list():
    provider = mock.MockProvider(references={}, required_symbols={}, skills={"m": 0.0})
    generation = provider.generate("p", "m", spec_id="unknown")
    assert generation.extracted is True


# --- 3.4 opencode provider --------------------------------------------------


def test_opencode_build_command_shape():
    provider = opencode.OpenCodeProvider(executable="/usr/bin/true", agent="codegen-eval")
    command = provider.build_command("hello", "opencode-go/mimo-v2.6-flash")
    assert command[0] == "/usr/bin/true"
    assert "run" in command
    assert "--agent" in command and "codegen-eval" in command
    assert "--model" in command and "opencode-go/mimo-v2.6-flash" in command
    assert "--format" in command and "json" in command
    assert command[-1] == "hello"


def test_opencode_missing_binary_is_a_config_error(monkeypatch):
    monkeypatch.setattr(opencode, "find_opencode", lambda: None)
    with pytest.raises(base.ProviderConfigError):
        opencode.OpenCodeProvider()


def test_parse_ndjson_collects_text_parts():
    payload = "\n".join(
        [
            json.dumps({"type": "step_start"}),
            json.dumps({"type": "text", "part": {"text": "```python\n"}}),
            json.dumps({"type": "text", "part": {"text": "x = 1\n```"}}),
            "not json",
        ]
    )
    text, errors = opencode.parse_ndjson(payload)
    assert text == "```python\nx = 1\n```"
    assert errors == []


def test_parse_ndjson_collects_errors():
    payload = json.dumps({"type": "error", "error": {"message": "nope"}})
    text, errors = opencode.parse_ndjson(payload)
    assert text == ""
    assert errors


@pytest.mark.skipif(
    os.environ.get("CODEGEN_EVALS_LIVE") != "1",
    reason="set CODEGEN_EVALS_LIVE=1 to run a live OpenCode call",
)
def test_live_opencode_call_returns_extractable_code():
    provider = opencode.OpenCodeProvider(timeout_s=180.0)
    generation = provider.generate("Define add(a, b).", "opencode-go/mimo-v2.6-flash")
    assert generation.error is None, generation.error
    assert generation.extracted is True
    assert "def " in (generation.code or "")
    assert generation.duration_s > 0.0


# --- 3.5 public API providers -----------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.mark.parametrize(
    "provider_class,env_var",
    [
        (public_api.AnthropicProvider, "ANTHROPIC_API_KEY"),
        (public_api.OpenAIProvider, "OPENAI_API_KEY"),
        (public_api.TogetherProvider, "TOGETHER_API_KEY"),
    ],
)
def test_public_provider_requires_named_credential(monkeypatch, provider_class, env_var):
    monkeypatch.delenv(env_var, raising=False)
    with pytest.raises(base.ProviderConfigError) as caught:
        provider_class()
    assert env_var in str(caught.value)


def test_anthropic_extracts_text(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    payload = {"content": [{"type": "text", "text": "```python\nx = 1\n```"}]}
    provider = public_api.AnthropicProvider(opener=lambda request, timeout: _FakeResponse(payload))
    generation = provider.generate("p", "claude-sonnet-4-5")
    assert generation.code == "x = 1\n"
    assert generation.provider == "anthropic"


def test_openai_extracts_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    payload = {"choices": [{"message": {"content": "```python\ny = 2\n```"}}]}
    provider = public_api.OpenAIProvider(opener=lambda request, timeout: _FakeResponse(payload))
    generation = provider.generate("p", "gpt-4o")
    assert generation.code == "y = 2\n"


def test_together_extracts_text(monkeypatch):
    monkeypatch.setenv("TOGETHER_API_KEY", "test-key")
    payload = {"choices": [{"message": {"content": "```python\nz = 3\n```"}}]}
    provider = public_api.TogetherProvider(opener=lambda request, timeout: _FakeResponse(payload))
    generation = provider.generate("p", "meta-llama/Llama-2-70b-chat-hf")
    assert generation.code == "z = 3\n"


def test_http_error_is_contained(monkeypatch):
    import urllib.error

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def boom(request, timeout):
        raise urllib.error.HTTPError("url", 500, "server error", {}, None)

    provider = public_api.OpenAIProvider(opener=boom)
    generation = provider.generate("p", "gpt-4o")
    assert generation.extracted is False
    assert generation.error is not None


# --- 3.6 provider selection and config --------------------------------------


def test_default_models_per_provider():
    assert providers.default_models("mock") == config.MOCK_MODELS
    assert providers.default_models("opencode") == config.DEFAULT_MODEL_BANK
    assert providers.default_models("together")


def test_unknown_provider_name_is_a_config_error():
    with pytest.raises(base.ProviderConfigError):
        providers.default_models("nope")
    with pytest.raises(base.ProviderConfigError):
        providers.build_provider("nope")


def test_judge_is_not_in_the_subject_bank():
    assert config.DEFAULT_JUDGE_MODEL not in config.DEFAULT_MODEL_BANK


def test_build_mock_provider_over_two_models_produces_results_for_both():
    provider = providers.build_provider("mock", specs=_specs(), temperature=0.0)
    for model_id in ("mock-mid", "mock-weak"):
        generation = provider.generate("p", model_id, spec_id="fizzbuzz")
        assert generation.model_id == model_id
        assert generation.params["temperature"] == 0.0


def test_parse_weights_round_trip():
    weights = config.parse_weights("execution=0.5,style=0.1")
    assert weights == {"execution": 0.5, "style": 0.1}


def test_parse_weights_rejects_bad_input():
    with pytest.raises(ValueError):
        config.parse_weights("execution")


def test_default_weights_and_thresholds_sum_sensibly():
    assert abs(sum(config.DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9
    assert config.DEFAULT_THRESHOLDS["high"] > config.DEFAULT_THRESHOLDS["low"]
