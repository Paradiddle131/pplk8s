"""How often the Haiku judge is right (#429): a stratified blind sample of judged turns, labelled again by a fresh
`claude -p` session on another model, shown the same rubric and never a setup's name.

Run from services/semantic-agent:
  uv run python ../../docs/research/semantic-bet/probes/429_judge_calibration.py sample [--n 60] [--seed 429]
      writes findings/429-judge-calibration/sample.jsonl: the turns, stratified by the judge's verdict and by setup
      family, each with its prompt (built by bet_eval as the judge's was) and the judge's two verdicts.
  uv run python ../../docs/research/semantic-bet/probes/429_judge_calibration.py label [--model sonnet]
      asks the labeller once per sampled turn (bet_eval.claude_judge), appending labels.jsonl; resumes.
  uv run python ../../docs/research/semantic-bet/probes/429_judge_calibration.py report
      prints the agreement, by verdict and by family, and every disagreement.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
OUT = RESEARCH / "findings" / "429-judge-calibration"
sys.path.insert(0, str(RESEARCH.parents[2] / "services/semantic-agent/src"))

from semantic_agent import bet_eval, bet_rule, evaluation

JUDGE = "claude -p (haiku)"


def family(arm: str) -> str:
    """The setup families the report groups by: Google's data agents, our agent on Google's tools, MetricFlow
    setups, the baseline."""
    if arm in ("native-mcp", "custom-toolbox", "cc-native-mcp"):
        return "google-tools"
    if arm.startswith("native-"):
        return "data-agent"
    if arm == "baseline":
        return "baseline"
    return "metricflow"


def candidates() -> list[dict]:
    """Every turn the Haiku judge decided with two equal verdicts, with the prompt it was shown."""
    out = []
    for name in bet_eval.SETS:
        bet = bet_eval.load_set(name)
        questions = {q.id: q for q in bet.questions}
        expected = bet_eval.read_expected(name) or {}
        described = evaluation.definitions(bet.questions)
        verdicts = bet_eval.read_verdicts(bet_eval.JUDGE_LOG, JUDGE, name)
        for e in bet_eval.scored_logs(bet):
            for i, t in enumerate(e.get("turns") or []):
                key = (
                    e["arm"],
                    e["model"],
                    e["case"],
                    e["run"],
                    i,
                    bet_rule.answer_hash(t["text"]),
                )
                got = verdicts.get(key)
                if not got or None in got or got[0] != got[1] or not got[0]:
                    continue
                turn = questions[e["case"]].turns[i]
                if turn.kind == "define":
                    definition = " ".join(described.get(n, n) for n in turn.define)
                    prompt = bet_rule.define_prompt(
                        turn.question, definition, t["text"]
                    )
                else:
                    prompt = bet_rule.judge_prompt(
                        turn.question, expected[e["case"]][i], t["text"]
                    )
                out.append(
                    {"set": name, "arm": e["arm"], "family": family(e["arm"]), "case": e["case"], "run": e["run"],
                     "turn": i, "answer": key[-1], "coded": t["outcome"], "judge": got[0], "prompt": prompt}
                )  # fmt: skip
    return out


def sample(n: int, seed: int) -> int:
    """Stratified by (verdict, family): an equal share for each stratum, the rest drawn at random."""
    pool = candidates()
    strata: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
    for c in pool:
        strata[(c["judge"], c["family"])].append(c)
    rng = random.Random(seed)
    for rows in strata.values():
        rng.shuffle(rows)
    picked: list[dict] = []
    while len(picked) < n and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(picked) < n:
                picked.append(strata[key].pop())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in picked)
    )
    print(
        f"429: {len(picked)} of {len(pool)} judged turns sampled over {len(strata)} strata"
    )
    return 0


def label(model: str) -> int:
    rows = [
        json.loads(line) for line in (OUT / "sample.jsonl").read_text().splitlines()
    ]
    path = OUT / "labels.jsonl"
    done = (
        {json.loads(line)["answer"] for line in path.read_text().splitlines()}
        if path.exists()
        else set()
    )
    ask = bet_eval.claude_judge(model)

    async def run() -> None:
        for r in rows:
            if r["answer"] in done:
                continue
            reply = await ask(r["prompt"])
            verdict = bet_rule.parse_verdict(reply)
            with path.open("a") as f:
                f.write(json.dumps({"answer": r["answer"], "labeller": f"claude -p ({model})",
                                    "label": verdict.value if verdict else None,
                                    "reply": " ".join(reply.split())[-300:]}) + "\n")  # fmt: skip

    asyncio.run(run())
    print(f"429: labels in {path}")
    return 0


def report() -> int:
    rows = {
        json.loads(x)["answer"]: json.loads(x)
        for x in (OUT / "sample.jsonl").read_text().splitlines()
    }
    labels = [json.loads(x) for x in (OUT / "labels.jsonl").read_text().splitlines()]
    by_verdict, by_family = collections.Counter(), collections.Counter()
    agree_v, agree_f = collections.Counter(), collections.Counter()
    diffs = []
    for lab in labels:
        r = rows[lab["answer"]]
        by_verdict[r["judge"]] += 1
        by_family[r["family"]] += 1
        if lab["label"] == r["judge"]:
            agree_v[r["judge"]] += 1
            agree_f[r["family"]] += 1
        else:
            diffs.append((r, lab))
    total = sum(by_verdict.values())
    print(f"agreement: {total - len(diffs)} of {total}")
    for k in sorted(by_verdict):
        print(f"  verdict {k}: {agree_v[k]} of {by_verdict[k]}")
    for k in sorted(by_family):
        print(f"  family {k}: {agree_f[k]} of {by_family[k]}")
    for r, lab in diffs:
        print(f"DIFF {r['set']} {r['arm']} {r['case']} run {r['run']} turn {r['turn'] + 1}: judge {r['judge']}, "
              f"labeller {lab['label']} | {lab['reply'][-200:]}")  # fmt: skip
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--n", type=int, default=60)
    s.add_argument("--seed", type=int, default=429)
    lab = sub.add_parser("label")
    lab.add_argument("--model", default="sonnet")
    sub.add_parser("report")
    a = p.parse_args()
    if a.cmd == "sample":
        return sample(a.n, a.seed)
    if a.cmd == "label":
        return label(a.model)
    return report()


if __name__ == "__main__":
    sys.exit(main())
