"""Problem 9: run 5 full scripted cases, measure real tokens per agent, and test one cost cut against quality.

    python scripts/cost_report.py        # about $0.02 of API calls
Writes output/cost_report.md and output/cost_report.json.

Cost-cut experiment: the Grader reads a COMPRESSED transcript (interviewer lines cut to 160 characters)
instead of the full one. Each transcript is graded three times: full (A), full again (B, to measure the
grader's own randomness), and compressed (C). If |A - C| is about the same as |A - B|, compression
doesn't hurt quality.
"""

import asyncio
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import UsageLimits

from app import config, orchestrator
from app.agents.grader import build_grader, finalize, grader_message
from app.usage import cost, record

SAMPLES = Path(__file__).resolve().parent / "sample_answers"
RUNS = [
    ("brew_bloom", "brew_bloom_strong.txt", "strong"),
    ("skylink", "skylink_medium.txt", "medium"),
    ("pickleball", "pickleball_strong.txt", "strong"),
    ("ledgerloop_ai", "ledgerloop_weak.txt", "weak"),
    ("harbor_er", "harbor_er_strong.txt", "strong"),
]
CASES_PER_MONTH = 13       # 3 cases a week during recruiting season
COACH_PRICE_PER_CASE = 75  # a paid human case coach, ~$150/hour, 30-minute case


async def run_case(case_id: str, script: str) -> dict:
    s = orchestrator.start_case("cost-test", case_id)
    for line in (SAMPLES / script).read_text().splitlines():
        if line.strip():
            s.last_turn_at = 0
            await orchestrator.candidate_turn(s.id, line.strip())
    interview_totals = dict(s.totals)
    res = await orchestrator.end_case(s.id)
    return {"session": s, "interview": interview_totals, "grader": res["agent_usage"]["grader"],
            "coach": res["agent_usage"]["coach"], "total": res["usage"], "turns": s.candidate_turns,
            "overall": res["scorecard"]["overall"]}


async def grade(s, compress: bool) -> tuple[dict, list[int], float]:
    g = await build_grader().run(grader_message(s, compress=compress), usage_limits=UsageLimits(request_limit=3))
    u = record(g, agent="grader-experiment", session_id=s.id, extra={"compressed": compress})
    card = finalize(s, g.output)
    return u, [x.score for x in card.scores], card.overall


def no_cache_cost(t: dict) -> float:
    return cost(t["input_tokens"], 0, 0, t["output_tokens"])


async def main() -> None:
    runs = []
    for case_id, script, quality in RUNS:
        r = await run_case(case_id, script)
        r.update(case_id=case_id, quality=quality)
        runs.append(r)
        print(f"{case_id:14s} {quality:7s} turns {r['turns']:2d}  overall {r['overall']}  cost ${r['total']['cost_usd']:.4f}")

    # --- cost-cut experiment
    exp = []
    for r in runs:
        (ua, sa, oa), (ub, sb, ob), (uc, sc, oc) = await asyncio.gather(grade(r["session"], False), grade(r["session"], False), grade(r["session"], True))
        exp.append({"case_id": r["case_id"], "full_tokens": ua["input_tokens"], "compressed_tokens": uc["input_tokens"],
                    "full_cost": ua["cost_usd"], "compressed_cost": uc["cost_usd"],
                    "overall_A": oa, "overall_B": ob, "overall_C": oc,
                    "diff_AB": statistics.mean(abs(x - y) for x, y in zip(sa, sb)),
                    "diff_AC": statistics.mean(abs(x - y) for x, y in zip(sa, sc))})

    # --- aggregate
    keys = ["input_tokens", "cache_read_tokens", "output_tokens", "cost_usd"]
    avg = {part: {k: statistics.mean(r[part][k] for r in runs) for k in keys} for part in ["interview", "grader", "coach", "total"]}
    per_case = avg["total"]["cost_usd"]
    per_case_nocache = statistics.mean(no_cache_cost(r["total"]) for r in runs)
    month = per_case * CASES_PER_MONTH
    cache_share = avg["total"]["cache_read_tokens"] / avg["total"]["input_tokens"]

    md = [
        "# Tokenomics: measured from real runs", "",
        f"5 full cases (scripted candidates of different quality), model `{config.MODEL_NAME}`. Prices per 1M tokens: input ${config_prices()['input_per_1m']}, "
        f"cached input ${config_prices()['cached_input_per_1m']}, output ${config_prices()['output_per_1m']}. Raw rows are in `output/usage_log.jsonl`.", "",
        "## One case, by agent (average of 5)", "",
        "| Agent | Input tokens | of which cached | Output tokens | Cost |", "|---|---|---|---|---|",
        *[f"| {name} | {avg[p]['input_tokens']:,.0f} | {avg[p]['cache_read_tokens']:,.0f} | {avg[p]['output_tokens']:,.0f} | ${avg[p]['cost_usd']:.5f} |"
          for name, p in [("Interviewer (all turns)", "interview"), ("Grader", "grader"), ("Coach", "coach"), ("**Whole case**", "total")]],
        "",
        "## Each run", "", "| Case | Candidate | Turns | Overall score | Tokens in / cached / out | Cost |", "|---|---|---|---|---|---|",
        *[f"| {r['case_id']} | {r['quality']} | {r['turns']} | {r['overall']} | {r['total']['input_tokens']:,} / {r['total']['cache_read_tokens']:,} / {r['total']['output_tokens']:,} | ${r['total']['cost_usd']:.4f} |" for r in runs],
        "",
        "## Cost per user and at scale", "",
        f"- **One case:** ${per_case:.4f}. Without prompt caching the same tokens would cost ${per_case_nocache:.4f}, so caching saves {100 * (1 - per_case / per_case_nocache):.0f}% ({100 * cache_share:.0f}% of input tokens were served from cache).",
        f"- **Per user per month:** {CASES_PER_MONTH} cases (3 a week in recruiting season) → **${month:.3f}**.",
        f"- **100 users** (a consulting club): ${month * 100:,.2f} a month.",
        f"- **10,000 users** (several MBA programs): ${month * 10_000:,.0f} a month.",
        f"- **Generating a new case** costs about $0.002 (see `generator_report.md`), and library cases cost $0.",
        f"- **Compared with a human coach:** one 30-minute case with a paid coach is about ${COACH_PRICE_PER_CASE}. "
        f"The app costs ${per_case:.4f}, about {COACH_PRICE_PER_CASE / per_case:,.0f} times cheaper. A classmate costs no money but 30–60 minutes of their time.",
        "", "## What keeps cost down", "",
        "1. **Prompt caching.** Static instructions and the case brief come first, the growing conversation comes last, and there's one cache key per case, so later turns re-read the prefix at 10% of the price.",
        "2. **The opening prompt is read from the case file**, with no model call.",
        "3. **Low reasoning effort** for the Interviewer, Grader and Coach, and short replies (about 90 words).",
        "4. **The Interviewer never holds the whole case**, only topic names, so its prompt stays small.",
        "5. **Hard caps:** 5 model calls and 40K tokens per turn, $0.05 per case, $2 per day (see `safety_results.md`).",
        "6. **Compressed transcript for the Grader** (the experiment below).", "",
        "## Experiment: does a compressed transcript hurt grading?", "",
        "| Case | Grader input, full | Compressed | Saved | Overall A (full) | B (full again) | C (compressed) | Avg score change A→B (randomness) | A→C (compression) |",
        "|---|---|---|---|---|---|---|---|---|",
        *[f"| {e['case_id']} | {e['full_tokens']:,} | {e['compressed_tokens']:,} | {100 * (1 - e['compressed_tokens'] / e['full_tokens']):.0f}% | {e['overall_A']} | {e['overall_B']} | {e['overall_C']} | {e['diff_AB']:.2f} | {e['diff_AC']:.2f} |" for e in exp],
        "",
    ]
    saved = statistics.mean(1 - e["compressed_tokens"] / e["full_tokens"] for e in exp)
    rnd = statistics.mean(e["diff_AB"] for e in exp)
    cmp_ = statistics.mean(e["diff_AC"] for e in exp)
    verdict = ("Compression changed scores about as much as simply grading twice, so it didn't measurably hurt quality."
               if cmp_ <= rnd + 0.25 else "Compression changed scores more than the grader's own randomness, so it does cost some quality.")
    md += [f"**Result:** compression saved {100 * saved:.0f}% of grader input tokens. The average per-dimension score change was {cmp_:.2f} points from compression, "
           f"against {rnd:.2f} points from grading the same transcript twice. {verdict} "
           "Honest caveat: grader input is mostly the cached rubric and answer key, so the dollar saving per case is small.", ""]
    (config.OUTPUT_DIR / "cost_report.md").write_text("\n".join(md))
    (config.OUTPUT_DIR / "cost_report.json").write_text(json.dumps({"avg": avg, "per_case": per_case, "per_case_no_cache": per_case_nocache,
                                                                    "per_user_month": month, "experiment": exp}, indent=1, default=str))
    print("\n".join(md))


def config_prices() -> dict:
    from app.usage import PRICES
    return PRICES


if __name__ == "__main__":
    asyncio.run(main())
