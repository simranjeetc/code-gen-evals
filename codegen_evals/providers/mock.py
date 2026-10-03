"""Deterministic offline provider.

This provider exists so the whole pipeline can be exercised with no network and
no credentials, and so tests have a stable subject. It is **not** a model: each
"skill" level maps to a deterministic mutation of the spec's reference solution,
chosen by hashing ``(model_id, spec_id)``.

Mutation happens at the source level rather than by inventing per-spec code, so
the mock stays runnable against the real hidden suites:

- ``perfect``  — the reference solution, unmodified
- ``untyped``  — reference with annotations and docstrings stripped
- ``stub``     — every required symbol replaced by a do-nothing stub
- ``empty``    — an empty module

The report labels mock runs as pipeline validation, never as a model ranking.
"""

from __future__ import annotations

import ast
import hashlib
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base import Provider

VARIANTS = ("perfect", "untyped", "stub", "empty")

# Share of the non-perfect mass given to each failure mode.
UNTYPED_SHARE = 0.40
STUB_SHARE = 0.35


def _unit(*parts: str) -> float:
    """A stable value in [0, 1) derived from the given strings."""
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:12], 16) / float(16 ** 12)


class _StripStyle(ast.NodeTransformer):
    """Removes type annotations and docstrings without changing behaviour."""

    @staticmethod
    def _drop_docstring(node) -> None:
        body = getattr(node, "body", None)
        if not body:
            return
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                remaining = body[1:]
                node.body = remaining if remaining else [ast.Pass()]

    def _clear_args(self, arguments: ast.arguments) -> None:
        for arg in list(arguments.args) + list(arguments.kwonlyargs) + list(arguments.posonlyargs):
            arg.annotation = None
        if arguments.vararg is not None:
            arguments.vararg.annotation = None
        if arguments.kwarg is not None:
            arguments.kwarg.annotation = None

    def visit_Module(self, node: ast.Module):
        self._drop_docstring(node)
        self.generic_visit(node)
        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        self._drop_docstring(node)
        self.generic_visit(node)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        node.returns = None
        self._clear_args(node.args)
        self._drop_docstring(node)
        self.generic_visit(node)
        return node

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        node.returns = None
        self._clear_args(node.args)
        self._drop_docstring(node)
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg):
        node.annotation = None
        return node

    def visit_AnnAssign(self, node: ast.AnnAssign):
        # An annotation-only declaration carries no runtime value; drop it.
        if node.value is None:
            return None
        self.generic_visit(node)
        return ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)


def strip_annotations_and_docstrings(source: str) -> str:
    """Return ``source`` with annotations and docstrings removed."""
    tree = ast.parse(source)
    tree = _StripStyle().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def build_stub(required_symbols: Sequence[str]) -> str:
    """A module where every required symbol exists but does nothing useful."""
    lines: List[str] = []
    for symbol in required_symbols:
        if symbol[:1].isupper():
            lines.append(f"class {symbol}:")
            lines.append("    def __init__(self, *args, **kwargs):")
            lines.append("        pass")
        else:
            lines.append(f"def {symbol}(*args, **kwargs):")
            lines.append("    return None")
        lines.append("")
    return "\n".join(lines)


class MockProvider(Provider):
    """Deterministic, offline, no-network provider."""

    name = "mock"

    def __init__(
        self,
        references: Optional[Dict[str, str]] = None,
        required_symbols: Optional[Dict[str, Sequence[str]]] = None,
        skills: Optional[Dict[str, float]] = None,
        temperature: float = 0.0,
        timeout_s: float = 120.0,
    ):
        super().__init__(temperature=temperature, timeout_s=timeout_s)
        self._references = dict(references or {})
        self._required_symbols = dict(required_symbols or {})
        self._skills = dict(skills or {})

    def skill_for(self, model_id: str) -> float:
        """Skill in [0, 1]; explicit where configured, hashed otherwise."""
        if model_id in self._skills:
            return self._skills[model_id]
        return _unit("skill", model_id)

    def variant_for(self, model_id: str, spec_id: str) -> str:
        skill = max(0.0, min(1.0, self.skill_for(model_id)))
        draw = _unit(model_id, spec_id)
        if draw < skill:
            return "perfect"
        remaining = draw - skill
        slack = 1.0 - skill
        if remaining < slack * UNTYPED_SHARE:
            return "untyped"
        if remaining < slack * (UNTYPED_SHARE + STUB_SHARE):
            return "stub"
        return "empty"

    def code_for(self, model_id: str, spec_id: str) -> str:
        variant = self.variant_for(model_id, spec_id)
        reference = self._references.get(spec_id, "")
        symbols = self._required_symbols.get(spec_id, [])
        if variant == "perfect":
            return reference or build_stub(symbols)
        if variant == "untyped":
            if not reference:
                return build_stub(symbols)
            try:
                return strip_annotations_and_docstrings(reference)
            except SyntaxError:
                return reference
        if variant == "stub":
            return build_stub(symbols)
        return ""

    def _invoke(
        self, prompt: str, model_id: str, spec_id: str = ""
    ) -> Tuple[str, Dict[str, Any]]:
        variant = self.variant_for(model_id, spec_id)
        code = self.code_for(model_id, spec_id)
        raw = "```python\n" + code + "```"
        return raw, {"variant": variant, "spec_id": spec_id}
