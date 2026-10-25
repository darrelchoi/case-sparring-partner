"""Agent 3: the Coach. Reads today's scorecard plus past ones and picks one drill and the next case."""

from __future__ import annotations

import json

from pydantic_ai import Agent

from app import config
from app.llm import build_model, settings
from app.models import CaseFile, CoachPlan, Scorecard

PROMPT = (config.ROOT / "prompts" / "coach.md").read_text()

# Fallback rule if the model picks an invalid case: weakest dimension → case type that trains it.
DIM_TO_TYPE = {
    "quantitative": "market_sizing", "structure": "profitability", "judgment": "m_and_a",
    "synthesis": "market_entry", "clarifying": "operations", "communication": "pricing",
}


def build_coach() -> Agent[None, CoachPlan]:
    return Agent(
        build_model(),
        output_type=CoachPlan,
        instructions=PROMPT,
        model_settings=settings(cache_key="csp-coach", effort="low", max_tokens=2_000),
    )


def coach_message(card: Scorecard, history: list[dict], library: dict[str, CaseFile]) -> str:
    today = {
        "case": card.case_title, "case_type": card.case_type,
        "scores": {s.dimension: s.score for s in card.scores},
        "math": [f"{r.math_id}: {r.verdict}" for r in card.math_results],
        "biggest_gap": card.biggest_gap,
    }
    past = [{"case_type": h["case_type"], "scores": h["scores"]} for h in history[-6:]]
    done = {h["case_id"] for h in history} | {card.case_id}
    lib = [{"id": c.id, "title": c.title, "type": c.case_type, "difficulty": c.difficulty, "done_before": c.id in done}
           for c in library.values()]
    return (f"TODAY:\n{json.dumps(today, indent=1)}\n\nPAST SCORECARDS (oldest first):\n{json.dumps(past)}\n\n"
            f"LIBRARY:\n{json.dumps(lib, indent=1)}")


def validate_plan(plan: CoachPlan, card: Scorecard, history: list[dict], library: dict[str, CaseFile]) -> tuple[CoachPlan, str | None]:
    """The coach must pick a real case, and not the one just played. Otherwise Python picks."""
    if plan.next_case_id in library and plan.next_case_id != card.case_id:
        return plan, None
    done = {h["case_id"] for h in history} | {card.case_id}
    want = DIM_TO_TYPE.get(plan.focus_dimension, "profitability")
    options = [c for c in library.values() if c.case_type == want and c.id not in done] or \
              [c for c in library.values() if c.id != card.case_id]
    pick = options[0]
    note = f"Coach picked '{plan.next_case_id}', which isn't a valid next case, so Python picked '{pick.id}'."
    return plan.model_copy(update={"next_case_id": pick.id,
                                   "next_case_reason": f"{pick.title} is a {pick.case_type.replace('_', ' ')} case, which trains {plan.focus_dimension}."}), note
