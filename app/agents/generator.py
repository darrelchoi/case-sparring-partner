"""Agent 4: the Case Generator. Writes a new case in the CaseFile schema. Python's checker recomputes
every number before the case is saved. A failed case goes back to the model with the errors, at most
MAX_GENERATOR_RETRIES times."""

from __future__ import annotations

import json
import re
import uuid

from pydantic_ai import Agent

from app import config
from app.cases import check_case, library
from app.llm import build_model, settings
from app.models import CaseFile
from app.usage import add_totals, append_jsonl, empty_totals, now, record

PROMPT = (config.ROOT / "prompts" / "generator.md").read_text()
EXAMPLE_IDS = ["brew_bloom", "pesopath"]


def build_generator() -> Agent[None, CaseFile]:
    lib = library()
    examples = "\n\n".join(lib[i].model_dump_json(indent=1) for i in EXAMPLE_IDS if i in lib)
    return Agent(
        build_model(),
        output_type=CaseFile,
        instructions=PROMPT + "\n\n# Two example cases at the quality bar\n\n" + examples,
        model_settings=settings(cache_key="csp-generator", effort="medium", max_tokens=12_000),
    )


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:24] or "case"


async def generate_case(case_type: str, industry: str, difficulty: int, session_id: str = "generator") -> dict:
    """Returns {"ok": bool, "case": CaseFile | None, "attempts": [...], "usage": totals}."""
    if case_type not in config.CASE_TYPES:
        raise ValueError(f"case_type must be one of {config.CASE_TYPES}")
    industry = industry.strip()[:60] or "any industry"
    difficulty = min(max(int(difficulty), 1), 3)

    agent = build_generator()
    ask = (f"Write one new case. case_type: {case_type}. Industry: {industry}. Difficulty: {difficulty} (1 = easy, 3 = hard). "
           "Return the complete case.")
    history = None
    totals = empty_totals()
    attempts: list[dict] = []
    for attempt in range(config.MAX_GENERATOR_RETRIES + 1):
        result = await agent.run(ask, message_history=history)
        u = record(result, agent="generator", session_id=session_id, extra={"attempt": attempt + 1})
        totals = add_totals(totals, u)
        case = result.output
        case.id = f"gen_{_slug(industry)}_{uuid.uuid4().hex[:6]}"
        case.case_type = case_type  # type: ignore[assignment]
        problems = check_case(case)
        attempts.append({"attempt": attempt + 1, "passed": not problems, "problems": problems, "tokens": u})
        append_jsonl(config.GENERATOR_LOG, {"time": now(), "case_type": case_type, "industry": industry, "attempt": attempt + 1,
                                            "passed": not problems, "problems": problems, "cost_usd": u["cost_usd"], "case_id": case.id})
        if not problems:
            config.GENERATED_DIR.mkdir(parents=True, exist_ok=True)
            (config.GENERATED_DIR / f"{case.id}.json").write_text(case.model_dump_json(indent=2) + "\n")
            return {"ok": True, "case": case, "attempts": attempts, "usage": totals}
        history = result.all_messages()
        ask = ("Your case failed these automatic checks:\n- " + "\n- ".join(problems)
               + "\nFix every problem and return the complete corrected case. Recompute every answer from its formula.")
    return {"ok": False, "case": None, "attempts": attempts, "usage": totals}
