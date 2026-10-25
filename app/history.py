"""Per-user practice history, stored locally in data/history.json (gitignored)."""

from __future__ import annotations

import json
import re

from app.config import HISTORY_FILE


def user_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:40] or "guest"


def _load() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def get(name: str) -> list[dict]:
    return _load().get(user_key(name), [])


def add(name: str, row: dict) -> None:
    data = _load()
    data.setdefault(user_key(name), []).append(row)
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(json.dumps(data, indent=1))


def delete(name: str) -> int:
    data = _load()
    n = len(data.pop(user_key(name), []))
    HISTORY_FILE.write_text(json.dumps(data, indent=1))
    return n
