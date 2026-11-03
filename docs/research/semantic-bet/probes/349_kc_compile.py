"""What Knowledge Catalog's `compile_query` accepts, probed with read-only calls only (#349, Q1, Q3).

What it measures: the current `tools/list` entries of the catalog MCP server's `compile_query` and
`execute_query` (description and input schema, printed whole so a finding can diff them), then
`compile_query` over a matrix of requests that tells apart where a failure sits: a request missing a
required argument or with a malformed one (does validation answer before the backend?), `modelEntry` as
the full entry name, the bare entry id, the dbt fully qualified name and a BigQuery table's entry, and
fields in the forms a dbt semantic model and a Looker model would use.
`execute_query` is never called: it runs a BigQuery job, and it waits for a compiled query to dry-run.
How to run (from the repo root): python3 -I docs/research/semantic-bet/probes/349_kc_compile.py
Env: probes/326_kc_readback.py's (GCP_PROJECT, BET_ENTRY_GROUP, CLOUDSDK_AUTH_ACCESS_TOKEN).
Live but read-only: `compile_query` reads no table data (its own description), and catalog API calls bill $0.
"""

import importlib.util
import json
import sys
from pathlib import Path


def _readback():
    path = Path(__file__).with_name("326_kc_readback.py")
    spec = importlib.util.spec_from_file_location("kc_readback", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


kc = _readback()
SYSTEM = f"projects/{kc.PROJECT}/locations/us/entryGroups/@bigquery/entries"
TABLE = f"bigquery.googleapis.com/projects/{kc.PROJECT}/datasets/governed/tables/orders_daily"

# (label, arguments): each differs from the first in one respect.
CASES = [
    (
        "full name, dbt fields",
        {
            "modelEntry": f"{kc.ENTRIES}/semantic_model_pplk8s_orders",
            "fields": ["order__status", "orders_total"],
        },
    ),
    (
        "full name, Looker-style fields",
        {
            "modelEntry": f"{kc.ENTRIES}/semantic_model_pplk8s_orders",
            "fields": ["orders.status", "orders.orders_total"],
        },
    ),
    (
        "full name, one metric",
        {
            "modelEntry": f"{kc.ENTRIES}/semantic_model_pplk8s_orders",
            "fields": ["revenue_eur"],
        },
    ),
    (
        "bare entry id",
        {"modelEntry": "semantic_model_pplk8s_orders", "fields": ["revenue_eur"]},
    ),
    (
        "dbt fully qualified name",
        {
            "modelEntry": f"dbt:semantic_model:{kc.PROJECT}.pplk8s.orders",
            "fields": ["revenue_eur"],
        },
    ),
    (
        "a BigQuery table's entry",
        {"modelEntry": f"{SYSTEM}/{TABLE}", "fields": ["revenue_eur"]},
    ),
    ("no fields", {"modelEntry": f"{kc.ENTRIES}/semantic_model_pplk8s_orders"}),
    ("no modelEntry", {"fields": ["revenue_eur"]}),
    (
        "rowLimit as a string",
        {
            "modelEntry": f"{kc.ENTRIES}/semantic_model_pplk8s_orders",
            "fields": ["revenue_eur"],
            "rowLimit": "ten",
        },
    ),
]


def main() -> int:
    listed = kc.call(kc.MCP, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    tools = {t["name"]: t for t in listed.get("result", {}).get("tools", [])}
    print("tools/list:", len(tools), "tools:", ", ".join(sorted(tools)))
    for name in ("compile_query", "execute_query"):
        print(f"--- {name}")
        print(json.dumps(tools.get(name), indent=1, sort_keys=True))
    for location in ("us", "global"):
        for label, args in CASES:
            request = {"projectId": kc.PROJECT, "location": location, **args}
            ok, text = kc.tool("compile_query", request)
            print(
                f"compile_query [{location}] {label}:",
                "ok" if ok else "error",
                text[:300],
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
