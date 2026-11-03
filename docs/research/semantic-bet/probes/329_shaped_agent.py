"""The `native-shaped` arm live: a data agent offered bet_shaped's table functions and parameterised verified queries.

Measures, on the lab project:
- whether a data agent's context takes BigQuery table functions in `userFunctions.bqRoutines` (the create or the
  publish refuses them, or not), and parameterised `exampleQueries` (`parameters`: name, DATE type, description);
- for each probe question below, what the agent's SQL used: a bet_shaped table function, a verified query
  (`matchedQuery`), or its own SQL over the silver tables; and its answer beside the right one, which the probe
  reads from the table function itself.
The agent, `bet-shaped` in `us`, holds the seven silver tables the saved queries read, the seven table functions
(their descriptions as written in probes/329_bet_shaped.sql), one verified query per saved query calling its
function with `@start_date` and `@end_date`, a one-paragraph system instruction, and the lab's per-query byte cap.
Created or updated through platform/gcp/data-agent/publish.py's Publisher (the pinned schema check, staging then
published), read in place, never edited.

Run (from the repo root), live, after `make gcp-cost-check` and `make gcp-usage-check`:
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/329_shaped_agent.py [out.jsonl]
Env: GCP_PROJECT (required); the credential as publish.py picks it (on cloud the proxy injects it).
Writes: the `bet-shaped` data agent; one chat per question (each runs BigQuery jobs capped at the lab's cap);
one JSON line per question to out.jsonl (default 329_shaped_agent.jsonl), the raw stream kept.
`--no-routines` publishes the agent without `bqRoutines`, `--no-examples` without the verified queries (each
run republishes `bet-shaped` with what it asks for; run the full context last to leave the arm as #333 needs it).
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PUBLISH = ROOT / "platform/gcp/data-agent/publish.py"
SHAPED_SQL = Path(__file__).resolve().parent / "329_bet_shaped.sql"
AGENT_ID = "bet-shaped"
LOCATION = "us"
DATASET = "bet_shaped"
TABLES = [
    "orders",
    "customers",
    "returns",
    "ad_spend",
    "leads",
    "bookings",
    "campaigns",
]

INSTRUCTION = (
    "You answer questions about the shop's sales, partner returns and marketing. The dataset bet_shaped holds one "
    "table function per agreed business metric set, each taking (start_date DATE, end_date DATE), both inclusive; "
    "they compute the metrics exactly as the business defines them (net revenue, cost per lead and cost per "
    "booking included). When a question asks for any of those metrics, call the matching bet_shaped table function "
    "with the question's dates rather than writing the aggregation over the silver tables yourself. Use the silver "
    "tables only for questions no function answers. Amounts are in EUR."
)

# (case, question, the table function that answers it or None, the right answer's query over the functions or None)
PROBES = [
    (
        "net_revenue_month",
        "What was our net revenue in September 2026?",
        "net_sales_daily",
        (
            "SELECT ROUND(SUM(net_revenue_eur), 2) AS net_revenue_eur "
            "FROM bet_shaped.net_sales_daily(DATE '2026-09-01', DATE '2026-09-30')"
        ),
    ),
    (
        "cost_per_lead_channel",
        "What was the cost per lead for each marketing channel in October 2026?",
        "channel_performance",
        (
            "SELECT campaign__channel, ROUND(cost_per_lead_eur, 2) AS cost_per_lead_eur "
            "FROM bet_shaped.channel_performance(DATE '2026-10-01', DATE '2026-10-31') ORDER BY 1"
        ),
    ),
    (
        "cancelled_first_week",
        "How many orders were cancelled on each day from 1 to 7 October 2026?",
        "daily_sales",
        (
            "SELECT DATE(metric_time__day) AS day, orders_cancelled "
            "FROM bet_shaped.daily_sales(DATE '2026-10-01', DATE '2026-10-07') ORDER BY 1"
        ),
    ),
    (
        "top_return_reason_q3",
        "Which return reason cost us the most in the third quarter of 2026, and how much?",
        "returns_by_reason",
        (
            "SELECT return__reason, returns_eur "
            "FROM bet_shaped.returns_by_reason(DATE '2026-07-01', DATE '2026-09-30') ORDER BY returns_eur DESC LIMIT 1"
        ),
    ),
    (
        "revenue_by_country_month",
        "What was revenue by customer country in September 2026?",
        "sales_by_country_daily",
        (
            "SELECT customer__country, ROUND(SUM(revenue_eur), 2) AS revenue_eur "
            "FROM bet_shaped.sales_by_country_daily(DATE '2026-09-01', DATE '2026-09-30') GROUP BY 1 ORDER BY 1"
        ),
    ),
    (
        "aov_by_country_month",
        "What was the average order value by customer country in September 2026?",
        None,
        (
            # The project's average_order_value_eur: revenue over non-cancelled orders; no saved query holds it.
            "SELECT c.country, ROUND(SUM(o.amount) / COUNT(o.order_id), 2) AS average_order_value_eur "
            "FROM silver.orders o JOIN silver.customers c USING (customer_id) "
            "WHERE o.order_date BETWEEN '2026-09-01' AND '2026-09-30' AND o.status <> 'cancelled' "
            "GROUP BY 1 ORDER BY 1"
        ),
    ),
    (
        "new_customers_month",
        "How many customers placed their first ever order in September 2026?",
        None,
        (
            "WITH f AS (SELECT customer_id, MIN(order_date) AS first_order FROM silver.orders GROUP BY 1) "
            "SELECT COUNTIF(first_order BETWEEN '2026-09-01' AND '2026-09-30') AS new_customers FROM f"
        ),
    ),
]

FUNCTION = re.compile(
    r"CREATE OR REPLACE TABLE FUNCTION bet_shaped\.(\w+)\(start_date DATE, end_date DATE\)\s*"
    r"OPTIONS \(description = '((?:[^'\\]|\\.)*)'\)"
)


def load_publish():
    spec = importlib.util.spec_from_file_location("publish", PUBLISH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["publish"] = (
        module  # dataclass-like NamedTuples resolve their module by name
    )
    spec.loader.exec_module(module)
    return module


def functions() -> dict[str, str]:
    """Each table function's name and description, as 329_bet_shaped.sql creates them."""
    found = {
        name: desc.replace("\\'", "'")
        for name, desc in FUNCTION.findall(SHAPED_SQL.read_text())
    }
    if len(found) != 7:
        raise SystemExit(
            f"{SHAPED_SQL}: expected 7 table functions, found {sorted(found)}"
        )
    return found


def question_of(description: str) -> str:
    return description.split("Question: ", 1)[1].split(" Dates are", 1)[0]


def context(project: str, cap: int, routines: bool, examples: bool = True) -> dict:
    fns = functions()
    params = [
        {
            "name": "start_date",
            "dataType": "DATE",
            "description": "The first day of the period asked about, inclusive.",
        },
        {
            "name": "end_date",
            "dataType": "DATE",
            "description": "The last day of the period asked about, inclusive.",
        },
    ]
    body = {
        "systemInstruction": INSTRUCTION,
        "datasourceReferences": {
            "bq": {
                "tableReferences": [
                    {"projectId": project, "datasetId": "silver", "tableId": t}
                    for t in TABLES
                ]
            }
        },
        "exampleQueries": [
            {
                "naturalLanguageQuestion": question_of(desc).replace(
                    "?", " between a start date and an end date?"
                ),
                "sqlQuery": f"SELECT * FROM `{project}.{DATASET}.{name}`(@start_date, @end_date)",
                "parameters": params,
            }
            for name, desc in fns.items()
        ],
        "options": {
            "datasource": {"bigQueryMaxBilledBytes": str(cap)},
            "model": "MODEL_UNSPECIFIED",
        },
    }
    if not examples:
        del body["exampleQueries"]
    if routines:
        body["userFunctions"] = {
            "bqRoutines": [
                {
                    "routineReference": {
                        "projectId": project,
                        "datasetId": DATASET,
                        "routineId": name,
                    },
                    "description": desc,
                }
                for name, desc in fns.items()
            ]
        }
    return body


def right_answer(sql: str | None, cap: int) -> list | str | None:
    if sql is None:
        return None
    run = subprocess.run(
        [
            "bq",
            "query",
            "--use_legacy_sql=false",
            f"--maximum_bytes_billed={cap}",
            "--format=json",
            sql,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode:
        return f"error: {run.stdout.strip() or run.stderr.strip()}"
    return json.loads(run.stdout or "[]")


def chat_transport(token: str, project: str):
    """publish.py's transport with a longer timeout: a chat streams for up to minutes."""

    def send(method: str, target: str, body: dict) -> tuple[int, object]:
        request = urllib.request.Request(
            target,
            data=json.dumps(body).encode(),
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "x-goog-user-project": project,
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return response.status, json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as error:
            raw = error.read().decode(errors="replace")
            try:
                return error.code, json.loads(raw or "{}")
            except ValueError:
                return error.code, {"error": {"message": raw[:500]}}

    return send


def chat(send, project: str, question: str) -> tuple[int, object, float]:
    parent = f"projects/{project}/locations/{LOCATION}"
    body = {
        "parent": parent,
        "messages": [{"userMessage": {"text": question}}],
        "dataAgentContext": {"dataAgent": f"{parent}/dataAgents/{AGENT_ID}"},
    }
    started = time.monotonic()
    status, payload = send(
        "POST",
        f"https://geminidataanalytics.{LOCATION}.rep.googleapis.com/v1/{parent}:chat",
        body,
    )
    return status, payload, round(time.monotonic() - started, 1)


def summarise(stream: object) -> dict:
    """What the stream says the agent did: its SQL, the functions and tables it names, a matched verified query,
    and its final text."""
    messages = stream if isinstance(stream, list) else [stream]
    sql, matched, texts, final = [], [], [], []
    for message in messages:
        system = (message or {}).get("systemMessage") or {}
        data = system.get("data") or {}
        if data.get("generatedSql"):
            sql.append(data["generatedSql"])
        if data.get("matchedQuery") or data.get("matchedExampleQuery"):
            matched.append(data.get("matchedQuery") or data.get("matchedExampleQuery"))
        text = system.get("text") or {}
        parts = "".join(text.get("parts") or [])
        if parts:
            texts.append(f"{text.get('textType', '?')}: {parts}")
            if text.get("textType") == "FINAL_RESPONSE":
                final.append(parts)
    joined = "\n".join(sql)
    return {
        "generated_sql": sql,
        "functions_called": sorted(
            set(re.findall(rf"{DATASET}`?\.`?(\w+)`?\s*\(", joined))
        ),
        "silver_tables": sorted(set(re.findall(r"silver`?\.`?(\w+)", joined))),
        "matched_query": matched,
        "final_response": final,
        "texts": texts,
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    routines = "--no-routines" not in sys.argv
    examples = "--no-examples" not in sys.argv
    out = Path(args[0] if args else "329_shaped_agent.jsonl")
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    publish = load_publish()
    cap = publish.query_cap()
    token = publish.access_token(dict(os.environ))
    send = publish.http_transport(token, project)
    chat_send = chat_transport(token, project)
    publisher = publish.Publisher(send, project, LOCATION, AGENT_ID)
    agent = publish.desired(
        context(project, cap, routines, examples),
        None,
        display_name="bet-shaped",
        description="The semantic bet's native-shaped arm: silver tables, bet_shaped table functions, "
        "parameterised verified queries.",
    )
    try:
        publisher.publish(agent)
    except publish.PublishError as error:
        print(f"329_shaped_agent: publish refused: {error}")
        return 2
    published = publisher.call(
        "GET", f"{publish.endpoint(LOCATION)}/v1/{publisher.name}"
    )
    kept = (published.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    print(
        "329_shaped_agent: published context keeps "
        f"{len((kept.get('userFunctions') or {}).get('bqRoutines') or [])} routines and "
        f"{sum(1 for q in kept.get('exampleQueries') or [] if q.get('parameters'))} parameterised verified queries"
    )
    with out.open("a") as sink:
        for case, question, function, answer_sql in PROBES:
            status, stream, seconds = chat(chat_send, project, question)
            row = {
                "case": case,
                "question": question,
                "covering_function": function,
                "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "routines_in_context": routines,
                "verified_queries_in_context": examples,
                "http_status": status,
                "seconds": seconds,
                **summarise(stream),
                "right_answer": right_answer(answer_sql, cap),
                "stream": stream,
            }
            sink.write(json.dumps(row) + "\n")
            print(
                f"{case}: HTTP {status} {seconds}s functions={row['functions_called']} "
                f"silver={row['silver_tables']} matched={bool(row['matched_query'])}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
