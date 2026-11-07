"""Carry a superseded set's runs into the version that supersedes it (RULE.md § Set versions, #378).

A set version (`hard-v2`, `supersedes: hard`) keeps the cases of the set it supersedes whose scoring
inputs are unchanged; their runs need not be asked again. This copies, for each such case:

- every run of every arm's log of the old set (`eval-hard-<arm>.jsonl`, `eval-hard-local.jsonl`)
  into the new set's log of the same arm (`eval-hard-v2-<arm>.jsonl`, `eval-hard-v2-local.jsonl`);
- every blind-judge verdict on those runs (`judge.jsonl`, keyed by set) as the new set's.

Each copied row carries `carried_from: <old set>` and `case_hash`, the SHA-256 of the case's
scoring inputs (its question turns, expected SQL and metrics as the set file parses them, the set's
hedges and the eval's tolerance). A case whose hash differs between the two files is refused: none
of its rows is copied, it is named, and the exit code is 1. A row already in the new set's log (the
same arm, model, case and run) is never copied again, so a second carry copies only what the old
set's logs gained since (a lane runs it before every pass on the new set). Rows are appended; no
log line is rewritten or removed, the old set's least of all.

Usage (from services/semantic-agent):
  uv run python -m semantic_agent.bet_carry [--to hard-v2] [--dry-run]
Exit 0: carried (or nothing new); 1: a case was refused; 2: the set names no `supersedes`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from semantic_agent.bet_eval import JUDGE_LOG, RESEARCH, SETS, read_log

# The eval's tolerance (evaluation.carries): within half a cent; part of what scores a turn.
TOLERANCE = 0.006


def case_hash(case: Mapping[str, Any], hedges: Sequence[str]) -> str:
    """The SHA-256 of what scores a case's runs: the case as the set file parses it (its turns'
    questions, expected SQL and metrics), the set's hedge phrases and the eval's tolerance."""
    payload = {"case": case, "hedges": list(hedges), "tolerance": TOLERANCE}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def case_hashes(path: Path) -> dict[str, str]:
    spec = yaml.safe_load(path.read_text())
    return {case["id"]: case_hash(case, spec["hedges"]) for case in spec["questions"]}


@dataclass
class Carry:
    """What one carry did: rows copied per log, the cases carried and the cases refused."""

    source: str
    target: str
    copied: dict[str, int] = field(default_factory=dict)
    verdicts: int = 0
    carried: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)


def _run_key(row: Mapping[str, Any]) -> tuple:
    return (row.get("arm"), row.get("model"), row.get("case"), row.get("run"))


def _append(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if rows:
        with path.open("a") as out:
            out.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def carry(target: str, directory: Path = RESEARCH, dry_run: bool = False) -> Carry:
    """Copy the superseded set's runs and verdicts of every unchanged case into `target`'s logs."""
    files = SETS[target]
    source = yaml.safe_load(files.questions.read_text()).get("supersedes")
    if source not in SETS:
        raise LookupError(f"{target} names no set it supersedes")
    old = SETS[source]
    old_hashes, new_hashes = case_hashes(old.questions), case_hashes(files.questions)
    result = Carry(source, target)
    for case in old_hashes:
        if case not in new_hashes:
            continue
        if old_hashes[case] == new_hashes[case]:
            result.carried.append(case)
        else:
            result.refused.append(case)
    carried = set(result.carried)
    # The old set's own logs: its prefix, but not a longer prefix another set owns (eval-hard-v2-).
    others = [s.prefix for s in SETS.values() if s.prefix != old.prefix]
    others = [p for p in others if p.startswith(old.prefix)]
    for path in sorted(directory.glob(f"{old.prefix}*.jsonl")):
        if any(path.name.startswith(p) for p in others):
            continue
        dest = directory / (files.prefix + path.name.removeprefix(old.prefix))
        have = {_run_key(r) for r in read_log(dest)}
        rows = []
        for row in read_log(path):
            if row.get("case") not in carried or _run_key(row) in have:
                continue
            have.add(_run_key(row))
            rows.append({**row, "carried_from": source, "case_hash": new_hashes[row["case"]]})
        if rows:
            result.copied[dest.name] = len(rows)
            if not dry_run:
                _append(dest, rows)
    judge = directory / JUDGE_LOG.name
    rows_all = read_log(judge)

    def key(r: Mapping[str, Any]) -> tuple:
        return (r["judge"], *_run_key(r), r["turn"], r["answer"], r["n"])

    have = {key(r) for r in rows_all if r.get("set") == target}
    verdicts = []
    for row in rows_all:
        if row.get("set") != source or row.get("case") not in carried or key(row) in have:
            continue
        have.add(key(row))
        verdicts.append(
            {**row, "set": target, "carried_from": source, "case_hash": new_hashes[row["case"]]}
        )
    result.verdicts = len(verdicts)
    if not dry_run:
        _append(judge, verdicts)
    return result


def verify(target: str, directory: Path = RESEARCH) -> list[str]:
    """Every carried row in `target`'s logs whose `case_hash` no longer matches its case: empty
    when the logs hold only runs of the cases as the set file scores them."""
    files = SETS[target]
    hashes = case_hashes(files.questions)
    bad = []
    others = [s.prefix for s in SETS.values() if s.prefix != files.prefix]
    others = [p for p in others if p.startswith(files.prefix)]
    for path in sorted(directory.glob(f"{files.prefix}*.jsonl")):
        if any(path.name.startswith(p) for p in others):
            continue
        for row in read_log(path):
            if row.get("carried_from") and row.get("case_hash") != hashes.get(row.get("case")):
                bad.append(f"{path.name}: {row.get('case')} run {row.get('run')}")
    return bad


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--to", dest="target", default="hard-v2", choices=list(SETS))
    parser.add_argument("--dry-run", action="store_true", help="count, write nothing")
    args = parser.parse_args(argv)
    try:
        result = carry(args.target, dry_run=args.dry_run)
    except LookupError as error:
        print(f"bet_carry: {error}", file=sys.stderr)
        return 2
    rows = sum(result.copied.values())
    print(
        f"bet_carry: {result.source} -> {result.target}: {len(result.carried)} cases carried, "
        f"{rows} runs and {result.verdicts} verdicts copied"
        + (" (dry run)" if args.dry_run else "")
    )
    for name, n in result.copied.items():
        print(f"  {name}: {n}")
    if result.refused:
        print(f"bet_carry: refused (scoring inputs differ): {', '.join(result.refused)}")
        return 1
    bad = [] if args.dry_run else verify(args.target)
    if bad:
        print("bet_carry: carried rows whose hash differs:\n  " + "\n  ".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
