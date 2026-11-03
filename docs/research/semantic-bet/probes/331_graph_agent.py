"""The `native-graph` arm live: a data agent with the sales graph's measures beside the tables it is built on.

Measures, on the lab project: for each probe question below, whether the data agent's SQL aggregates through the
graph (`GRAPH_EXPAND` and `AGG()` on `bet_graph.sales`) or writes its own SQL over the silver tables, and its
answer beside the right one, read from the graph's measures (or, where no measure holds the metric, from the
project's definition over silver).
The agent, `bet-graph` in `us`, holds `silver.orders`, `silver.customers` and `silver.returns`, the property graph
`bet_graph.sales` (probes/331_bet_graph_sales.sql: those three tables, their measures and edges), a one-line system
instruction naming the graph, and the lab's per-query byte cap; published through platform/gcp/data-agent/
publish.py's Publisher, and chatted through probes/329_shaped_agent.py's chat and summary, both read in place.

Run (from the repo root), live, after `make gcp-cost-check` and `make gcp-usage-check`, once the graph exists:
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/331_graph_agent.py [out.jsonl]
Writes: the `bet-graph` data agent; one chat per question; one JSON line per question to out.jsonl (default
331_graph_agent.jsonl), the raw stream kept.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ID = "bet-graph"
LOCATION = "us"
TABLES = ["orders", "customers", "returns"]
INSTRUCTION = (
    "You answer questions about the shop's orders, customers and partner returns. The property graph "
    "bet_graph.sales holds the business's metric definitions as measures on those tables. Amounts are in EUR."
)

# (case, question, the right answer's query)
PROBES = [
    (
        "revenue_by_country",
        "What was revenue by customer country in September 2026?",
        (
            "SELECT customers_country, ROUND(AGG(orders_revenue_eur), 2) AS revenue_eur "
            "FROM GRAPH_EXPAND('bet_graph.sales', start_node => 'orders') "
            "WHERE orders_order_date BETWEEN '2026-09-01' AND '2026-09-30' GROUP BY 1 ORDER BY 1"
        ),
    ),
    (
        "cancellation_rate",
        "What share of orders was cancelled in September 2026?",
        (
            "SELECT ROUND(AGG(orders_cancellation_rate), 4) AS cancellation_rate "
            "FROM GRAPH_EXPAND('bet_graph.sales', start_node => 'orders') "
            "WHERE orders_order_date BETWEEN '2026-09-01' AND '2026-09-30'"
        ),
    ),
    (
        "returns_by_country",
        "How much did partner returns cost us by customer country in October 2026?",
        # From silver: GRAPH_EXPAND from `returns` doesn't reach `customers` (measured 2026-11-03, the name unknown),
        # likely because returns reach customers by two paths (directly and through orders).
        (
            "SELECT c.country, SUM(r.amount) AS returns_eur FROM silver.returns r JOIN silver.customers c "
            "USING (customer_id) WHERE r.return_date BETWEEN '2026-10-01' AND '2026-10-31' GROUP BY 1 ORDER BY 1"
        ),
    ),
    (
        "aov_month",
        "What was the average order value in September 2026?",
        # The project's average_order_value_eur (revenue over non-cancelled orders): not a measure in the graph.
        (
            "SELECT ROUND(SUM(amount) / COUNT(order_id), 2) AS average_order_value_eur FROM silver.orders "
            "WHERE order_date BETWEEN '2026-09-01' AND '2026-09-30' AND status <> 'cancelled'"
        ),
    ),
]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def context(project: str, cap: int) -> dict:
    return {
        "systemInstruction": INSTRUCTION,
        "datasourceReferences": {
            "bq": {
                "tableReferences": [
                    {"projectId": project, "datasetId": "silver", "tableId": t}
                    for t in TABLES
                ],
                "propertyGraphReferences": [
                    {
                        "projectId": project,
                        "datasetId": "bet_graph",
                        "propertyGraphId": "sales",
                    }
                ],
            }
        },
        "options": {
            "datasource": {"bigQueryMaxBilledBytes": str(cap)},
            "model": "MODEL_UNSPECIFIED",
        },
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0] if args else "331_graph_agent.jsonl")
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    shaped = load("shaped_agent", HERE / "329_shaped_agent.py")
    publish = shaped.load_publish()
    cap = publish.query_cap()
    token = publish.access_token(dict(os.environ))
    publisher = publish.Publisher(
        publish.http_transport(token, project), project, LOCATION, AGENT_ID
    )
    agent = publish.desired(
        context(project, cap),
        None,
        display_name="bet-graph",
        description="The semantic bet's native-graph arm: silver tables and the sales graph's measures.",
    )
    try:
        publisher.publish(agent)
    except publish.PublishError as error:
        print(f"331_graph_agent: publish refused: {error}")
        return 2
    chat_send = shaped.chat_transport(token, project)
    shaped.AGENT_ID = AGENT_ID  # chat() addresses the module's agent
    with out.open("a") as sink:
        for case, question, answer_sql in PROBES:
            status, stream, seconds = shaped.chat(chat_send, project, question)
            summary = shaped.summarise(stream)
            joined = "\n".join(summary["generated_sql"])
            row = {
                "case": case,
                "question": question,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "http_status": status,
                "seconds": seconds,
                "graph_expand": bool(re.search(r"GRAPH_EXPAND", joined, re.IGNORECASE)),
                "graph_table": bool(
                    re.search(r"GRAPH_TABLE|\bMATCH\b", joined, re.IGNORECASE)
                ),
                **summary,
                "right_answer": shaped.right_answer(answer_sql, cap),
                "stream": stream,
            }
            sink.write(json.dumps(row) + "\n")
            print(
                f"{case}: HTTP {status} {seconds}s graph_expand={row['graph_expand']} "
                f"silver={row['silver_tables']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
