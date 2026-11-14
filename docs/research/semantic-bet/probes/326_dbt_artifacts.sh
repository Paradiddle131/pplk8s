#!/usr/bin/env bash
# What it measures: the dbt artifacts Knowledge Catalog's dbt import would read for the lab project, built
# offline, and their sizes: the full manifest.json of the `gcp` target (relations named
# `<GCP_PROJECT>.<dataset>.<table>`, so the import's `reference` links can resolve in the US location), and a
# trimmed variant holding only the semantic layer (semantic models, metrics, saved queries) and the models
# the semantic models read, with what they depend on outside that set dropped.
# How to run (from the repo root): bash docs/research/semantic-bet/probes/326_dbt_artifacts.sh [out-dir]
# Env: GCP_PROJECT (default pplk8s-lab-001). Offline: `dbt parse` opens no connection; no catalog.json,
# which needs a live `dbt docs generate`.
# Writes <out-dir>/full/manifest.json and <out-dir>/trimmed/manifest.json (default
# ${TMPDIR:-/tmp}/semantic-bet-326) and prints one summary line per variant.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
# shellcheck source-path=SCRIPTDIR source=../../../../tests/e2e/lib/dbt-deps.sh
source "$REPO/tests/e2e/lib/dbt-deps.sh"
OUT=${1:-${TMPDIR:-/tmp}/semantic-bet-326}
PROJECT="$OUT/dbt"
DBT_BIGQUERY=dbt-bigquery==1.12.1
export GCP_PROJECT=${GCP_PROJECT:-pplk8s-lab-001} DBT_TARGET=gcp DBT_PROFILES_DIR="$PROJECT"
export GCP_ACCESS_TOKEN=${GCP_ACCESS_TOKEN:-offline-parse}

rm -rf "$OUT" && mkdir -p "$PROJECT" "$OUT/full" "$OUT/trimmed"
(cd "$REPO/dbt" && tar --exclude=./target --exclude=./logs --exclude=./dbt_packages -cf - .) | tar -xf - -C "$PROJECT"
dbt_deps "$PROJECT"
(cd "$PROJECT" && uv run --quiet --no-project --with-requirements requirements-postgres.txt --with "$DBT_BIGQUERY" \
  dbt parse --quiet)
cp "$PROJECT/target/manifest.json" "$OUT/full/manifest.json"

python3 -I - "$OUT/full/manifest.json" "$OUT/trimmed/manifest.json" <<'PY'
import json
import sys

src, dst = sys.argv[1], sys.argv[2]
m = json.load(open(src))
semantic = m.get("semantic_models", {})
read = {d for sm in semantic.values() for d in sm["depends_on"]["nodes"]}
keep_kinds = ("semantic_models", "metrics", "saved_queries")
kept = set(read) | {k for kind in keep_kinds for k in m.get(kind, {})}
trimmed = {k: v for k, v in m.items() if k not in ("nodes", "sources", "macros", "docs", "exposures", "groups", "unit_tests", "disabled", "child_map", "parent_map", "group_map")}
trimmed["nodes"] = {k: v for k, v in m["nodes"].items() if k in read}
for node in trimmed["nodes"].values():
    node["depends_on"] = {"macros": [], "nodes": [n for n in node["depends_on"]["nodes"] if n in kept]}
for empty in ("sources", "macros", "docs", "exposures", "groups", "unit_tests", "disabled"):
    trimmed[empty] = {}
trimmed["parent_map"] = {k: [p for p in m["parent_map"].get(k, []) if p in kept] for k in kept}
trimmed["child_map"] = {k: [c for c in m["child_map"].get(k, []) if c in kept] for k in kept}
trimmed["group_map"] = {}
json.dump(trimmed, open(dst, "w"))


def summary(name, d, path):
    size = len(open(path, "rb").read())
    counts = {k: len(d.get(k, {})) for k in ("nodes", "sources", "macros", "semantic_models", "metrics", "saved_queries")}
    rels = sorted({f"{n['database']}.{n['schema']}" for n in d["nodes"].values() if n.get("resource_type") == "model"})
    print(f"{name}: {size} bytes ({size / 1024:.1f} KiB); {counts}; model datasets: {', '.join(rels)}")


summary("full", m, src)
summary("trimmed", trimmed, dst)
print(f"dbt {m['metadata']['dbt_version']}, adapter {m['metadata']['adapter_type']}, schema {m['metadata']['dbt_schema_version']}")
PY
