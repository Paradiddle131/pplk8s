"""A probe arm live on the frozen set: probes/328_mcp_agent.py on Google's MCP servers (`native-mcp`, #328, Q3),
or with `--agent 330_toolbox_agent.py` the generated Toolbox tools (`custom-toolbox`, #330).

What it measures: per case and run, every turn of the conversation in one session (semantic_agent.bet_live),
each turn's tool calls on the arm's MCP servers (does it search the dbt metrics, read their definitions, try
`compile_query`, or write its own SQL), its answer, and the turn's and run's outcome under RULE.md
(bet_eval.score_case, the expected numbers from the Compose warehouse's dbt_dev, as the local arms take them).
Appends one JSON line per finished run to `docs/research/semantic-bet/eval-<arm>.jsonl` (or `--out`) in
eval-local.jsonl's shape and resumes from it: a run already logged is never asked again. Then rewrites
`docs/research/semantic-bet/eval.md` from every arm's log.
The free tier's requests are shared with other scheduled runs: give a pass `--requests` (model responses) and
`--minutes`; a spent daily quota or a refused key ends it, any other failed model call leaves that run for a
later pass.

Env: the agent probe's (`GCP_PROJECT`, the endpoints, `BET_MCP_TOKEN`, `BET_SQL_DENY`), the model's (`MODEL_ID`),
and the expected numbers' warehouse (`WAREHOUSE_OWNER_URL`, `DBT_DBNAME=dbt_dev`; needs `make services-up` and
the agents' fixture). Live: run `make gcp-cost-check` and `make gcp-usage-check` before and after.
Run from services/semantic-agent:
  DBT_DBNAME=dbt_dev uv run python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
    [--agent 330_toolbox_agent.py] [--arm <name>] [--runs 3] [--requests 300] [--minutes 35] [case id...]
Exit 0: every run of every case asked is logged; 3: the pass stopped short (quota, budget, time).
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import os
import sys
import time
from pathlib import Path

from semantic_agent import evaluation
from semantic_agent.bet_eval import ALL_REPORT, RUNS, load_bet, read_logs, report
from semantic_agent.bet_live import converse, log_path, run_live
from semantic_agent.model import DEFAULT_MODEL_ID

# Each agent probe's arm in RULE.md.
ARMS = {"328_mcp_agent.py": "native-mcp", "330_toolbox_agent.py": "custom-toolbox"}


def _agent_module(name: str):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location("bet_probe_agent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--agent",
        default="328_mcp_agent.py",
        choices=sorted(ARMS),
        help="the probe beside this one whose build_agent() answers",
    )
    parser.add_argument(
        "--arm", help="the arm's name in the logs (default: the agent's arm in RULE.md)"
    )
    parser.add_argument("--out", type=Path, help="the log (default: eval-<arm>.jsonl)")
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument(
        "--requests", type=int, help="stop once this pass spent this many"
    )
    parser.add_argument("--minutes", type=float, help="stop asking after this long")
    parser.add_argument(
        "ids", nargs="*", help="only these cases (default: the whole set)"
    )
    args = parser.parse_args()

    arm = args.arm or ARMS[args.agent]
    log = args.out or log_path(arm)
    bet = load_bet(ids=args.ids)
    database = os.environ.get("DBT_DBNAME", "dbt_dev")
    # The eval's owner role, as bet_eval takes the expected numbers (expected_sql reads silver too).
    url = os.environ.get(
        "WAREHOUSE_OWNER_URL",
        f"postgresql://warehouse:warehouse@localhost:5433/{database}",
    )
    expected = evaluation.expected_numbers(bet.questions, url)
    described = evaluation.definitions(bet.questions)
    agent = _agent_module(args.agent)
    model = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
    deadline = time.monotonic() + 60 * args.minutes if args.minutes else None

    async def ask(questions):
        return await converse(agent.build_agent(), questions)

    why = await run_live(
        bet,
        expected,
        described,
        arm,
        ask,
        model,
        args.runs,
        log,
        deadline,
        args.requests,
    )
    print(f"stopped: {why}; logged to {log}", flush=True)
    ALL_REPORT.write_text(report(load_bet(), read_logs(), args.runs, every_arm=True))
    print(f"every arm: written to {ALL_REPORT}")
    return 0 if why == "done" else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
