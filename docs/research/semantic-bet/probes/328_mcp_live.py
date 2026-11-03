"""The `native-mcp` arm live: probes/328_mcp_agent.py on Google's MCP servers, over frozen cases (#328, Q3).

What it measures: per case, every tool call the agent makes on BigQuery's and Knowledge Catalog's remote MCP
servers (does it search the dbt metrics, read their definitions, try `compile_query`, or write its own SQL),
its answer, and the answer's outcome under RULE.md (bet_rule's `number_right` and `turn_outcome`, with the
expected numbers from the Compose warehouse's dbt_dev, as the eval takes them).
Writes one JSON line per case and run to the file named by `--out`; a case already in it is skipped.

Env: probes/328_mcp_agent.py's (`GCP_PROJECT`, the endpoints, `BET_MCP_TOKEN`), the model's, and the expected
numbers' warehouse (`WAREHOUSE_OWNER_URL`, `DBT_DBNAME=dbt_dev`, needs `make services-up` and the agents'
fixture). Live: run `make gcp-cost-check` and `make gcp-usage-check` before and after.
Run from services/semantic-agent:
  DBT_DBNAME=dbt_dev uv run python ../../docs/research/semantic-bet/probes/328_mcp_live.py \
    --out ../../docs/research/semantic-bet/findings/<date>-328-mcp-live.jsonl <case id>...
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import importlib.util
import json
import os
from pathlib import Path

from semantic_agent import evaluation
from semantic_agent.bet_eval import load_bet
from semantic_agent.bet_rule import number_right, turn_outcome
from semantic_agent.model import DEFAULT_MODEL_ID


def _agent_module():
    path = Path(__file__).with_name("328_mcp_agent.py")
    spec = importlib.util.spec_from_file_location("bet_mcp_agent", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run", type=int, default=1)
    parser.add_argument("ids", nargs="+")
    args = parser.parse_args()

    bet = load_bet(ids=args.ids)
    database = os.environ.get("DBT_DBNAME", "dbt_dev")
    # The eval's owner role, as bet_eval takes the expected numbers (expected_sql reads silver too).
    url = os.environ.get(
        "WAREHOUSE_OWNER_URL",
        f"postgresql://warehouse:warehouse@localhost:5433/{database}",
    )
    expected = evaluation.expected_numbers(bet.questions, url)
    done = set()
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            row = json.loads(line)
            done.add((row["case"], row["run"]))
    agent = _agent_module()
    for question in bet.questions:
        if (question.id, args.run) in done:
            continue
        turn = question.turns[0]
        result = await agent.ask(turn.question)
        numbers = expected[question.id][0]
        right = number_right(result["answer"], numbers)
        outcome = turn_outcome(result["answer"], right, bet.hedges, turn.question)
        row = {
            "case": question.id,
            "run": args.run,
            "groups": bet.groups.get(question.id, []),
            "model": os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
            "at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expected": numbers,
            "outcome": str(outcome),
            **result,
        }
        with args.out.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        tools = [c["tool"] for c in result["calls"]]
        print(f"{question.id}: {outcome} {tools}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
