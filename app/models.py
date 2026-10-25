"""Structured types: the case file schema, the grader's scorecard, and the coach's plan."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CaseType = Literal["profitability", "market_sizing", "market_entry", "m_and_a", "pricing", "operations"]
Dimension = Literal["structure", "clarifying", "quantitative", "judgment", "synthesis", "communication"]
DIMENSIONS: list[str] = ["structure", "clarifying", "quantitative", "judgment", "synthesis", "communication"]


# ----------------------------------------------------------------------------- case file

class HiddenFact(BaseModel):
    topic: str = Field(description="Short snake_case id, e.g. 'labor_costs'. Unique within the case.")
    hint: str = Field(description="What kind of question unlocks this, shown to the interviewer, e.g. 'cost breakdown or cost trends'.")
    fact: str = Field(description="What the interviewer says when this is revealed. Must state every number in `numbers`.")
    numbers: dict[str, float] = Field(
        default_factory=dict,
        description="Named numbers in this fact, e.g. {'labor_cost_per_store_m': 1.2}. Names unique across the whole case.",
    )


class Series(BaseModel):
    name: str
    values: list[float]


class Exhibit(BaseModel):
    id: str = Field(description="Short id, e.g. 'ex1'.")
    title: str
    kind: Literal["bar", "line", "table"]
    unlock_topic: str = Field(description="The hidden fact topic that must be revealed before this exhibit can be shown.")
    labels: list[str] = Field(description="X-axis labels or table row labels.")
    series: list[Series] = Field(description="One or more data series, each with one value per label.")
    unit: str = Field(default="", description="Unit shown on the axis, e.g. '$M' or '%'.")


class MathAnswer(BaseModel):
    id: str
    question: str = Field(description="The calculation the candidate should do, phrased as the interviewer would ask it.")
    formula: str = Field(description="Arithmetic using the names from the hidden facts' `numbers`, e.g. 'stores * revenue_per_store_m'.")
    answer: float = Field(description="The correct result of the formula.")
    unit: str = ""
    tolerance_pct: float = Field(default=5.0, description="How far off (percent) a candidate's number may be and still count as right.")


class CaseFile(BaseModel):
    id: str
    title: str
    case_type: CaseType
    industry: str
    difficulty: int = Field(ge=1, le=3)
    prompt: str = Field(description="What the interviewer reads to open the case. No hidden numbers.")
    clarifying_answers: dict[str, str] = Field(
        description="Answers to likely clarifying questions, keyed by subject: objective, timeline, geography, business_model..."
    )
    hidden_facts: list[HiddenFact]
    exhibits: list[Exhibit] = Field(default_factory=list)
    math_answers: list[MathAnswer]
    ideal_structure: list[str] = Field(description="Bullet outline of a strong framework for this case.")
    recommendation: str = Field(description="What a great final recommendation says.")
    common_mistakes: list[str] = Field(default_factory=list)


# ----------------------------------------------------------------------------- grader

class DimensionScore(BaseModel):
    dimension: Dimension
    score: int = Field(ge=1, le=5)
    reason: str = Field(description="One sentence on why this score.")
    evidence_quote: str = Field(description="A short quote copied word for word from one CANDIDATE turn in the transcript.")


class MathAttempt(BaseModel):
    math_id: str = Field(description="The id of the math question from the answer key.")
    candidate_number: float | None = Field(description="The final number the candidate gave for this question, or null if they never answered it.")
    candidate_quote: str = Field(description="The candidate's words where they gave that number, copied word for word. Empty if none.")


class GraderOutput(BaseModel):
    """What the grader model returns. Python then checks it and builds the final Scorecard."""

    scores: list[DimensionScore]
    math_attempts: list[MathAttempt]
    top_strength: str
    biggest_gap: str
    summary: str = Field(description="Two sentences of feedback to the candidate, written to them as 'you'.")


class MathResult(BaseModel):
    math_id: str
    question: str
    correct_answer: float
    unit: str
    candidate_number: float | None
    verdict: Literal["correct", "incorrect", "not_attempted"]


class Scorecard(BaseModel):
    case_id: str
    case_title: str
    case_type: str
    scores: list[DimensionScore]
    math_results: list[MathResult]
    overall: float
    top_strength: str
    biggest_gap: str
    summary: str
    adjustments: list[str] = Field(default_factory=list, description="What Python changed in the model's grades, and why.")


# ----------------------------------------------------------------------------- coach

class CoachPlan(BaseModel):
    pattern: str = Field(description="What you notice across this and past cases, in one or two sentences.")
    focus_dimension: Dimension
    drill: str = Field(description="One concrete practice drill, doable in 10 minutes.")
    next_case_id: str = Field(description="The id of a library case that targets the focus area. Must be from the given list.")
    next_case_reason: str
