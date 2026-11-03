"""Check the bet's frozen set on the fixture: every expected number exists, and every trap and distractor bites.

Measures: for each case of services/semantic-agent/evals/semantic_bet.yaml, its expected SQL's first value on
dbt_dev, and for a `trap` its naive SQL's, for a `distractor` its legacy SQL's; fails when an expected value is
empty or a trap's or distractor's value is within the eval's tolerance (0.006) of the expected one.
Run (from the repo root), after tests/e2e/agent-fixture.sh and the legacy models built in dbt_dev
(`dbt run --select path:models/legacy` as autopilot.md § Gates runs dbt):
  python3 -I docs/research/semantic-bet/probes/325_check_set.py
Offline: reads the Compose warehouse (`docker exec pplk8s-warehouse-1 psql`), writes nothing; needs PyYAML
(`uv run --with pyyaml python ...` when python3 has none).
"""

import subprocess
import sys
from pathlib import Path

import yaml

SET = Path("services/semantic-agent/evals/semantic_bet.yaml")
TOLERANCE = 0.006


def value(sql: str) -> str:
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
    return out.split("|")[0].split("\n")[0]


def first_sql(case: dict) -> str | None:
    turn = (case.get("turns") or [case])[0]
    return turn.get("expected_sql")


def main() -> int:
    spec = yaml.safe_load(SET.read_text())
    groups, failures = spec["groups"], []
    print("case\tgroups\texpected\tnaive\tlegacy")
    for case in spec["questions"]:
        cid, sql = case["id"], first_sql(case)
        if sql is None:
            continue
        expected = value(sql)
        naive = value(spec["naive_sql"][cid]) if cid in spec["naive_sql"] else ""
        legacy = value(spec["legacy_sql"][cid]) if cid in spec["legacy_sql"] else ""
        print(f"{cid}\t{','.join(groups[cid])}\t{expected}\t{naive}\t{legacy}")
        if expected == "":
            failures.append(f"{cid}: no expected value")
        for name, other in (("naive", naive), ("legacy", legacy)):
            if other and abs(float(other) - float(expected)) <= TOLERANCE:
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
