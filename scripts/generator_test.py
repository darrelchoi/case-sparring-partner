"""Problem 6: generate several cases and record how often the math checker catches the generator.

    python scripts/generator_test.py            # 6 cases, one per case type
    python scripts/generator_test.py --n 3
Writes output/generator_report.md (every attempt is also in output/generator_log.jsonl).
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.generator import generate_case
from app.config import CASE_TYPES, OUTPUT_DIR

INDUSTRIES = ["boutique fitness studios", "K-pop concert tours", "regional hospitals", "electric scooters",
              "craft breweries", "online tutoring", "pet insurance", "cold-chain logistics"]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    args = ap.parse_args()

    jobs = [(CASE_TYPES[i % len(CASE_TYPES)], INDUSTRIES[i % len(INDUSTRIES)], 2) for i in range(args.n)]
    results = await asyncio.gather(*(generate_case(t, ind, d, session_id="generator-test") for t, ind, d in jobs))

    rows, first, retry, never, cost = [], 0, 0, 0, 0.0
    for (t, ind, _), r in zip(jobs, results):
        n = len(r["attempts"])
        if r["ok"] and n == 1:
            first += 1; outcome = "passed first try"
        elif r["ok"]:
            retry += 1; outcome = f"passed after {n - 1} retr{'y' if n == 2 else 'ies'}"
        else:
            never += 1; outcome = "rejected (never passed)"
        cost += r["usage"]["cost_usd"]
        caught = "; ".join(p for a in r["attempts"] for p in a["problems"]) or "—"
        title = r["case"].title if r["case"] else "—"
        rows.append(f"| {t} | {ind} | {outcome} | {title} | {caught[:220]} | ${r['usage']['cost_usd']:.4f} |")
        print(f"{t:14s} {ind:26s} {outcome}")

    md = [
        "# Case Generator test", "",
        f"Generated {args.n} cases. **{first}** passed the math checker on the first try, **{retry}** passed after the "
        f"checker sent errors back, and **{never}** were rejected. Total cost ${cost:.4f} (${cost / max(args.n, 1):.4f} per case).", "",
        "| Case type | Industry | Outcome | Title | What the checker caught | Cost |", "|---|---|---|---|---|---|", *rows, "",
    ]
    (OUTPUT_DIR / "generator_report.md").write_text("\n".join(md))
    print(f"\nfirst try {first} | after retry {retry} | rejected {never} | cost ${cost:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
