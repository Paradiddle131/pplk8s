"""Does a data agent use the metric definitions Knowledge Catalog imported from dbt (Q2)?

The import ran before this probe (findings/2026-11-03-326-kc-dbt-import.md), and the $0 guard keeps agents from
deleting it, so "without the import" is the same tables copied to `bet_nokc`, which no dbt entry links to:
- `bet-kc`: the silver tables the dbt entries' `reference` links point at;
- `bet-nokc`: their copies in `bet_nokc` (same rows, columns and BigQuery descriptions; no dbt entry links to them).
Both agents get the same one-line instruction and no authored context (no glossary, no verified queries), so any
use of a metric definition comes from what the data agent reads on its own. Each agent is asked the same trap
questions from the frozen set (services/semantic-agent/evals/semantic_bet.yaml), moved onto the lab's dates; the
right answer is the metric's definition written as SQL over silver, run by `bq` with the lab's byte cap.
Recorded per question and agent: the SQL, whether it applies the definition the trap tests, the final answer, and
any text naming dbt, a metric or Knowledge Catalog.

Run (from the repo root), live, after `make gcp-cost-check` and `make gcp-usage-check`:
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/327_kc_agent.py [out.jsonl]
Env: GCP_PROJECT (required); the credential as platform/gcp/data-agent/publish.py picks it.
Writes: the dataset `bet_nokc` (US; `bq cp` of seven small silver tables, free), the data agents `bet-kc` and
`bet-nokc`, one chat per question and agent (BigQuery jobs capped at the lab's cap), one JSON line each to
out.jsonl (default 327_kc_agent.jsonl), the raw stream kept.
`--reference` asks the same questions of the generated-context agent `pplk8s-semantic` instead, chat only.
"""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TABLES = [
    "orders",
    "customers",
    "returns",
    "ad_spend",
    "leads",
    "bookings",
    "campaigns",
]
COPY = "bet_nokc"
# The generated-context agent (platform/gcp/data-agent/publish.py's default), asked as it stands, never republished.
REFERENCE = "pplk8s-semantic"
INSTRUCTION = "You answer questions about the shop's orders, partner returns and marketing. Amounts are in EUR."
MENTIONS = re.compile(
    r"\b(dbt|metric|semantic|knowledge catalog|catalog)\b", re.IGNORECASE
)

# (case, question, the definition the trap tests, the right answer as SQL over silver)
PROBES = [
    (
        "revenue_september",
        "What was our total revenue in September 2026?",
        "revenue_eur leaves cancelled orders out",
        (
            "SELECT ROUND(SUM(amount), 2) FROM silver.orders "
            "WHERE status <> 'cancelled' AND order_date BETWEEN '2026-09-01' AND '2026-09-30'"
        ),
    ),
    (
        "return_rate_september",
        "What share of the orders placed in September 2026 were returned?",
        "return_rate counts returns on the order's date",
        (
            "SELECT ROUND((SELECT COUNT(*) FROM silver.returns WHERE order_date BETWEEN '2026-09-01' AND '2026-09-30') "
            "/ (SELECT COUNT(*) FROM silver.orders WHERE order_date BETWEEN '2026-09-01' AND '2026-09-30'), 4)"
        ),
    ),
    (
        "aov_september",
        "What was our average order value in September 2026?",
        "average_order_value_eur is over non-cancelled orders",
        (
            "SELECT ROUND(SUM(amount) / COUNT(*), 2) FROM silver.orders "
            "WHERE status <> 'cancelled' AND order_date BETWEEN '2026-09-01' AND '2026-09-30'"
        ),
    ),
    (
        "cancellation_rate_period",
        "What share of all orders placed between 17 August and 2 October 2026 were cancelled?",
        "cancellation_rate is a ratio of sums",
        (
            "SELECT ROUND(COUNTIF(status = 'cancelled') / COUNT(*), 4) FROM silver.orders "
            "WHERE order_date BETWEEN '2026-08-17' AND '2026-10-02'"
        ),
    ),
    (
        "customers_september",
        "How many distinct customers bought from us in September 2026?",
        "customers_distinct leaves cancelled orders out, distinct over the month",
        (
            "SELECT COUNT(DISTINCT customer_id) FROM silver.orders "
            "WHERE status <> 'cancelled' AND order_date BETWEEN '2026-09-01' AND '2026-09-30'"
        ),
    ),
    (
        "channel_lowest_cpl",
        (
            "Which ad channel had the lowest cost per lead between 17 August and 2 October 2026, and what was that "
            "cost in EUR?"
        ),
        "cost_per_lead_eur is spend over leads, a ratio of sums",
        (
            "WITH s AS (SELECT c.channel, SUM(a.spend) AS spend FROM silver.ad_spend a JOIN silver.campaigns c "
            "USING (campaign_id) WHERE a.spend_date BETWEEN '2026-08-17' AND '2026-10-02' GROUP BY 1), "
            "l AS (SELECT c.channel, COUNT(*) AS leads FROM silver.leads d JOIN silver.campaigns c USING (campaign_id) "
            "WHERE d.created_date BETWEEN '2026-08-17' AND '2026-10-02' GROUP BY 1) "
            "SELECT channel, ROUND(spend / leads, 2) AS cost_per_lead_eur FROM s JOIN l USING (channel) "
            "ORDER BY 2 LIMIT 1"
        ),
    ),
]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def bq(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bq", *args], capture_output=True, text=True, check=False)


def copy_tables(project: str) -> None:
    """bet_nokc: the silver tables copied as they are now (rows, schema and descriptions; no dbt entry links them)."""
    if bq("show", f"{project}:{COPY}").returncode:
        made = bq("mk", "--location=US", "--dataset", f"{project}:{COPY}")
        if made.returncode:
            raise SystemExit(f"bq mk {COPY}: {made.stdout}{made.stderr}")
    for table in TABLES:
        done = bq("cp", "-f", f"{project}:silver.{table}", f"{project}:{COPY}.{table}")
        if done.returncode:
            raise SystemExit(f"bq cp {table}: {done.stdout}{done.stderr}")


def context(project: str, dataset: str, cap: int) -> dict:
    return {
        "systemInstruction": INSTRUCTION,
        "datasourceReferences": {
            "bq": {
                "tableReferences": [
                    {"projectId": project, "datasetId": dataset, "tableId": t}
                    for t in TABLES
                ]
            }
        },
        "options": {
            "datasource": {"bigQueryMaxBilledBytes": str(cap)},
            "model": "MODEL_UNSPECIFIED",
        },
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0] if args else "327_kc_agent.jsonl")
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    shaped = load("shaped_agent", HERE / "329_shaped_agent.py")
    publish = shaped.load_publish()
    cap = publish.query_cap()
    token = publish.access_token(dict(os.environ))
    send = publish.http_transport(token, project)
    chat_send = shaped.chat_transport(token, project)
    reference = "--reference" in sys.argv
    arms = (
        [(REFERENCE, "silver")]
        if reference
        else [("bet-kc", "silver"), ("bet-nokc", COPY)]
    )
    if not reference:
        copy_tables(project)
    right = {case: shaped.right_answer(sql, cap) for case, _, _, sql in PROBES}
    with out.open("a") as sink:
        for agent_id, dataset in arms:
            if agent_id != REFERENCE:
                publisher = publish.Publisher(send, project, shaped.LOCATION, agent_id)
                agent = publish.desired(
                    context(project, dataset, cap),
                    None,
                    display_name=agent_id,
                    description=f"The semantic bet's Q2 arm: the {dataset} tables, no authored context.",
                )
                try:
                    publisher.publish(agent)
                except publish.PublishError as error:
                    print(f"327_kc_agent: {agent_id} publish refused: {error}")
                    return 2
            shaped.AGENT_ID = (
                agent_id  # shaped.chat addresses the agent by this module global
            )
            for case, question, definition, _ in PROBES:
                try:
                    status, stream, seconds = shaped.chat(chat_send, project, question)
                except (http.client.IncompleteRead, OSError) as error:
                    # A stream cut mid-read (seen once in a run): keep the row as a transport error, go on.
                    status, stream, seconds = (
                        0,
                        {"transport_error": repr(error)[:300]},
                        None,
                    )
                summary = shaped.summarise(stream)
                said = "\n".join(summary["texts"])
                row = {
                    "agent": agent_id,
                    "dataset": dataset,
                    "case": case,
                    "question": question,
                    "definition": definition,
                    "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "http_status": status,
                    "seconds": seconds,
                    "generated_sql": summary["generated_sql"],
                    "final_response": summary["final_response"],
                    "mentions": sorted({m.lower() for m in MENTIONS.findall(said)}),
                    "right_answer": right[case],
                    "texts": summary["texts"],
                    "stream": stream,
                }
                sink.write(json.dumps(row) + "\n")
                final = " ".join(summary["final_response"])[:160].replace("\n", " ")
                print(
                    f"{agent_id} {case}: HTTP {status} {seconds}s right={right[case]} final={final!r}"
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
