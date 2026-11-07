"""The semantic agent's three MetricFlow tools as a command line, for an agent that is not ADK:
the semantic bet's arm `cc-metricflow` (#374), a Claude Code subagent answering through them.

Each call runs the same function the ADK agent's tool runs (semantic_agent.tools) and, for a data
call, the same guard: the audit row first (caller `claude-code-<model>`, the session from
`BET_CC_SESSION`), then the freshness, or the error that withholds the result.

    python -m semantic_agent.tool_cli list_metrics
    python -m semantic_agent.tool_cli describe_metric '{"name": "revenue_eur"}'
    python -m semantic_agent.tool_cli query_metrics '{"metrics": ["revenue_eur"], ...}'

Env: the semantic agent's warehouse (DBT_HOST, DBT_PORT, DBT_DBNAME); BET_CC_MODEL, BET_CC_SESSION.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from semantic_agent import audit
from semantic_agent.guard import guarded
from semantic_agent.tools import CATALOG_TOOLS, TOOLS, catalog

BY_NAME = {tool.__name__: tool for tool in TOOLS}


def call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """One tool call as the ADK agent makes it: the catalog tools unguarded, data tools audited."""
    if name not in BY_NAME:
        return {"error": f"no tool {name!r}; the tools are {sorted(BY_NAME)}"}
    try:
        response = BY_NAME[name](**args)
    except Exception as error:  # the caller sees what went wrong, as an ADK tool error reads
        return {"error": f"{name} failed: {type(error).__name__}: {error}"}
    if name in CATALOG_TOOLS:
        return response if isinstance(response, dict) else {"result": response}
    caller = audit.Caller(
        agent=f"claude-code-{os.environ.get('BET_CC_MODEL', 'unknown')}",
        session_id=os.environ.get("BET_CC_SESSION"),
    )
    return guarded(name, args, response, caller, catalog)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    args = json.loads(argv[1]) if len(argv) > 1 else {}
    print(json.dumps(call(argv[0], args), ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
