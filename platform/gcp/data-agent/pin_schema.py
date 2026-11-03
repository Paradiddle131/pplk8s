"""Pin what publish.py sends to the Conversational Analytics API (v1) from its discovery document (#207).

Reads `https://geminidataanalytics.googleapis.com/$discovery/rest?version=v1` (or a saved copy given as the
first argument) and writes `schemas/geminidataanalytics-v1-data-agent.json`: the document's `revision`, the
`DataAgent` schema and every schema it reaches (the request body of create and patch), and the four methods
publish.py calls (`dataAgents.get`, `create`, `patch`; `operations.get`) with their paths and parameters.
publish.py builds its URLs from those paths and validates every body against those schemas before sending.

dbt/scripts/schemas/ pins only the `Context` messages build_catalog.py may fill; this pin is the whole request
body, and tests/test_data_agent.py holds the two equal where they overlap, so renew both on a new revision:
`python3 platform/gcp/data-agent/pin_schema.py`, then `cd dbt && python3 scripts/pin_context_schema.py`.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

DISCOVERY = "https://geminidataanalytics.googleapis.com/$discovery/rest?version=v1"
ROOT = "GoogleCloudGeminidataanalyticsV1DataAgent"
METHODS = {
    "get": ("dataAgents", "get"),
    "create": ("dataAgents", "create"),
    "patch": ("dataAgents", "patch"),
    "operations.get": ("operations", "get"),
}
OUT = (
    Path(__file__).resolve().parent
    / "schemas"
    / "geminidataanalytics-v1-data-agent.json"
)


def refs(node: object) -> set[str]:
    """Every `$ref` under a schema."""
    if isinstance(node, dict):
        return (
            {node["$ref"]} if "$ref" in node else set().union(*map(refs, node.values()))
        )
    if isinstance(node, list):
        return set().union(*map(refs, node))
    return set()


def pin(discovery: dict) -> dict:
    schemas, todo = {}, [ROOT]
    while todo:
        name = todo.pop()
        if name not in schemas:
            schemas[name] = discovery["schemas"][name]
            todo += sorted(refs(schemas[name]))
    locations = discovery["resources"]["projects"]["resources"]["locations"][
        "resources"
    ]
    methods = {}
    for key, (resource, method) in METHODS.items():
        spec = locations[resource]["methods"][method]
        methods[key] = {
            "httpMethod": spec["httpMethod"],
            "path": spec["path"],
            "parameters": sorted(spec.get("parameters", {})),
            "request": spec.get("request", {}).get("$ref"),
        }
    return {
        "source": DISCOVERY,
        "revision": discovery["revision"],
        "root": ROOT,
        "methods": methods,
        "schemas": schemas,
    }


def main() -> int:
    if len(sys.argv) > 1:
        discovery = json.loads(Path(sys.argv[1]).read_text())
    else:
        with urllib.request.urlopen(DISCOVERY, timeout=60) as response:
            discovery = json.load(response)
    pinned = pin(discovery)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(pinned, indent=2, sort_keys=True) + "\n")
    print(
        f"pin_schema: revision {pinned['revision']}, {len(pinned['schemas'])} schemas in {OUT}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
