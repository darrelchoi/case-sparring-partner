"""Safety guards (Problem 10). Every check here is plain Python, so a clever prompt can't talk its way past it."""

from __future__ import annotations

import re

from app import config
from app.session import CaseSession
from app.usage import append_jsonl, now, spent_today

# Instruction-like text a candidate has no reason to say in a case interview.
INJECTION_PATTERNS = [
    r"\bignore\b.{0,40}\b(instructions?|rules?|rubric|prompt|above|previous)\b",
    r"\b(system|developer)\s*(prompt|message|note|override)?\s*:",
    r"\byou are now\b",
    r"\b(new|updated) (instructions?|rules)\b",
    r"\b(answer key|hidden facts?|hidden data)\b",
    r"\b(reveal|tell me|give me|list|dump|print)\b.{0,15}\ball (of )?(the |your )?(data|facts|topics|numbers)\b",
    r"\b(give|score|grade|rate) (me|this|my answers?)\b.{0,30}\b(5|five|10|perfect|full marks|top score)\b",
    r"\b5\s*/\s*5\b",
    r"\b(reveal|show|print|list) (me )?(your|the) (prompt|instructions|rules|topics)\b",
    r"\bjailbreak\b|\bDAN mode\b|\bdeveloper mode\b",
    r"</?(system|instructions?)>",
]
_INJECTION_RE = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def log_safety(event: str, session: CaseSession | None, **details) -> None:
    append_jsonl(config.SAFETY_LOG, {"time": now(), "event": event, "session_id": session.id if session else None, **details})


class Blocked(Exception):
    """A guard stopped this request. The message is safe to show the user."""


def check_budget(session: CaseSession) -> None:
    if session.totals["cost_usd"] >= config.MAX_COST_PER_CASE:
        log_safety("case_budget_hit", session, cost=session.totals["cost_usd"])
        raise Blocked(f"This case hit its spending cap (${config.MAX_COST_PER_CASE:.2f}). Press \"I'm ready to be graded\" to get your scorecard.")
    if spent_today() >= config.MAX_COST_PER_DAY:
        log_safety("daily_budget_hit", session)
        raise Blocked("The app has reached today's spending cap. Please try again tomorrow.")


def check_input(session: CaseSession, text: str, now_ts: float) -> list[str]:
    """Raise Blocked for hard stops. Return a list of soft flags (the turn goes through, but it's marked)."""
    if session.closed:
        raise Blocked("This case is over. Press \"I'm ready to be graded\" or start a new case.")
    if not text.strip():
        raise Blocked("Say or type something first.")
    if len(text) > config.MAX_INPUT_CHARS:
        log_safety("input_too_long", session, chars=len(text))
        raise Blocked(f"That message is too long ({len(text)} characters). Keep each answer under {config.MAX_INPUT_CHARS}, the way you would out loud.")
    if session.candidate_turns >= config.MAX_TURNS_PER_CASE:
        log_safety("turn_limit_hit", session)
        raise Blocked(f"This case reached its {config.MAX_TURNS_PER_CASE}-turn limit. Press \"I'm ready to be graded\".")
    last = next((t for t in reversed(session.transcript) if t.role == "candidate"), None)
    if last and last.text.strip() == text.strip() and now_ts - session.last_turn_at < 15:
        log_safety("duplicate_turn", session)
        raise Blocked("You just sent that. Say or type something new.")
    if now_ts - session.last_turn_at < config.MIN_SECONDS_BETWEEN_TURNS:
        log_safety("rate_limited", session)
        raise Blocked("Slow down a moment, then send again.")
    check_budget(session)

    if not config.DEFENSES_ON:
        return []
    flags = [p.pattern for p in _INJECTION_RE if p.search(text)]
    if flags:
        log_safety("injection_flagged", session, text=text[:300], patterns=flags)
    return flags


def looks_like_attack(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION_RE)


_NUM_RE = re.compile(r"(?<![\w.])\$?(\d[\d,]*(?:\.\d+)?)")


def numbers_in(text: str) -> list[float]:
    out = []
    for m in _NUM_RE.finditer(text):
        try:
            out.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return out


UNIT_SCALES = (1, 1e3, 1e6, 1e-3, 1e-6)
# Ways the interviewer may legitimately restate an allowed number: thousands/millions, hours↔minutes, %↔fraction.
RESTATE_SCALES = UNIT_SCALES + (60, 1 / 60, 100, 1 / 100, 12, 1 / 12, 365)


def _matches(x: float, pool: list[float], scales: tuple = UNIT_SCALES) -> bool:
    for v in pool:
        for scale in scales:
            if abs(x - v * scale) <= max(1e-9, abs(v * scale) * 0.001):
                return True
    return False


def check_output(session: CaseSession, reply: str) -> tuple[str, list[str]]:
    """Leak filter: block any reply that states an UNREVEALED hidden number. Numbers that aren't backed by
    anything (possible made-up data) are logged as warnings."""
    warnings: list[str] = []
    if not config.DEFENSES_ON:
        return reply, warnings
    allowed = (
        session.revealed_numbers()
        + numbers_in(session.case.prompt)
        + [n for a in session.case.clarifying_answers.values() for n in numbers_in(a)]
        + [n for t in session.transcript if t.role == "candidate" for n in numbers_in(t.text)]
        + session.turn_calc_results
    )
    unrevealed = session.unrevealed_numbers()
    for x in numbers_in(reply):
        if x < 10 and float(x).is_integer():
            continue  # small counts like "two things" or "3 drivers" are fine
        if _matches(x, allowed, RESTATE_SCALES):
            continue
        if _matches(x, unrevealed):
            log_safety("leak_blocked", session, number=x, reply=reply[:300])
            return ("Let's take that one step at a time. What would you like to look at next?", ["leak_blocked"])
        warnings.append(f"unverified number {x:g}")
    if warnings:
        log_safety("unverified_number", session, numbers=warnings, reply=reply[:300])
    return reply, warnings
