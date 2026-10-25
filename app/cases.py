"""Load case files and check them. The checker recomputes every formula in Python, so a case with
wrong math (hand-written or generated) never reaches a candidate."""

from __future__ import annotations

import ast
import json
import operator
from pathlib import Path

from pydantic import ValidationError

from app.config import CASES_DIR, GENERATED_DIR
from app.models import CaseFile

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expr: str, names: dict[str, float] | None = None) -> float:
    """Arithmetic only: numbers, + - * / ** and parentheses, plus the given variable names. No function calls."""
    names = names or {}

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in names:
                raise ValueError(f"unknown name '{node.id}'")
            return float(names[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            if isinstance(node.op, ast.Pow) and abs(ev(node.right)) > 10:
                raise ValueError("exponent too large")
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"not allowed in a formula: {ast.dump(node)[:60]}")

    if len(expr) > 300:
        raise ValueError("formula too long")
    return ev(ast.parse(expr.replace(",", ""), mode="eval"))


def check_case(case: CaseFile) -> list[str]:
    """Return a list of problems. Empty list = the case is clean."""
    problems: list[str] = []
    topics = [f.topic for f in case.hidden_facts]
    if len(set(topics)) != len(topics):
        problems.append("duplicate hidden-fact topics")
    if len(case.hidden_facts) < 3:
        problems.append("needs at least 3 hidden facts")
    if not case.math_answers:
        problems.append("needs at least 1 math question")

    names: dict[str, float] = {}
    for f in case.hidden_facts:
        for k, v in f.numbers.items():
            if k in names:
                problems.append(f"number name '{k}' is used in two facts")
            names[k] = v
            if not _number_in_text(v, f.fact):
                problems.append(f"fact '{f.topic}' never states its number {k}={v:g}")

    for m in case.math_answers:
        try:
            got = safe_eval(m.formula, names)
        except (ValueError, SyntaxError, ZeroDivisionError) as e:
            problems.append(f"math '{m.id}': formula can't be computed ({e})")
            continue
        if not _close(got, m.answer, 0.5):
            problems.append(f"math '{m.id}': formula gives {got:,.4g} but the answer key says {m.answer:,.4g}")

    for ex in case.exhibits:
        if ex.unlock_topic not in topics:
            problems.append(f"exhibit '{ex.id}' unlocks on unknown topic '{ex.unlock_topic}'")
        for s in ex.series:
            if len(s.values) != len(ex.labels):
                problems.append(f"exhibit '{ex.id}' series '{s.name}' has {len(s.values)} values for {len(ex.labels)} labels")

    for v in names.values():
        if _number_in_text(v, case.prompt) and abs(v) >= 10:
            problems.append(f"the opening prompt gives away hidden number {v:g}")
    return problems


def _close(a: float, b: float, pct: float) -> bool:
    if b == 0:
        return abs(a) < 1e-9
    return abs(a - b) / abs(b) * 100 <= pct


def _number_in_text(v: float, text: str) -> bool:
    """True if the number appears in the text in any common form (1200, 1,200, 1.2)."""
    t = text.replace(",", "")
    forms = {f"{v:g}", f"{v:.0f}" if float(v).is_integer() else f"{v:g}", f"{v:.1f}", f"{v:.2f}"}
    if float(v).is_integer():
        forms.add(str(int(v)))
    return any(f in t for f in forms if f)


def load_case_file(path: Path) -> CaseFile:
    return CaseFile.model_validate_json(path.read_text())


def all_cases(include_generated: bool = True) -> dict[str, CaseFile]:
    out: dict[str, CaseFile] = {}
    paths = sorted(CASES_DIR.glob("*.json"))
    if include_generated:
        paths += sorted(GENERATED_DIR.glob("*.json"))
    for p in paths:
        try:
            c = load_case_file(p)
        except (ValidationError, json.JSONDecodeError):
            continue
        if not check_case(c):
            out[c.id] = c
    return out


def library() -> dict[str, CaseFile]:
    return all_cases(include_generated=False)
