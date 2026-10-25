"""Token metering: every model call is priced and appended to output/usage_log.jsonl."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic_ai.messages import ModelResponse

from app.config import DATA_DIR, MODEL_NAME, USAGE_LOG

PRICES = json.loads((DATA_DIR / "prices.json").read_text())[MODEL_NAME]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def cost(input_tokens: int, cache_read: int, cache_write: int, output_tokens: int) -> float:
    uncached = max(input_tokens - cache_read - cache_write, 0)
    return (
        uncached * PRICES["input_per_1m"]
        + cache_read * PRICES["cached_input_per_1m"]
        + cache_write * PRICES["cache_write_per_1m"]
        + output_tokens * PRICES["output_per_1m"]
    ) / 1e6


def record(result, *, agent: str, session_id: str, extra: dict | None = None) -> dict:
    """Sum the usage of every model request in one agent run, log it, and return the totals."""
    rows = [m for m in result.new_messages() if isinstance(m, ModelResponse)]
    totals = {"input_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0, "output_tokens": 0, "requests": len(rows)}
    for m in rows:
        totals["input_tokens"] += m.usage.input_tokens
        totals["cache_read_tokens"] += m.usage.cache_read_tokens
        totals["cache_write_tokens"] += m.usage.cache_write_tokens
        totals["output_tokens"] += m.usage.output_tokens
    totals["cost_usd"] = round(
        cost(totals["input_tokens"], totals["cache_read_tokens"], totals["cache_write_tokens"], totals["output_tokens"]), 8
    )
    append_jsonl(USAGE_LOG, {"time": now(), "agent": agent, "session_id": session_id, **totals, **(extra or {})})
    return totals


def spent_today() -> float:
    """Dollars spent across the whole app today (UTC), for the daily budget cap."""
    if not USAGE_LOG.exists():
        return 0.0
    today = now()[:10]
    total = 0.0
    for line in USAGE_LOG.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("time", "").startswith(today):
            total += row.get("cost_usd", 0.0)
    return total


def empty_totals() -> dict:
    return {"input_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0, "output_tokens": 0, "requests": 0, "cost_usd": 0.0}


def add_totals(a: dict, b: dict) -> dict:
    out = {k: a.get(k, 0) + b.get(k, 0) for k in empty_totals()}
    out["cost_usd"] = round(out["cost_usd"], 8)
    return out
