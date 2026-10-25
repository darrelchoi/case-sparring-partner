"""Problems 3–5: run a whole case in the terminal: interview → scorecard → coach plan.

    python scripts/cli_interview.py brew_bloom
    python scripts/cli_interview.py brew_bloom --script answers.txt   # one candidate line per row (for testing)
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import guards, orchestrator


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_id")
    ap.add_argument("--user", default="cli-tester")
    ap.add_argument("--script", help="file with one candidate message per line")
    args = ap.parse_args()

    s = orchestrator.start_case(args.user, args.case_id)
    print(f"\n== {s.case.title} ==\nINTERVIEWER: {s.case.prompt}\n")
    lines = Path(args.script).read_text().splitlines() if args.script else None

    while True:
        if lines is not None:
            if not lines:
                break
            text = lines.pop(0).strip()
            if not text:
                continue
            print(f"YOU: {text}")
            s.last_turn_at = 0  # scripted runs skip the human rate limit
        else:
            text = input("YOU (or 'done'): ").strip()
            if text.lower() == "done":
                break
        try:
            out = await orchestrator.candidate_turn(s.id, text)
        except guards.Blocked as e:
            print(f"[blocked] {e}\n")
            continue
        for ev in out["events"]:
            print(f"   · {ev}")
        u = out.get("turn_usage", {})
        print(f"INTERVIEWER: {out['reply']}")
        print(f"   [stage {out['state']['stage']} | tokens in {u.get('input_tokens', 0)} (cached {u.get('cache_read_tokens', 0)}) "
              f"out {u.get('output_tokens', 0)} | case cost so far ${out['state']['usage']['cost_usd']:.4f}]\n")
        if out["state"]["closed"]:
            print(out["state"]["close_reason"])
            break

    res = await orchestrator.end_case(s.id)
    card, plan = res["scorecard"], res["coach"]
    print(f"\n== SCORECARD (overall {card['overall']}/5) ==")
    for sc in card["scores"]:
        print(f"  {sc['dimension']:14s} {sc['score']}  {sc['reason']}\n{'':17s}\"{sc['evidence_quote']}\"")
    for m in card["math_results"]:
        print(f"  math {m['math_id']:24s} {m['verdict']:14s} you: {m['candidate_number']}  key: {m['correct_answer']} {m['unit']}")
    for a in card["adjustments"]:
        print(f"  [python adjustment] {a}")
    print(f"\nStrength: {card['top_strength']}\nGap: {card['biggest_gap']}")
    print(f"\n== COACH ==\n{plan['pattern']}\nFocus: {plan['focus_dimension']}\nDrill: {plan['drill']}\nNext case: {plan['next_case_id']} ({plan['next_case_reason']})")
    print(f"\nTotal case cost: ${res['usage']['cost_usd']:.4f}  ({res['usage']['input_tokens']} in, {res['usage']['cache_read_tokens']} cached, {res['usage']['output_tokens']} out)")


if __name__ == "__main__":
    asyncio.run(main())
