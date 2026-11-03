"""A probe arm live on one of the bet's sets (the frozen one, or `--set hard`, #364): probes/328_mcp_agent.py on Google's MCP servers (`native-mcp`, #328, Q3),
with `--agent 330_toolbox_agent.py` the generated Toolbox tools (`custom-toolbox`, #330), with
`--agent 363_lightdash_agent.py` Lightdash's free query API (`custom-lightdash`, #363), or with
`--agent 354_data_agent.py --arm <arm>` a data-agent arm (#354).

What it measures: per case and run, every turn of the conversation in one session (semantic_agent.bet_live),
each turn's tool calls on the arm's MCP servers (does it search the dbt metrics, read their definitions, try
`compile_query`, or write its own SQL), its answer, and the turn's and run's outcome under RULE.md
(bet_eval.score_case, the expected numbers from the Compose warehouse's dbt_dev, as the local arms take them).
Appends one JSON line per finished run to `docs/research/semantic-bet/eval-<arm>.jsonl` (on the hard set
`eval-hard-<arm>.jsonl`; or `--out`) in eval-local.jsonl's shape and resumes from it: a run already logged is
never asked again. Then rewrites `docs/research/semantic-bet/eval.md` from every arm's log, one section per set.
The free tier's requests are shared with other scheduled runs: give a pass `--requests` (model responses) and
`--minutes`; a spent daily quota or a refused key ends it, any other failed model call leaves that run for a
later pass.

Env: the agent probe's (`GCP_PROJECT`, the endpoints, `BET_MCP_TOKEN`, `BET_SQL_DENY`), the model's (`MODEL_ID`),
and the expected numbers' warehouse (`WAREHOUSE_OWNER_URL`, `DBT_DBNAME=dbt_dev`; needs `make services-up` and
the agents' fixture). Live: run `make gcp-cost-check` and `make gcp-usage-check` before and after.
Run from services/semantic-agent:
  DBT_DBNAME=dbt_dev uv run python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
    [--agent 330_toolbox_agent.py] [--arm <name>] [--set hard] [--runs 3] [--requests 300] [--minutes 35] \
    [case id...]
On Claude (`MODEL_BACKEND=anthropic`, #361, #365) a pass takes `--dollars` (its budget) and `--label` (its row in the
spend ledger): it opens the pass with `spend.METER.start`, stops before a case-run that would cross the budget, and
closes it with `spend.finish_pass`, which appends the row and the anomaly checks; without `BET_ANTHROPIC_API_KEY`
it is skipped with that reason (exit 3).
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

from semantic_agent import evaluation, spend
from semantic_agent.bet_eval import FROZEN, RUNS, SETS, load_set, write_every_arm
from semantic_agent.bet_live import converse, log_path, run_live
from semantic_agent.model import DEFAULT_MODEL_ID, MissingKey, claude_key

# Each agent probe's arm in RULE.md.
ARMS = {
    "328_mcp_agent.py": "native-mcp",
    "330_toolbox_agent.py": "custom-toolbox",
    "363_lightdash_agent.py": "custom-lightdash",
    "354_data_agent.py": "native-kc",  # or --arm <any of its AGENTS>
}


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
    parser.add_argument(
        "--set",
        dest="which",
        default=FROZEN,
        choices=list(SETS),
        help="the set asked (default: the frozen set)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        help="the log (default: eval-<arm>.jsonl, eval-hard-<arm>.jsonl)",
    )
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument(
        "--requests", type=int, help="stop once this pass spent this many"
    )
    parser.add_argument("--minutes", type=float, help="stop asking after this long")
    parser.add_argument(
        "--dollars", type=float, help="a Claude pass's budget in USD (spend.py)"
    )
    parser.add_argument("--label", help="the pass's name in the spend ledger")
    parser.add_argument(
        "ids", nargs="*", help="only these cases (default: the whole set)"
    )
    args = parser.parse_args()

    arm = args.arm or ARMS[args.agent]
    claude = os.environ.get("MODEL_BACKEND", "openrouter") == "anthropic"
    if claude:
        try:
            claude_key()
        except MissingKey as missing:
            print(f"skipped: {missing}")
            return 3
    log = args.out or log_path(arm, name=args.which)
    bet = load_set(args.which, args.ids)
    database = os.environ.get("DBT_DBNAME", "dbt_dev")
    # The eval's owner role, as bet_eval takes the expected numbers (expected_sql reads silver too).
    url = os.environ.get(
        "WAREHOUSE_OWNER_URL",
        f"postgresql://warehouse:warehouse@localhost:5433/{database}",
    )
    expected = evaluation.expected_numbers(bet.questions, url)
    described = evaluation.definitions(bet.questions)
    agent = _agent_module(args.agent)
    # A probe whose agent answers with a model of its own (a data agent) names it; the others take MODEL_ID's.
    model = getattr(agent, "MODEL", None) or os.environ.get(
        "MODEL_ID", DEFAULT_MODEL_ID
    )
    deadline = time.monotonic() + 60 * args.minutes if args.minutes else None

    async def converse_fresh(questions):
        return await converse(agent.build_agent(), questions)

    # A data-agent probe answers through its own chat API; an ADK probe through bet_live.converse.
    ask = agent.asker(arm) if hasattr(agent, "asker") else converse_fresh

    if claude:
        spend.METER.start(
            args.label
            or f"{model} {arm}" + ("" if args.which == FROZEN else f" {args.which}"),
            args.dollars,
        )
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
    if claude:
        found = spend.finish_pass(note=f"stopped: {why}")
        usage = spend.total(u for _, u in spend.METER.pass_calls)
        print("ANOMALIES: " + ("; ".join(found) if found else "none"))
        print(
            f"spend: {usage.calls} calls, {usage.tokens} tokens, ${usage.dollars:.4f} "
            f"of the pass's budget {args.dollars}; ledger row in {spend.LEDGER}"
        )
    # Scored at the rule's k whatever this pass asked, as `make agent-eval ARM=bet` writes it.
    print(f"every arm: written to {write_every_arm()}")
    return 0 if why == "done" else 3


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
