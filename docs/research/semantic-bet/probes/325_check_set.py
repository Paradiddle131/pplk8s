"""Check the bet's frozen set on the fixture: every expected number exists, and every trap and distractor bites.

Measures: for each case of a bet set (services/semantic-agent/evals/semantic_bet.yaml, or the set the first
argument names, e.g. semantic_bet_hard.yaml, #356), every turn's expected SQL on dbt_dev (each column, one meaning
of an ambiguous turn each), and for a `trap` its naive SQL's first value, for a `distractor` its legacy SQL's;
fails when an expected value is empty, an ambiguous turn's meanings agree within the eval's tolerance (0.006), or a
trap's or distractor's value is within that tolerance of the first turn's expected one.
Run (from the repo root), after tests/e2e/agent-fixture.sh and the legacy models built in dbt_dev
(`dbt run --select path:models/legacy` as autopilot.md § Gates runs dbt):
  python3 -I docs/research/semantic-bet/probes/325_check_set.py [services/semantic-agent/evals/<set>.yaml]
Offline: reads the Compose warehouse (`docker exec pplk8s-warehouse-1 psql`), writes nothing; needs PyYAML
(`uv run --with pyyaml python ...` when python3 has none).
"""

import subprocess
import sys
from pathlib import Path

import yaml

SET = Path("services/semantic-agent/evals/semantic_bet.yaml")
TOLERANCE = 0.006


def row(sql: str) -> list[str]:
    cmd = [
        "docker",
        "exec",
        "pplk8s-warehouse-1",
        "psql",
        "-U",
        "warehouse",
        "-d",
        "dbt_dev",
        "-At",
        "-c",
        sql,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip()
    return out.split("\n")[0].split("|")


def value(sql: str) -> str:
    return row(sql)[0]


def check_turn(cid: str, turn: dict, failures: list[str]) -> list[str]:
    """A turn's expected values, one per column; records an empty one, or meanings that agree."""
    values = row(turn["expected_sql"])
    if any(v == "" for v in values):
        failures.append(f"{cid}: no expected value")
    if turn.get("ambiguous") and len(values) > 1 and "" not in values:
        numbers = [float(v) for v in values]
        if any(
            abs(a - b) <= TOLERANCE
            for i, a in enumerate(numbers)
            for b in numbers[i + 1 :]
        ):
            failures.append(f"{cid}: two meanings give the same number")
    return values


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else SET
    spec = yaml.safe_load(path.read_text())
    groups, failures = spec["groups"], []
    print("case\tgroups\texpected\tnaive\tlegacy")
    for case in spec["questions"]:
        cid = case["id"]
        turns = [t for t in case.get("turns") or [case] if t.get("expected_sql")]
        if not turns:
            continue
        values = [check_turn(cid, t, failures) for t in turns]
        expected = values[0][0]
        naive = value(spec["naive_sql"][cid]) if cid in spec["naive_sql"] else ""
        legacy = value(spec["legacy_sql"][cid]) if cid in spec["legacy_sql"] else ""
        shown = " / ".join(",".join(v) for v in values)
        print(f"{cid}\t{','.join(groups[cid])}\t{shown}\t{naive}\t{legacy}")
        for name, other in (("naive", naive), ("legacy", legacy)):
            if other and expected and abs(float(other) - float(expected)) <= TOLERANCE:
                failures.append(f"{cid}: {name} gives the expected number")
    cases = len(spec["questions"])
    uncovered = sum("uncovered" in g for g in groups.values())
    share = 100 * uncovered / cases
    print(
        f"cases {cases}, uncovered {uncovered} ({share:.1f}%), traps {len(spec['naive_sql'])}"
    )
    print(f"distractors {len(spec['legacy_sql'])}, failures {len(failures)}")
    print("\n".join(failures), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
