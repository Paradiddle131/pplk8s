"""The arm cc-metricflow (#374): a Claude Code subagent (Haiku, Sonnet or Opus on the owner's subscription, no
API credits) answering the bet's questions through the semantic agent's three MetricFlow tools only, called as
`python -m semantic_agent.tool_cli` (audited like the ADK agent's calls).

It is not the ADK agent: the harness is Claude Code's, the subagent is told (not forced) to use only the tool
command, and a batch of cases shares one subagent session, where RULE.md asks a fresh session per run. The report
names it as its own setup for those reasons; it answers "how does the same model do through the same semantic
layer in another agent harness", not the rule's adopt-or-build question.

Retired 2026-11-09 (#452): the halves that wrote batches and prompts for subagents are gone, and the script refuses
to run; the strict runner (387_cc_strict.py) asks every Claude Code run. What stays is the agent module that scores
the subagents' recorded answers. The retired halves were:
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


# Retired (owner, 2026-11-09, on #452: "we no longer need to add more runs with subagents"): every Claude Code
# row comes from 387_cc_strict.py; the subagent rows stay in the logs, and no new batch is written or rendered.
RETIRED = "374_cc_agent: the subagent lane is retired; ask Claude Code runs through 387_cc_strict.py"

if __name__ == "__main__":
    sys.exit(RETIRED)
