#!/usr/bin/env python3
"""#380: hard-v2 against v1 on RULE.md's four pre-registered criteria (§ Set versions), from the scored data.

Reads only what the report reads (scored-runs.jsonl and results.json: retirements, redactions, label
corrections and the judge's verdicts already applied by bet_eval) plus the set files for kinds and the
naive SQL; standard library only, the statistics are report/build.py's (seeded percentile bootstrap over
cases, the exact Clopper-Pearson bound when every case's share is 0 or 1).

  python3 -I docs/research/semantic-bet/probes/380_compare.py [--whole]

Prints Markdown: each criterion with its numbers, intervals and pass or fail; the coverage each number
rests on (cases reached and runs a case against k = 3); v1 against v2 per group and per arm; and the
exploratory `sql_hard` result against the floor. Without --whole it labels itself provisional whenever
an arm a criterion reads is not whole at k = 3 on hard-v2, and never states a verdict on that criterion.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
SETS_DIR = RESEARCH.parents[2] / "services/semantic-agent/evals"
SET_FILES = {
    "frozen": "semantic_bet.yaml",
    "hard": "semantic_bet_hard.yaml",
    "hard-v2": "semantic_bet_hard_v2.yaml",
}
K = 3

spec = importlib.util.spec_from_file_location("build", RESEARCH / "report/build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)  # type: ignore[union-attr]

FREE = "nvidia/nemotron-3.5-super-vl:free"
MANAGED_BEST = (
    "native-context-bare",
    "google-data-agent (MODEL_UNSPECIFIED, THINKING)",
)
FLOOR = ("native-bare", "google-data-agent (MODEL_UNSPECIFIED)")
METRICFLOW = ("custom-metricflow", FREE)
# Pre-registered (RULE.md § Set versions, 2026-11-06T09:18Z), word for word in the thresholds.
C2_MAX = 0.85
C3_FROZEN_STATED = 0.38
C4_GAP = 0.15


def kinds_of(setname: str) -> dict[str, list[str]]:
    """The `kinds:` map of a set file (no YAML library): case -> its kinds."""
    lines = (SETS_DIR / SET_FILES[setname]).read_text().split("\n")
    if "kinds:" not in lines:
        return {}
    out: dict[str, list[str]] = {}
    i = lines.index("kinds:") + 1
    while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
        ln = lines[i].strip()
        if ":" in ln and not ln.startswith("-"):
            case, rest = ln.split(":", 1)
            out[case] = [
                k.strip() for k in rest.strip().strip("[]").split(",") if k.strip()
            ]
        i += 1
    return out


def per_case(rows: list[dict]) -> dict[str, list[str]]:
    pc: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r.get("outcome"):
            pc[r["case"]].append(r["outcome"])
    return pc


def acc(
    pc: dict[str, list[str]], cases: list[str], what: str = "right", seed: int = 325
):
    """Mean over the cases reached of the share of runs that are `what`, its interval, and coverage."""
    reached = [c for c in cases if c in pc]
    vals = [build.share(pc[c], what) for c in reached]
    iv = build.boot(vals, seed)
    ex = build.exact(iv, len(reached)) if iv else None
    runs = sum(len(pc[c]) for c in reached)
    return {
        "mean": iv[0] if iv else None,
        "lo": (ex or iv[1:])[0] if iv else None,
        "hi": (ex or iv[1:])[1] if iv else None,
        "exact": bool(ex),
        "reached": len(reached),
        "of": len(cases),
        "runs": runs,
        "whole": len(reached) == len(cases) and all(len(pc[c]) >= K for c in reached),
    }


def pct(x) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def fmt(a: dict) -> str:
    if a["mean"] is None:
        return f"no runs (0 of {a['of']} cases)"
    band = "exact 95%" if a["exact"] else "95%"
    k = "" if a["whole"] else ", not whole at k = 3"
    return f"{pct(a['mean'])} [{band} {pct(a['lo'])}, {pct(a['hi'])}] on {a['reached']} of {a['of']} cases, {a['runs']} runs{k}"


def verdict(ok: bool, *arms: dict) -> str:
    if not all(a["whole"] for a in arms):
        return (
            "**provisional** ("
            + ("would pass" if ok else "would fail")
            + " on the runs so far)"
        )
    return "**pass**" if ok else "**fail**"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--whole",
        action="store_true",
        help="refuse unless every arm a criterion reads is whole at k = 3",
    )
    args = ap.parse_args()

    R = json.loads((RESEARCH / "results.json").read_text())
    scored = build.load_scored(str(RESEARCH / "scored-runs.jsonl"))
    sets = R["sets"]
    v2 = sets["hard-v2"]
    groups2 = v2["groups"]
    new = (
        [c for c in v2["new"] if c in v2["cases"]]
        if isinstance(v2["new"], list)
        else []
    )
    if not new:
        new = [c for c in v2["cases"] if c.startswith("hv2_")]
    new_unc = [c for c in new if "uncovered" in groups2.get(c, [])]
    new_both = [c for c in new if build.bucket(groups2.get(c, [])) == "uncovered"]
    v2_both = [
        c for c in v2["cases"] if build.bucket(groups2.get(c, [])) == "uncovered"
    ]
    fz = sets["frozen"]
    fz_unc = [
        c for c in fz["cases"] if build.bucket(fz["groups"].get(c, [])) == "uncovered"
    ]

    def pc(setname, key):
        return per_case(scored.get((setname, key[0], key[1]), []))

    out = []
    w = out.append
    w(f"## #380 readout from results.json written {R.get('written', '?')}")
    w("")
    w(
        f"- hard-v2 as scored: {len(v2['cases'])} cases, {len(new)} of them new; the new cases' groups: "
        f"{sum(1 for c in new if 'uncovered' in groups2.get(c, []))} `uncovered`, "
        f"{sum(1 for c in new if 'composable' in groups2.get(c, []))} `composable`, "
        f"{sum(1 for c in new if build.bucket(groups2.get(c, [])) != 'uncovered')} `covered`."
    )
    w(
        '- RULE.md reads "`uncovered` case" on hard-v2 as `composable` or `uncovered`; criterion 2 names "new `uncovered` cases", '
        "so it is read both ways below, the narrow reading (the `uncovered` group alone) first."
    )
    w("")

    # 1. Agent-independent.
    k2 = kinds_of("hard-v2")
    missing_kind = [c for c in new if not k2.get(c)]
    w("### 1. Every new case's naive SQL misses, and each carries a rubric kind")
    w("")
    w(
        f"- Rubric kinds: {len(new) - len(missing_kind)} of {len(new)} new cases carry one"
        + (f"; missing: {', '.join(missing_kind)}" if missing_kind else "")
        + "."
    )
    w(
        "- Naive SQL against expected: `probes/325_check_set.py` on the frozen file gave `failures 0` at the freeze "
        "(findings/2026-11-06-377-hard-set-v2.md); rerun it on the fixture to restate it here."
    )
    w("")

    # 2. The best SQL writer is off the ceiling.
    mb = pc("hard-v2", MANAGED_BEST)
    a_narrow, a_both = acc(mb, new_unc), acc(mb, new_both)
    w("### 2. The managed best is right on at most 85% of the new `uncovered` cases")
    w("")
    w(
        f"- `{MANAGED_BEST[0]}` on {MANAGED_BEST[1]}, new `uncovered` only: {fmt(a_narrow)}: "
        + verdict(a_narrow["mean"] is not None and a_narrow["mean"] <= C2_MAX, a_narrow)
        + "."
    )
    w(
        f"- New `composable` or `uncovered`: {fmt(a_both)}: "
        + verdict(a_both["mean"] is not None and a_both["mean"] <= C2_MAX, a_both)
        + "."
    )
    w("")

    # 3. The inversion is gone.
    mf2, mf1 = pc("hard-v2", METRICFLOW), pc("frozen", METRICFLOW)
    a_v2, a_fz = acc(mf2, v2_both), acc(mf1, fz_unc)
    a_v2n = acc(mf2, [c for c in v2["cases"] if "uncovered" in groups2.get(c, [])])
    w(
        "### 3. `custom-metricflow` on the free model answers fewer of v2's `uncovered` cases than of the frozen set's"
    )
    w("")
    w(
        f"- hard-v2, `composable` or `uncovered` (RULE.md's reading on this set): {fmt(a_v2)}."
    )
    w(f"- hard-v2, the `uncovered` group alone: {fmt(a_v2n)}.")
    w(
        f"- Frozen set's `uncovered`, as scored now: {fmt(a_fz)}; as stated in the criterion: {pct(C3_FROZEN_STATED)}."
    )
    # The frozen figure is the comparison point, not a run under test: only hard-v2's arm must be whole.
    if a_v2["mean"] is None or a_fz["mean"] is None:
        w("- No verdict: an arm has no runs.")
    else:
        ok_stated, ok_now = a_v2["mean"] < C3_FROZEN_STATED, a_v2["mean"] < a_fz["mean"]
        if ok_stated == ok_now:
            w(
                "- Against the stated 38% and the frozen set as scored now alike: "
                + verdict(ok_stated, a_v2)
                + "."
            )
        else:
            w(
                f"- Split: {'passes' if ok_stated else 'fails'} against the stated 38%, {'passes' if ok_now else 'fails'} against the frozen set as "
                f"scored now ({pct(a_fz['mean'])}, after #382's rescoring); the owner reads which comparison the criterion meant"
                + (
                    ""
                    if a_v2["whole"]
                    else ", and hard-v2's arm is not yet whole at k = 3"
                )
                + "."
            )
    w("")

    # 4. The floor feels it.
    fl = pc("hard-v2", FLOOR)
    a_fl, a_mb = acc(fl, new), acc(mb, new)
    d = build.paired(mb, fl, new, "right", 325)
    w(
        "### 4. The bare data agent is at least 15 points below the managed best on the new cases"
    )
    w("")
    w(f"- Managed best on the new cases: {fmt(a_mb)}.")
    w(f"- Floor `{FLOOR[0]}` on the new cases: {fmt(a_fl)}.")
    if d:
        w(
            f"- Paired by case, managed best minus floor: {100 * d[0]:+.1f} points [95% {100 * d[1]:+.1f}, {100 * d[2]:+.1f}] on {d[3]} cases: "
            + verdict(d[0] >= C4_GAP, a_fl, a_mb)
            + "."
        )
    w("")

    # v1 against v2, per group and arm.
    w(
        "### v1 against v2, per arm and group (right; `hard` as scored, `hard-v2` all cases and its new ones)"
    )
    w("")
    w(
        "| Arm | Model | hard (v1) | hard-v2 | hard-v2 new | hard-v2 new `uncovered` or `composable` | v2 new runs a case |"
    )
    w("|---|---|---|---|---|---|---|")
    keys = sorted({(a, m) for (s, a, m) in scored if s == "hard-v2"})
    for a, m in keys:
        p1, p2 = pc("hard", (a, m)), pc("hard-v2", (a, m))
        r1, r2, rn, ru = (
            acc(p1, sets["hard"]["cases"]),
            acc(p2, v2["cases"]),
            acc(p2, new),
            acc(p2, new_both),
        )
        runs = (rn["runs"] / rn["reached"]) if rn["reached"] else 0
        w(
            f"| `{a}` | {m} | {pct(r1['mean'])} | {pct(r2['mean'])} | {pct(rn['mean'])} ({rn['reached']}/{rn['of']}) | {pct(ru['mean'])} | {runs:.1f} |"
        )
    w("")
    w("| Group | hard (v1) cases | hard-v2 cases | hard-v2 new |")
    w("|---|---|---|---|")
    for g in ("covered", "trap", "composable", "uncovered", "conversation"):
        n1 = sum(
            1 for c in sets["hard"]["cases"] if g in sets["hard"]["groups"].get(c, [])
        )
        n2 = sum(1 for c in v2["cases"] if g in groups2.get(c, []))
        nn = sum(1 for c in new if g in groups2.get(c, []))
        w(f"| `{g}` | {n1} | {n2} | {nn} |")
    w("")

    # Exploratory: sql_hard against the floor.
    sh = [c for c in v2["cases"] if "sql_hard" in k2.get(c, [])]
    w(
        f"### Exploratory: the `sql_hard` cases ({len(sh)} as scored), each arm paired against the floor (no pass or fail)"
    )
    w("")
    w("| Arm | Model | right | minus the floor, paired | runs |")
    w("|---|---|---|---|---|")
    for a, m in keys:
        p = pc("hard-v2", (a, m))
        r = acc(p, sh)
        dd = build.paired(p, fl, sh, "right", 325)
        ds = (
            f"{100 * dd[0]:+.1f} [{100 * dd[1]:+.1f}, {100 * dd[2]:+.1f}] on {dd[3]}"
            if dd
            else "n/a"
        )
        w(
            f"| `{a}` | {m} | {pct(r['mean'])} ({r['reached']}/{r['of']}) | {ds} | {r['runs']} |"
        )
    w("")
    whole = all(x["whole"] for x in (a_narrow, a_both, a_v2, a_fl, a_mb))
    w(
        "Every arm the criteria read is whole at k = 3."
        if whole
        else "Provisional: an arm a criterion reads is not whole at k = 3 on hard-v2 (#379); no criterion is judged here."
    )
    if args.whole and not whole:
        print("\n".join(out))
        print(
            "380_compare: --whole given, but an arm is not whole at k = 3",
            file=sys.stderr,
        )
        return 3
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
