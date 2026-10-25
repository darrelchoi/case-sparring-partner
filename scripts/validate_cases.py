"""Problem 2: check every case file. Loads each through the schema and recomputes every math answer in Python.

    python scripts/validate_cases.py              # library + generated cases
    python scripts/validate_cases.py path/to.json # one file
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError

from app.cases import check_case, load_case_file
from app.config import CASES_DIR, GENERATED_DIR


def main() -> int:
    paths = [Path(p) for p in sys.argv[1:]] or sorted(CASES_DIR.glob("*.json")) + sorted(GENERATED_DIR.glob("*.json"))
    bad = 0
    for p in paths:
        try:
            case = load_case_file(p)
        except (ValidationError, json.JSONDecodeError) as e:
            print(f"FAIL  {p.name}: does not match the schema\n      {str(e).splitlines()[0]}")
            bad += 1
            continue
        problems = check_case(case)
        if problems:
            bad += 1
            print(f"FAIL  {p.name}")
            for pr in problems:
                print(f"      - {pr}")
        else:
            print(f"ok    {p.name:28s} {case.case_type:14s} {len(case.hidden_facts)} facts, {len(case.math_answers)} math checks")
    total = len(paths)
    print(f"\n{total - bad}/{total} valid" + (", all math checks pass." if not bad else "."))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
