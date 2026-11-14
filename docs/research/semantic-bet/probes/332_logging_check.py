"""Does a data agent keep conversation logging on over a view of a row-policied table, and what does a turn log?

Measures, on the lab project: publishes the data agent `bet-rls` in `us` over `bet_rls.orders_v` (a view of
`bet_rls.orders`, whose row access policy probes/332_rls_check.sh creates) with BigQuery Agent Analytics on, into
`agent_logs.data_agent_conversations`; reads the agent back to see whether the API kept the two logging fields;
asks one question; then counts the log table's rows for the agent, if the table exists.
Through platform/gcp/data-agent/publish.py's Publisher and probes/329_shaped_agent.py's chat, read in place.

Run (from the repo root), live, after probes/332_rls_check.sh (which runs the cost and usage checks):
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/332_logging_check.py
Writes: the `bet-rls` data agent; one chat (one BigQuery job on six rows, capped); prints what it saw.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ID = "bet-rls"
LOCATION = "us"
LOG = "agent_logs.data_agent_conversations"
QUESTION = "What is the total order amount by country?"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    shaped = load("shaped_agent", HERE / "329_shaped_agent.py")
    publish = shaped.load_publish()
    cap = publish.query_cap()
    token = publish.access_token(dict(os.environ))
    send = publish.http_transport(token, project)
    publisher = publish.Publisher(send, project, LOCATION, AGENT_ID)
    context = {
        "systemInstruction": "You answer questions about orders. Amounts are in EUR.",
        "datasourceReferences": {
            "bq": {
                "tableReferences": [
                    {
                        "projectId": project,
                        "datasetId": "bet_rls",
                        "tableId": "orders_v",
                    }
                ]
            }
        },
        "options": {
            "datasource": {"bigQueryMaxBilledBytes": str(cap)},
            "model": "MODEL_UNSPECIFIED",
        },
    }
    agent = publish.desired(
        context,
        publish.analytics_table(LOG, project),
        display_name="bet-rls",
        description="The semantic bet's row-policy probe: a view of a row-policied table, logging on.",
    )
    try:
        publisher.publish(agent)
    except publish.PublishError as error:
        print(f"332_logging_check: publish refused: {error}")
    current = publisher.call("GET", f"{publish.endpoint(LOCATION)}/v1/{publisher.name}")
    print(
        "kept: bigqueryAgentAnalyticsEnabled="
        f"{current.get('bigqueryAgentAnalyticsEnabled')}, bigqueryAgentAnalyticsTable="
        f"{json.dumps(current.get('bigqueryAgentAnalyticsTable'))}"
    )
    shaped.AGENT_ID = AGENT_ID
    status, stream, seconds = shaped.chat(
        shaped.chat_transport(token, project), project, QUESTION
    )
    summary = shaped.summarise(stream)
    print(f"chat: HTTP {status} {seconds}s sql={summary['generated_sql'][-1:]}")
    print(f"final: {summary['final_response']}")
    print(
        f"rows: {[m['systemMessage']['data']['result'].get('data') for m in stream if isinstance(m, dict) and ((m.get('systemMessage') or {}).get('data') or {}).get('result')]}"
    )
    show = subprocess.run(
        ["bq", "show", "--format=json", f"{project}:{LOG}"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(
        f"log table: {'exists' if show.returncode == 0 else 'absent: ' + (show.stdout or show.stderr).strip()[:200]}"
    )
    if show.returncode == 0:
        count = subprocess.run(
            [
                "bq",
                "query",
                "--use_legacy_sql=false",
                f"--maximum_bytes_billed={cap}",
                "--format=json",
                f"SELECT COUNT(*) AS turns FROM `{project}.{LOG}`",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"log rows: {(count.stdout or count.stderr).strip()[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
