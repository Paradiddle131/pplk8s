"""What Knowledge Catalog stored from the dbt import, read back with read-only calls only (Q1).

What it measures: the import job's state and counts, the entries per type in the entry group, the links of
one metric, one semantic model and one dbt model, keyword and semantic search on three questions, the size of
`lookup_context` for a metric and a semantic model, and whether the catalog MCP server's `compile_query`
(no table reads) accepts an imported semantic model.
How to run (from the repo root): python3 -I docs/research/semantic-bet/probes/326_kc_readback.py
Env: GCP_PROJECT (default pplk8s-lab-001), BET_ENTRY_GROUP (default dbt-metadata-ingestion), and a token in
CLOUDSDK_AUTH_ACCESS_TOKEN (on cloud the proxy injects it; locally, `gcloud auth print-access-token`).
Live but read-only: Knowledge Catalog API calls bill $0, and `compile_query` reads no table data.
"""

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

PROJECT = os.environ.get("GCP_PROJECT", "pplk8s-lab-001")
GROUP = os.environ.get("BET_ENTRY_GROUP", "dbt-metadata-ingestion")
API = "https://dataplex.googleapis.com/v1"
MCP = "https://dataplex.googleapis.com/mcp"
LOC = f"projects/{PROJECT}/locations/us"
ENTRIES = f"{LOC}/entryGroups/{GROUP}/entries"
QUESTIONS = ["net revenue", "return rate", "how many orders were cancelled"]


def token() -> str:
    tok = os.environ.get("CLOUDSDK_AUTH_ACCESS_TOKEN")
    if tok:
        return tok
    out = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


TOKEN = token()


def call(url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="GET" if body is None else "POST"
    )
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return {"error": f"HTTP {err.code}: {err.read()[:300]!r}"}


def tool(name: str, args: dict) -> tuple[bool, str]:
    res = call(
        MCP,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        },
    )
    if "error" in res:
        return False, str(res["error"])
    out = res["result"]
    return not out.get("isError", False), "".join(
        c.get("text", "") for c in out.get("content", [])
    )


def main() -> int:
    for job in call(f"{API}/{LOC}/metadataJobs").get("metadataJobs", []):
        print(
            "job",
            job["name"].rsplit("/", 1)[1],
            job["status"]["state"],
            job["createTime"][:19],
            job["status"].get("updateTime", "")[:19],
            json.dumps(job.get("importResult", {})),
        )

    entries, page = [], ""
    while True:
        res = call(
            f"{API}/{ENTRIES}?pageSize=500" + (f"&pageToken={page}" if page else "")
        )
        entries += res.get("entries", [])
        page = res.get("nextPageToken", "")
        if not page:
            break
    print(
        "entries",
        len(entries),
        dict(Counter(e["entryType"].rsplit("/", 1)[1] for e in entries)),
    )

    for entry in [
        "metric_pplk8s_return_rate",
        "semantic_model_pplk8s_orders",
        "model_pplk8s_slv_orders",
    ]:
        res = call(
            f"{API}/{LOC}:lookupEntryLinks?"
            + urllib.parse.urlencode({"entry": f"{ENTRIES}/{entry}"})
        )
        for link in res.get("entryLinks", []):
            ends = {
                r["type"]: r["name"].rsplit("/entries/", 1)[1]
                for r in link["entryReferences"]
            }
            print(
                "link",
                entry,
                link["entryLinkType"].rsplit("/", 1)[1],
                ends.get("SOURCE"),
                "->",
                ends.get("TARGET"),
            )

    for q in QUESTIONS:
        for semantic in (False, True):
            body = {"query": q, "pageSize": 5} | (
                {"semanticSearch": True} if semantic else {}
            )
            res = call(f"{API}/projects/{PROJECT}/locations/global:searchEntries", body)
            hits = [
                r["dataplexEntry"].get("fullyQualifiedName")
                for r in res.get("results", [])
            ]
            print(
                "search",
                "semantic" if semantic else "keyword",
                repr(q),
                res.get("error") or hits,
            )

    ok, text = tool(
        "lookup_context",
        {
            "projectId": PROJECT,
            "location": "us",
            "resources": [
                f"{ENTRIES}/metric_pplk8s_return_rate",
                f"{ENTRIES}/semantic_model_pplk8s_orders",
            ],
        },
    )
    print("lookup_context", "ok" if ok else "error", len(text), "chars")

    ok, text = tool(
        "compile_query",
        {
            "projectId": PROJECT,
            "location": "us",
            "modelEntry": f"{ENTRIES}/semantic_model_pplk8s_orders",
            "fields": ["orders.status", "orders_total"],
        },
    )
    print("compile_query", "ok" if ok else "error", text[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
