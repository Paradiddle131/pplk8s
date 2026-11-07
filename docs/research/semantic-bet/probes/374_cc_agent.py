"""The arm cc-metricflow (#374): a Claude Code subagent (Haiku, Sonnet or Opus on the owner's subscription, no
API credits) answering the bet's questions through the semantic agent's three MetricFlow tools only, called as
`python -m semantic_agent.tool_cli` (audited like the ADK agent's calls).

It is not the ADK agent: the harness is Claude Code's, the subagent is told (not forced) to use only the tool
command, and a batch of cases shares one subagent session, where RULE.md asks a fresh session per run. The report
names it as its own setup for those reasons; it answers "how does the same model do through the same semantic
layer in another agent harness", not the rule's adopt-or-build question.

Two halves, both offline:
  python3 -I docs/research/semantic-bet/probes/374_cc_agent.py --batches frozen|hard RUN SIZE OUT_DIR MODEL
      writes OUT_DIR/<set>-run<RUN>-<n>.json, the cases whose run RUN the log lacks for `claude-code (MODEL)`,
      SIZE cases a batch: each case's id and its turns' questions, never an expected number (SIZE 1: one fresh
      subagent per case, as RULE.md's fresh session per run asks).
  python3 -I docs/research/semantic-bet/probes/374_cc_agent.py --render BATCH_DIR ANSWERS_DIR MODEL
      writes BATCH_DIR/<batch>.prompt.md, 374_cc_prompt.md filled for each batch; a subagent is handed only its path.
  BET_CC_MODEL=<model> BET_CC_ANSWERS=<dir> uv run python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
    --agent 374_cc_agent.py --arm cc-metricflow [--set hard] --runs 3 --no-canary
      (from services/semantic-agent) scores the answers the subagents wrote (<dir>/*.jsonl, one line a case:
      {"case", "run", "turns": [{"question", "answer", "calls"}]}) exactly as a live arm's, into
      eval[-hard]-cc-metricflow.jsonl; a case with no recorded answer is left for a later pass.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
ROOT = RESEARCH.parents[2]
MODEL = f"claude-code ({os.environ.get('BET_CC_MODEL', 'unknown')})"
SETS = {
    "frozen": ("semantic_bet.yaml", "eval-cc-metricflow.jsonl"),
    "hard": ("semantic_bet_hard.yaml", "eval-hard-cc-metricflow.jsonl"),
    "hard-v2": ("semantic_bet_hard_v2.yaml", "eval-hard-v2-cc-metricflow.jsonl"),
}


def questions(name: str) -> list[dict[str, Any]]:
    """The set's cases as the subagent sees them: ids and questions only."""
    import yaml  # the semantic agent's environment has it

    data = yaml.safe_load(
        (ROOT / "services/semantic-agent/evals" / SETS[name][0]).read_text()
    )
    out = []
    for q in data["questions"]:
        turns = q.get("turns") or [q]
        out.append({"id": q["id"], "turns": [t["question"] for t in turns]})
    return out


def batches(name: str, run: int, size: int, out: Path, model: str) -> int:
    log = RESEARCH / SETS[name][1]
    label = f"claude-code ({model})"
    done = set()
    if log.exists():
        for line in log.read_text().splitlines():
            row = json.loads(line)
            if row["model"] == label and row["run"] == run and row.get("outcome"):
                done.add(row["case"])
    todo = [c for c in questions(name) if c["id"] not in done]
    out.mkdir(parents=True, exist_ok=True)
    for n in range(0, len(todo), size):
        path = out / f"{name}-run{run}-{n // size + 1:02d}.json"
        path.write_text(
            json.dumps(
                {"set": name, "run": run, "model": model, "cases": todo[n : n + size]},
                indent=1,
            )
        )
        print(path)
    print(
        f"374_cc_agent: {len(todo)} cases of {name} run {run} in {(len(todo) + size - 1) // size} batches"
    )
    return 0


def scored_runs(label: str) -> set[tuple[str, int]]:
    """The (case, run) pairs both sets' logs already hold for this model."""
    done = set()
    for _, log in SETS.values():
        path = RESEARCH / log
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if row["model"] == label and row.get("outcome"):
                    done.add((row["case"], int(row["run"])))
    return done


def render(batch_dir: Path, answers: Path, model: str) -> int:
    """One prompt per batch file (`<set>-run<R>-<NN>.json`), from 374_cc_prompt.md: the subagent is
    handed only the path of its prompt; its answers go to answers/<model>-<set>-run<R>-<NN>.jsonl."""
    template = (HERE / "374_cc_prompt.md").read_text()
    for batch in sorted(batch_dir.glob("*-run*-*.json")):
        stem = batch.stem
        run = json.loads(batch.read_text())["run"]
        prompt = (
            template.replace("{MODEL}", model)
            .replace("{SESSION}", f"{model}-{stem}")
            .replace("{BATCH}", str(batch))
            .replace("{OUT}", str(answers / f"{model}-{stem}.jsonl"))
            .replace("{RUN}", str(run))
        )
        out = batch.with_suffix(".prompt.md")
        out.write_text(prompt)
        print(out)
    return 0


def recorded() -> dict[str, list[dict[str, Any]]]:
    """Every recorded answer by case, its runs in order."""
    by_case: dict[str, list[dict[str, Any]]] = {}
    # A run already scored stays out: the scorer asks only the missing runs and takes the next answer in
    # line, so a logged run 1 left in would be scored again as run 2.
    scored = scored_runs(MODEL)
    # Only this model's files (<model>-<set>-run<n>-<k>.jsonl): another model's answers never score as its own.
    for path in sorted(
        Path(os.environ["BET_CC_ANSWERS"]).glob(f"{os.environ['BET_CC_MODEL']}-*.jsonl")
    ):
        for line in path.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if (row["case"], row.get("run")) not in scored:
                    by_case.setdefault(row["case"], []).append(row)
    for rows in by_case.values():
        rows.sort(key=lambda r: r.get("run", 0))
    return by_case


def asker(arm: str) -> Callable[[Sequence[str]], Awaitable[list[dict[str, Any]]]]:
    """The runner's `ask`: the next recorded answer of the case whose first question this is."""
    by_case = recorded()
    # By every question of the case: conversation cases open with a single-turn case's question.
    by_turns = {tuple(c["turns"]): c["id"] for name in SETS for c in questions(name)}

    async def ask(qs: Sequence[str]) -> list[dict[str, Any]]:
        case = by_turns.get(tuple(qs))
        rows = by_case.get(case or "", [])
        if not rows:
            return [
                {
                    "question": qs[0],
                    "answer": "",
                    "calls": [],
                    "model_calls": 0,
                    "failure": {
                        "kind": "error",
                        "message": "no recorded answer",
                        "retry_after_s": None,
                    },
                }
            ]
        turns = rows.pop(0)["turns"]
        return [
            {
                "question": q,
                "answer": (turns[i]["answer"] if i < len(turns) else ""),
                "calls": [{"tool": str(c)} for c in (turns[i].get("calls") or [])]
                if i < len(turns)
                else [],
                "model_calls": 1,
            }
            for i, q in enumerate(qs)
        ]

    return ask


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["--batches"] and len(a) == 6:
        raise SystemExit(batches(a[1], int(a[2]), int(a[3]), Path(a[4]), a[5]))
    if a[:1] == ["--render"] and len(a) == 4:
        raise SystemExit(render(Path(a[1]), Path(a[2]), a[3]))
    sys.exit(
        "usage: 374_cc_agent.py --batches frozen|hard RUN SIZE OUT_DIR MODEL"
        " | --render BATCH_DIR ANSWERS_DIR MODEL"
    )
