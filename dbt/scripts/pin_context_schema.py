"""Pin the Conversational Analytics API's v1 `Context` schemas that build_catalog.py writes into context.json.

Reads the API's discovery document (`https://geminidataanalytics.googleapis.com/$discovery/rest?version=v1`,
or a saved copy given as the first argument) and writes `scripts/schemas/geminidataanalytics-v1-context.json`:
its `revision` and the schemas of `PINNED`, as the document holds them, which check_catalog.py validates
context.json against. A schema the pin leaves out is one the generator must not use.

Host-only (dbt/.dockerignore): run it from dbt/ when Google publishes a new revision, then `make bigquery-check`.
Usage: python3 scripts/pin_context_schema.py [discovery.json]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

DISCOVERY = "https://geminidataanalytics.googleapis.com/$discovery/rest?version=v1"
PREFIX = "GoogleCloudGeminidataanalyticsV1"
PINNED = (
    "Context",
    "DatasourceReferences",
    "BigQueryTableReferences",
    "BigQueryTableReference",
    "Schema",
    "Field",
    "ExampleQuery",
    "QueryParameter",
    "GlossaryTerm",
)
OUT = Path(__file__).resolve().parent / "schemas" / "geminidataanalytics-v1-context.json"


def main() -> int:
    if len(sys.argv) > 1:
        discovery = json.loads(Path(sys.argv[1]).read_text())
    else:
        with urllib.request.urlopen(DISCOVERY, timeout=60) as response:  # noqa: S310 (a fixed https URL)
            discovery = json.load(response)
    pin = {
        "source": DISCOVERY,
        "revision": discovery["revision"],
        "root": PREFIX + "Context",
        "schemas": {PREFIX + name: discovery["schemas"][PREFIX + name] for name in PINNED},
    }
    OUT.write_text(json.dumps(pin, indent=2, sort_keys=True) + "\n")
    print(f"pin_context_schema: revision {pin['revision']}, {len(pin['schemas'])} schemas in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
