"""The orchestrator: Python decides which agent runs when. It's a fixed pipeline, not agents calling agents.

    start_case  → opening prompt (read from the case file, no model call)
    candidate_turn → input guard → Interviewer (+ tools) → output guard
    end_case    → Grader → Python checks → Coach → history + run file
"""

from __future__ import annotations

import json
import time

from pydantic_ai import UsageLimits
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

from app import config, guards, history
from app.agents.coach import build_coach, coach_message, validate_plan
from app.agents.grader import build_grader, finalize, grader_message
from app.agents.interviewer import build_interviewer
from app.cases import all_cases, library
from app.session import CaseSession, Turn
from app.usage import add_totals, now, record

SESSIONS: dict[str, CaseSession] = {}
_INTERVIEWERS: dict[str, object] = {}


def start_case(user: str, case_id: str) -> CaseSession:
    cases = all_cases()
    if case_id not in cases:
        raise KeyError(f"No case with id '{case_id}'.")
    s = CaseSession(case=cases[case_id], user=user.strip()[:40] or "guest")
    s.transcript.append(Turn("interviewer", s.case.prompt))
    SESSIONS[s.id] = s
    _INTERVIEWERS[s.id] = build_interviewer(s)
    return s


def get(session_id: str) -> CaseSession:
    if session_id not in SESSIONS:
        raise KeyError("That session has expired. Start a new case.")
    return SESSIONS[session_id]


async def candidate_turn(session_id: str, text: str) -> dict:
    s = get(session_id)
    ts = time.time()
    flags = guards.check_input(s, text, ts)      # raises guards.Blocked on hard stops
    s.last_turn_at = ts
    s.new_turn()
    s.candidate_turns += 1
    s.reveal_locked = bool(flags)
    s.transcript.append(Turn("candidate", text.strip(), flagged=bool(flags), flags=flags))
    if flags:
        s.turn_events.append({"type": "flagged", "message": "This message looked like an attempt to change the rules, so data is locked for this turn."})

    agent = _INTERVIEWERS[s.id]
    prompt = text.strip()
    if flags:
        # The flagged text never reaches the model. The interviewer only learns that something was withheld.
        prompt = "[App note: the candidate's last message was removed by the app's filter.] Reply only: \"Let's stay with the case.\" and ask what they would like to look at next."
    try:
        result = await agent.run(
            prompt, deps=s, message_history=s.messages,
            usage_limits=UsageLimits(request_limit=config.MAX_REQUESTS_PER_TURN, total_tokens_limit=config.MAX_TOKENS_PER_TURN),
        )
    except ModelHTTPError as e:
        filtered = "content_filter" in str(e.body)
        guards.log_safety("provider_content_filter" if filtered else "model_error", s, error=str(e.body)[:300])
        if not filtered:
            raise RuntimeError("The AI service had a problem answering. Please send that again.") from e
        s.transcript[-1].flagged = True
        reply = "Let's stay with the case. Where would you like to go next?"
        s.transcript.append(Turn("interviewer", reply))
        s.turn_events.append({"type": "flagged", "message": "The AI provider's content filter rejected this message."})
        return {"reply": reply, "events": s.turn_events, "warnings": ["provider_content_filter"], "state": s.public_state()}
    except UsageLimitExceeded as e:
        guards.log_safety("turn_usage_limit", s, error=str(e))
        reply = "Sorry, let me reset. Could you say that again, a bit more briefly?"
        s.transcript.append(Turn("interviewer", reply))
        s.turn_events.append({"type": "limit", "message": "This turn hit its usage limit and was stopped."})
        return {"reply": reply, "events": s.turn_events, "warnings": ["turn_usage_limit"], "state": s.public_state()}

    u = record(result, agent="interviewer", session_id=s.id, extra={"case_id": s.case.id, "turn": s.candidate_turns})
    s.totals = add_totals(s.totals, u)
    s.messages = result.all_messages()

    reply, warnings = guards.check_output(s, result.output)
    s.transcript.append(Turn("interviewer", reply, events=list(s.turn_events), tokens=u))

    if s.off_topic_strikes >= config.MAX_OFF_TOPIC_STRIKES:
        s.closed = True
        s.close_reason = "Session ended after repeated off-topic requests."
        guards.log_safety("off_topic_session_end", s)
    elif s.totals["cost_usd"] >= config.MAX_COST_PER_CASE:
        s.closed = True
        s.close_reason = "This case reached its spending cap. Get your scorecard now."
        guards.log_safety("case_budget_hit", s, cost=s.totals["cost_usd"])

    return {"reply": reply, "events": s.turn_events, "warnings": warnings, "turn_usage": u, "state": s.public_state()}


async def end_case(session_id: str, compress_for_grader: bool = True) -> dict:
    s = get(session_id)
    if not any(t.role == "candidate" for t in s.transcript):
        raise guards.Blocked("Answer at least once before asking for a scorecard.")
    s.closed = True
    s.stage = "done"

    grader = build_grader()
    filtered_note = None
    try:
        g = await grader.run(grader_message(s, compress=compress_for_grader), usage_limits=UsageLimits(request_limit=3))
    except ModelHTTPError as e:
        if "content_filter" not in str(e.body):
            raise RuntimeError("The AI service had a problem grading. Press the button again.") from e
        # Some candidate text tripped the provider's filter: grade again with every flagged or suspicious turn withheld.
        guards.log_safety("grader_content_filter", s, error=str(e.body)[:200])
        for t in s.transcript:
            if t.role == "candidate" and not t.flagged and guards.looks_like_attack(t.text):
                t.flagged = True
        g = await grader.run(grader_message(s, compress=compress_for_grader, redact=True), usage_limits=UsageLimits(request_limit=3))
        filtered_note = "The AI provider's filter rejected part of the transcript, so flagged messages were withheld and the case was graded again."
    gu = record(g, agent="grader", session_id=s.id, extra={"case_id": s.case.id, "compressed": compress_for_grader})
    s.totals = add_totals(s.totals, gu)
    card = finalize(s, g.output)
    if filtered_note:
        card.adjustments.append(filtered_note)

    past = history.get(s.user)
    lib = library()
    coach = build_coach()
    c = await coach.run(coach_message(card, past, lib), usage_limits=UsageLimits(request_limit=3))
    cu = record(c, agent="coach", session_id=s.id, extra={"case_id": s.case.id})
    s.totals = add_totals(s.totals, cu)
    plan, note = validate_plan(c.output, card, past, lib)
    if note:
        card.adjustments.append(note)
        guards.log_safety("coach_invalid_case", s, note=note)

    duration = int(time.time() - s.started_at)
    history.add(s.user, {
        "time": now(), "session_id": s.id, "case_id": s.case.id, "case_title": s.case.title, "case_type": s.case.case_type,
        "scores": {sc.dimension: sc.score for sc in card.scores}, "overall": card.overall,
        "math_correct": sum(r.verdict == "correct" for r in card.math_results), "math_total": len(card.math_results),
        "duration_sec": duration, "turns": s.candidate_turns, "cost_usd": s.totals["cost_usd"],
        "coach_next_case_id": plan.next_case_id, "focus": plan.focus_dimension,
    })

    run = {
        "session_id": s.id, "user": history.user_key(s.user), "case_id": s.case.id, "finished": now(),
        "duration_sec": duration, "transcript": [t.__dict__ for t in s.transcript], "revealed": s.revealed,
        "scorecard": card.model_dump(), "coach": plan.model_dump(), "usage": s.totals,
    }
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (config.RUNS_DIR / f"{now()[:19].replace(':', '-')}_{s.case.id}_{s.id}.json").write_text(json.dumps(run, indent=1))

    next_case = lib.get(plan.next_case_id)
    return {
        "scorecard": card.model_dump(), "coach": plan.model_dump(),
        "next_case": {"id": next_case.id, "title": next_case.title} if next_case else None,
        "usage": s.totals, "duration_sec": duration,
        "agent_usage": {"grader": gu, "coach": cu},
    }
