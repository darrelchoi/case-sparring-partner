"""The state of one practice case. Python owns this state. The interviewer can only change it through tools."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from app.models import CaseFile
from app.usage import empty_totals


@dataclass
class Turn:
    role: str  # "candidate" | "interviewer"
    text: str
    flagged: bool = False
    flags: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)   # tools the interviewer used to produce this reply
    tokens: dict = field(default_factory=dict)


@dataclass
class CaseSession:
    case: CaseFile
    user: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    stage: str = "clarify"
    revealed: list[str] = field(default_factory=list)       # hidden-fact topics revealed so far
    exhibits_shown: list[str] = field(default_factory=list)
    transcript: list[Turn] = field(default_factory=list)
    messages: list = field(default_factory=list)            # PydanticAI message history for the interviewer
    totals: dict = field(default_factory=empty_totals)      # tokens + dollars for the whole case
    off_topic_strikes: int = 0
    candidate_turns: int = 0
    started_at: float = field(default_factory=time.time)
    last_turn_at: float = 0.0
    closed: bool = False
    close_reason: str = ""
    # Per-turn scratch, reset at the start of every candidate turn.
    turn_events: list[dict] = field(default_factory=list)   # what the UI should show (fact unlocked, exhibit...)
    turn_reveals: int = 0
    turn_calc_results: list[float] = field(default_factory=list)
    reveal_locked: bool = False                              # set when the input guard flags a turn

    def new_turn(self) -> None:
        self.turn_events = []
        self.turn_reveals = 0
        self.turn_calc_results = []
        self.reveal_locked = False

    def fact(self, topic: str):
        return next((f for f in self.case.hidden_facts if f.topic == topic), None)

    def revealed_numbers(self) -> list[float]:
        out: list[float] = []
        for t in self.revealed:
            f = self.fact(t)
            if f:
                out += list(f.numbers.values())
        for ex in self.case.exhibits:
            if ex.id in self.exhibits_shown:
                for s in ex.series:
                    out += s.values
        return out

    def unrevealed_numbers(self) -> list[float]:
        out: list[float] = []
        for f in self.case.hidden_facts:
            if f.topic not in self.revealed:
                out += list(f.numbers.values())
        return out

    def public_state(self) -> dict:
        """What the browser gets after each turn."""
        return {
            "session_id": self.id,
            "case": {"id": self.case.id, "title": self.case.title, "case_type": self.case.case_type,
                     "industry": self.case.industry, "difficulty": self.case.difficulty},
            "stage": self.stage,
            "revealed_count": len(self.revealed),
            "fact_count": len(self.case.hidden_facts),
            "exhibits": [ex.model_dump() for ex in self.case.exhibits if ex.id in self.exhibits_shown],
            "usage": self.totals,
            "turns": self.candidate_turns,
            "closed": self.closed,
            "close_reason": self.close_reason,
            "elapsed_sec": int(time.time() - self.started_at),
        }
