"""What dbt-mcp gives on the lab's dbt project with no dbt platform account.

Measures: which tools dbt-mcp lists when only a local project and dbt Core are configured (no
DBT_HOST, no token), and what a few of them return on the Compose warehouse: the dbt CLI tools
(list, compile, show), and the semantic-layer and discovery tools, which need the dbt platform.
Run (from the repo root, the Compose warehouse up with `make services-up`):
  uv run --no-project --python 3.13 --with dbt-mcp==2.7.0 python -I docs/research/semantic-bet/probes/334_dbt_mcp.py \
    <project-dir> <dbt-executable>
<project-dir> is a copy of dbt/ with `dbt deps` run (as probes/326_dbt_artifacts.sh makes one);
<dbt-executable> is dbt Core with dbt/requirements-postgres.txt installed.
Env: WAREHOUSE_PORT and WAREHOUSE_DBNAME (default 5433, warehouse); the probe writes its own profiles.yml
for the Compose warehouse on localhost, because dbt-mcp reads DBT_HOST as the dbt platform's host.
Offline: nothing leaves the machine but dbt-mcp's own calls, which it makes only with a platform token.
"""

import asyncio
import json
import os
import shutil
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

CALLS = [
    ("list", {"selector": "tag:semantic"}),
    ("compile", {"node_names": ["slv_orders"]}),
    (
        "show",
        {
            "sql_query": "select count(*) as n from {{ ref('slv_orders') }}",
            "limit": 5,
        },
    ),
    ("list_metrics", {}),
    ("query_metrics", {"metrics": ["revenue_eur"], "group_by": []}),
    ("get_all_models", {}),
    ("get_mart_models", {}),
    ("get_metrics_compiled_sql", {"metrics": ["revenue_eur"], "group_by": []}),
    ("get_lineage_dev", {"unique_id": "metric.pplk8s.revenue_eur"}),
    ("get_node_details_dev", {"node_id": "slv_orders"}),
]


def short(text: str, limit: int = 700) -> str:
    """The head and the tail of a long result: dbt's own log lines come first, the answer last."""
    text = " ".join(text.split())
    return (
        text if len(text) <= limit else text[: limit // 2] + " … " + text[-limit // 2 :]
    )


def write_profiles() -> str:
    profiles = tempfile.mkdtemp(prefix="dbt-mcp-profiles-")
    with open(os.path.join(profiles, "profiles.yml"), "w") as f:
        f.write(
            "pplk8s:\n  target: dev\n  outputs:\n    dev:\n      type: postgres\n      host: localhost\n"
            f"      port: {os.environ.get('WAREHOUSE_PORT', '5433')}\n      user: warehouse\n      password: warehouse\n"
            f"      dbname: {os.environ.get('WAREHOUSE_DBNAME', 'warehouse')}\n      schema: public\n      threads: 4\n"
        )
    return profiles


async def main(project_dir: str, dbt_path: str) -> None:
    profiles = write_profiles()
    env = {
        "PATH": os.environ["PATH"],
        "HOME": os.environ.get("HOME", "/root"),
        "DBT_PROJECT_DIR": project_dir,
        "DBT_PATH": dbt_path,
        "DBT_PROFILES_DIR": profiles,
    }
    server = StdioServerParameters(
        command=shutil.which("dbt-mcp") or "dbt-mcp", env=env
    )
    async with (
        stdio_client(server) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = (await session.list_tools()).tools
        names = sorted(t.name for t in tools)
        print(json.dumps({"tool_count": len(names), "tools": names}))
        for name, args in CALLS:
            if name not in names:
                print(json.dumps({"call": name, "result": "not listed"}))
                continue
            try:
                res = await asyncio.wait_for(session.call_tool(name, args), timeout=180)
                text = " ".join(getattr(c, "text", "") for c in res.content)
                print(
                    json.dumps(
                        {"call": name, "is_error": res.isError, "result": short(text)}
                    )
                )
            except Exception as exc:  # noqa: BLE001 - a probe records every failure as data
                print(json.dumps({"call": name, "error": short(repr(exc))}))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
