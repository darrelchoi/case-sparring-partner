"""Paths and fixed settings for Case Sparring Partner."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CASES_DIR = ROOT / "cases"
GENERATED_DIR = CASES_DIR / "generated"
OUTPUT_DIR = ROOT / "output"
STATIC_DIR = ROOT / "static"

USAGE_LOG = OUTPUT_DIR / "usage_log.jsonl"
SAFETY_LOG = OUTPUT_DIR / "safety_log.jsonl"
GENERATOR_LOG = OUTPUT_DIR / "generator_log.jsonl"
RUNS_DIR = OUTPUT_DIR / "runs"
HISTORY_FILE = DATA_DIR / "history.json"

MODEL_NAME = "gpt-6-luna"  # the only model allowed on the course key

# Spending and loop guards (Problem 10). Python enforces every one of these, not the model.
MAX_REQUESTS_PER_TURN = 5          # model round-trips (incl. tool calls) for one candidate turn
MAX_TOKENS_PER_TURN = 40_000       # total tokens one turn may use before it is stopped
MAX_TURNS_PER_CASE = 40            # candidate turns before the case is closed
MAX_INPUT_CHARS = 1_500            # longest candidate message accepted
MAX_COST_PER_CASE = 0.05           # dollars; the case ends gracefully past this
MAX_COST_PER_DAY = 2.00            # dollars across the whole app, read from the usage log
MIN_SECONDS_BETWEEN_TURNS = 1.0    # simple rate limit per session
MAX_OFF_TOPIC_STRIKES = 3          # off-topic attempts before the session ends
MAX_GENERATOR_RETRIES = 2          # generator retries after a failed math check

# Safety tests flip this off to show what happens without the Python defenses (the "before" run).
DEFENSES_ON = True

STAGES = ["clarify", "structure", "analysis", "synthesis", "done"]
CASE_TYPES = ["profitability", "market_sizing", "market_entry", "m_and_a", "pricing", "operations"]
