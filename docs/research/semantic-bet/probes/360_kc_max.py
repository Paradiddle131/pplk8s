"""The data agent with as much Knowledge Catalog context as the lab can give it: the arm native-kc-max (#360, Q2).

What it builds, from the dbt project (the semantic models', metrics' and models' YAML, read from the manifests
`dbt parse` writes, the same source the generated context uses):
- `bet_kcmax`, a copy of the 16 silver tables the semantic models read (US, `bq cp`, free), so the glossary links
  and descriptions below reach this arm's tables only: a data agent imports the business glossary terms linked to
  its tables, so links on `silver` would reach every other silver arm and the main track's agents too;
- (a) BigQuery table and column descriptions on those copies, the words `persist_docs` would write (each model's
  and declared column's `description`), by DDL (`ALTER TABLE ... SET OPTIONS` / `ALTER COLUMN ... SET OPTIONS`),
  each statement dry-run first and run with the lab's `maximum_bytes_billed`;
- (b) a Knowledge Catalog business glossary `bet-kc-max` in `us`: one term per metric (its label, description and
  its definition written out) and one per glossary term (`config.meta.glossary`), each linked to the columns it
  reads (`definition` entry links), at most 10 terms per table, the most a data agent imports
  (https://docs.cloud.google.com/knowledge-catalog/docs/manage-glossaries, Limitations); the $0 guard refuses
  Knowledge Catalog writes from agents, so `--paste` writes the owner's Cloud Shell block for it;
- the data agent `bet-kc-max`: native-kc's one-line instruction, no authored glossary or verified queries, over the
  `bet_kcmax` copies, `semantic.time_spine` and RULE.md's `legacy` tables (native-context's tables, the silver ones
  as copies), the lab's byte cap; the arm reads only what Knowledge Catalog and BigQuery hold.

Run from the repo root (the manifests: `bash docs/research/semantic-bet/probes/326_dbt_artifacts.sh <dir>` first,
offline, then pass `--manifests <dir>/dbt/target`; default `${TMPDIR:-/tmp}/semantic-bet-326/dbt/target`):
  python3 -I docs/research/semantic-bet/probes/360_kc_max.py --dry-run [--manifests DIR]
      offline: prints the copies, every DDL statement, the terms, the links and the agent body; sends nothing.
  python3 -I docs/research/semantic-bet/probes/360_kc_max.py --paste OUT_DIR [--manifests DIR]
      offline: writes OUT_DIR/paste.sh (the owner's Cloud Shell block) and OUT_DIR/undo.sh.
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/360_kc_max.py --describe
      live, after `make gcp-cost-check` and `make gcp-usage-check`: the copies (only the missing ones) and the
      descriptions (one dry run, then one capped DDL job per statement).
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/360_kc_max.py --publish
      live: creates or updates and publishes `bet-kc-max`, then the read-back.
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/360_kc_max.py --readback
      live, read-only: the agent's published tables, each copy's descriptions, the glossary's terms and each
      table's linked terms (`lookupEntryLinks`).
Env: GCP_PROJECT (required live); the credential as platform/gcp/data-agent/publish.py picks it (on cloud the proxy
injects it).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = "pplk8s-lab-001"
SOURCE = "silver"
COPY = "bet_kcmax"
LOCATION = "us"
GLOSSARY = "bet-kc-max"
AGENT_ID = "bet-kc-max"
# native-kc's instruction (327_kc_agent.py), unchanged: the arm adds catalog context, not authored context.
INSTRUCTION = "You answer questions about the shop's orders, partner returns and marketing. Amounts are in EUR."
# RULE.md: every arm that writes SQL is given the legacy tables; native-context also reads the time spine.
EXTRA = [
    ("semantic", "time_spine"),
    ("legacy", "channel_daily"),
    ("legacy", "country_sales"),
    ("legacy", "daily_net_sales"),
]
# A data agent imports at most this many glossary terms per table (manage-glossaries, Limitations).
TERMS_PER_TABLE = 10
# Knowledge Catalog limits: a term's description at most 1 KB; BigQuery's column description 1,024 characters.
DESCRIPTION_MAX = 1024
# Knowledge Catalog bills metadata storage above the first 1 MiB a month (knowledge-catalog pricing).
FREE_METADATA = 1 << 20
AGG = {
    "sum": "SUM({})",
    "count": "COUNT({})",
    "count_distinct": "COUNT(DISTINCT {})",
    "average": "AVG({})",
    "min": "MIN({})",
    "max": "MAX({})",
}
DIMENSION = re.compile(r"\{\{\s*Dimension\('(\w+?)__(\w+)'\)\s*\}\}")
RATIO = "each totalled over the whole period asked (a ratio of totals, never an average of daily ratios)"
METRIC_FILTER = re.compile(r"\{\{\s*Metric\('(\w+)',\s*group_by=\['(\w+)'\]\)\s*\}\}")


@dataclass
class Term:
    """A glossary term to create, with the columns it is linked to."""

    id: str
    display: str
    description: str
    kind: str  # glossary | simple | formula | window
    columns: set[tuple[str, str]] = field(default_factory=set)


def slug(name: str) -> str:
    """A resource id: lowercase letters, digits and hyphens, starting with a letter, at most 63 characters."""
    out = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return (out if out[:1].isalpha() else f"t-{out}")[:63].rstrip("-")


def clip(text: str, limit: int = DESCRIPTION_MAX) -> str:
    """Text cut to `limit` UTF-8 bytes on a word boundary, ending with an ellipsis when cut."""
    text = " ".join(text.split())
    if len(text.encode()) <= limit:
        return text
    cut = text.encode()[: limit - 4].decode(errors="ignore").rsplit(" ", 1)[0]
    return cut + " ..."


class Project:
    """The dbt project as the manifests hold it: the silver tables the semantic models read, their words, the
    semantic models, the metrics and the glossary terms."""

    def __init__(self, target: Path):
        manifest = json.loads((target / "manifest.json").read_text())
        semantic = json.loads((target / "semantic_manifest.json").read_text())
        self.models = {sm["name"]: sm for sm in semantic["semantic_models"]}
        self.metrics = {m["name"]: m for m in semantic["metrics"]}
        self.table_of = {
            name: sm["node_relation"]["alias"] for name, sm in self.models.items()
        }
        nodes = {
            (n["schema"], n["alias"]): n
            for n in manifest["nodes"].values()
            if n["resource_type"] == "model"
        }
        self.nodes = {t: nodes[(SOURCE, t)] for t in sorted(self.table_of.values())}
        self.tables = list(self.nodes)
        self.glossary = [
            g
            for n in self.nodes.values()
            for g in (n["config"].get("meta") or {}).get("glossary") or []
        ]

    def text(self, words: str) -> str:
        """Our words with `silver.<table>` pointed at the copy the arm reads."""
        return re.sub(
            rf"\b{SOURCE}\.(\w+)",
            lambda m: f"{COPY}.{m[1]}" if m[1] in self.nodes else m[0],
            words,
        )

    def columns(self, table: str) -> list[str]:
        return list(self.nodes[table]["columns"])

    def dimension_column(
        self, entity: str, dim: str, near: str | None = None
    ) -> tuple[str, str]:
        """The (table, column) a `<entity>__<dimension>` reads: the metric's own semantic model first, else the
        one whose primary entity it is."""
        order = [near] if near else []
        order += [
            n
            for n, sm in self.models.items()
            if any(
                e["name"] == entity and e["type"] == "primary" for e in sm["entities"]
            )
        ]
        for name in order:
            for d in self.models[name]["dimensions"]:
                if d["name"] == dim:
                    return self.table_of[name], d["expr"] or d["name"]
        raise KeyError(f"{entity}__{dim}")

    def filter_sql(
        self, template: str, near: str | None
    ) -> tuple[str, set[tuple[str, str]]]:
        """A MetricFlow filter as SQL over the table, and the columns it reads."""
        cols: set[tuple[str, str]] = set()

        def dim(m: re.Match) -> str:
            table, col = self.dimension_column(m[1], m[2], near)
            cols.add((table, col))
            return col

        def metric(m: re.Match) -> str:
            return f"{m[1]} per {m[2]}"

        return METRIC_FILTER.sub(metric, DIMENSION.sub(dim, template)), cols

    def simple(self, metric: dict) -> tuple[str, set[tuple[str, str]]]:
        """A simple metric's definition as SQL, and the columns it reads."""
        params = metric["type_params"]["metric_aggregation_params"]
        name = params["semantic_model"]
        table = self.table_of[name]
        expr = metric["type_params"]["expr"] or "1"
        if params["agg"] == "percentile":
            p = params["agg_params"]["percentile"]
            sql = f"PERCENTILE_CONT({expr}, {p})"
        else:
            sql = AGG[params["agg"]].format("*" if expr == "1" else expr)
        known = set(self.columns(table))
        if re.fullmatch(
            r"[a-z_][a-z0-9_]*", expr
        ):  # a column, declared in the YAML or not
            cols = {(table, expr)}
        else:  # an expression: the declared columns it names
            cols = {
                (table, c) for c in re.findall(r"[a-z_][a-z0-9_]*", expr) if c in known
            }
        if not cols:  # COUNT(*): the row's key
            primary = [
                e
                for e in self.models[name]["entities"]
                if e["type"] in ("primary", "natural")
            ]
            key = (
                (primary[0]["expr"] or primary[0]["name"])
                if primary
                else self.columns(table)[0]
            )
            cols.add((table, key))
        wheres = []
        for f in (metric.get("filter") or {}).get("where_filters") or []:
            sql_f, f_cols = self.filter_sql(f["where_sql_template"], name)
            wheres.append(sql_f)
            cols |= f_cols
        time = params.get("agg_time_dimension")
        out = f"{sql} FROM {COPY}.{table}"
        if wheres:
            out += " WHERE " + " AND ".join(wheres)
        if time:
            out += f", dated by {time}"
        return out, cols

    def input_ref(self, ref: dict) -> tuple[str, set[tuple[str, str]]]:
        """An input metric as a compound metric names it (with its own filter, if any), and the columns it reads."""
        cols = set(self.definition(ref["name"])[1])
        wheres = []
        for f in (ref.get("filter") or {}).get("where_filters") or []:
            sql_f, f_cols = self.filter_sql(f["where_sql_template"], None)
            wheres.append(sql_f)
            cols |= f_cols
        text = ref["name"] + (f" (where {' AND '.join(wheres)})" if wheres else "")
        return text, cols

    def definition(self, name: str) -> tuple[str, set[tuple[str, str]]]:
        """A metric's definition in words and SQL, and every column its inputs read."""
        metric = self.metrics[name]
        tp = metric["type_params"]
        kind = metric["type"]
        if kind == "simple":
            return self.simple(metric)
        if kind == "ratio":
            (num, num_cols), (den, den_cols) = (
                self.input_ref(tp["numerator"]),
                self.input_ref(tp["denominator"]),
            )
            cols = num_cols | den_cols
            return (
                f"{num} / {den}, {RATIO}",
                cols,
            )
        if kind == "derived":
            parts, cols = [], set()
            for m in tp["metrics"]:
                cols |= self.definition(m["name"])[1]
                if m.get("alias") and m.get("offset_window"):
                    w = m["offset_window"]
                    parts.append(
                        f"{m['alias']} is {m['name']} {w['count']} {w['granularity']} earlier"
                    )
            text = tp["expr"] + (f", where {'; '.join(parts)}" if parts else "")
            return text, cols
        if kind == "cumulative":
            c = tp["cumulative_type_params"]
            base = c["metric"]["name"]
            if c.get("window"):
                span = f"over the {c['window']['count']} {c['window']['granularity']}s ending on each day"
            elif c.get("grain_to_date"):
                span = f"{c['grain_to_date']} to date"
            else:
                span = "all time to date"
            return f"{base} {span}", self.definition(base)[1]
        if kind == "conversion":
            c = tp["conversion_type_params"]
            (base, base_cols), (conv, conv_cols) = (
                self.input_ref(c["base_metric"]),
                self.input_ref(c["conversion_metric"]),
            )
            w = c.get("window") or {}
            within = f" within {w['count']} {w['granularity']}s" if w else ""
            return (
                f"share of {base} whose {c['entity']} reaches {conv}{within}, counted on the {c['base_metric']['name']} date",
                base_cols | conv_cols,
            )
        raise ValueError(f"{name}: metric type {kind}")

    def terms(self) -> list[Term]:
        """One term per metric and one per glossary term, each with the columns it reads."""
        out = []
        for name, metric in sorted(self.metrics.items()):
            text, cols = self.definition(name)
            offset = any(
                m.get("offset_window")
                for m in metric["type_params"].get("metrics") or []
            )
            kind = (
                "simple"
                if metric["type"] == "simple"
                else "window"
                if metric["type"] == "cumulative" or offset
                else "formula"
            )
            out.append(
                Term(
                    id=slug(name),
                    display=metric.get("label") or name,
                    description=clip(
                        self.text(f"{metric['description']} Metric {name}: {text}.")
                    ),
                    kind=kind,
                    columns=cols,
                )
            )
        for g in self.glossary:
            cols = set()
            for d in g.get("dimensions") or []:
                entity, dim = d.split("__", 1)
                cols.add(self.dimension_column(entity, dim))
            if not cols:
                for m in g.get("metrics") or []:
                    cols |= self.definition(m)[1]
            extra = []
            if g.get("synonyms"):
                extra.append("Also called: " + ", ".join(g["synonyms"]) + ".")
            if g.get("metrics"):
                extra.append("Metrics: " + ", ".join(g["metrics"]) + ".")
            if g.get("dimensions"):
                extra.append("Dimensions: " + ", ".join(g["dimensions"]) + ".")
            out.append(
                Term(
                    id=slug(g["term"]),
                    display=g["term"],
                    description=clip(self.text(" ".join([g["description"], *extra]))),
                    kind="glossary",
                    columns=cols,
                )
            )
        ids = [t.id for t in out]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"term ids collide: {sorted(dupes)}")
        return out

    def ddl(self, project: str) -> list[str]:
        """The descriptions persist_docs would write, as DDL on the copies."""
        out = []
        for table, node in self.nodes.items():
            ref = f"`{project}.{COPY}.{table}`"
            out.append(
                f"ALTER TABLE {ref} SET OPTIONS (description = {sql_string(self.text(node['description']))})"
            )
            for col, spec in node["columns"].items():
                if spec.get("description"):
                    words = clip(self.text(spec["description"]))
                    out.append(
                        f"ALTER TABLE {ref} ALTER COLUMN IF EXISTS {col} "
                        f"SET OPTIONS (description = {sql_string(words)})"
                    )
        return out


def sql_string(text: str) -> str:
    """A GoogleSQL string literal."""
    return "'" + " ".join(text.split()).replace("\\", "\\\\").replace("'", "\\'") + "'"


# Which terms a table keeps when more than TERMS_PER_TABLE read it, fixed before any run from the term's shape only:
# first the business words that are not metrics (their meaning is written nowhere else), then the simple metrics
# (the building blocks: one aggregate, its filter), then the formulas over them (ratio, derived, conversion), then
# the time windows of another metric (cumulative, or derived with an offset: the base metric already carries the
# definition); ties by id. The terms that read one table take their slots first; a term that reads several is then
# linked on each of its tables that still has room, so it reaches the agent through any one of them.
RANK = {"glossary": 0, "simple": 1, "formula": 2, "window": 3}


def links(terms: list[Term]) -> tuple[list[tuple[str, str, str]], dict[str, list[str]]]:
    """The (table, column, term id) links to create, at most TERMS_PER_TABLE terms per table, and the terms each
    table drops."""
    order = sorted(terms, key=lambda t: (RANK[t.kind], t.id))
    on: dict[str, list[str]] = {}
    dropped: dict[str, list[str]] = {}
    for spanning in (False, True):
        for t in order:
            tables = sorted({tbl for tbl, _ in t.columns})
            if (len(tables) > 1) != spanning:
                continue
            for table in tables:
                slots = on.setdefault(table, [])
                if len(slots) < TERMS_PER_TABLE:
                    slots.append(t.id)
                else:
                    dropped.setdefault(table, []).append(t.id)
    by_id = {t.id: t for t in terms}
    kept = [
        (table, col, term)
        for table, ids in sorted(on.items())
        for term in ids
        for tbl, col in sorted(by_id[term].columns)
        if tbl == table
    ]
    return kept, dropped


def link_id(table: str, column: str, term: str) -> str:
    return "kcmax-" + hashlib.sha1(f"{table}.{column}>{term}".encode()).hexdigest()[:16]


def context(project: str, tables: list[str], cap: int | None) -> dict:
    """bet-kc-max's context: native-kc's instruction, the copies plus the time spine and the legacy tables."""
    refs = [{"projectId": project, "datasetId": COPY, "tableId": t} for t in tables]
    refs += [{"projectId": project, "datasetId": d, "tableId": t} for d, t in EXTRA]
    body = {
        "systemInstruction": INSTRUCTION,
        "datasourceReferences": {"bq": {"tableReferences": refs}},
    }
    if cap is not None:
        body["options"] = {
            "datasource": {"bigQueryMaxBilledBytes": str(cap)},
            "model": "MODEL_UNSPECIFIED",
        }
    return body


def plan_json(
    proj: Project, terms: list[Term], kept: list[tuple[str, str, str]]
) -> dict:
    """What the owner's paste creates, as the JSON file it writes."""
    return {
        "glossary": {
            "id": GLOSSARY,
            "displayName": "pplk8s semantic layer (bet kc-max)",
            "description": (
                "The lab's metrics and business terms from the dbt semantic layer, linked to the columns of "
                f"{COPY} (synthetic data; issue 360)."
            ),
        },
        "tables": proj.tables,
        "terms": [
            {"id": t.id, "displayName": t.display, "description": t.description}
            for t in terms
        ],
        "links": [
            {"id": link_id(tbl, col, term), "table": tbl, "column": col, "term": term}
            for tbl, col, term in kept
        ],
    }


PASTE = r"""# bet-kc-max (#360): a Knowledge Catalog business glossary linked to the columns of bet_kcmax.
# Paste into Cloud Shell on project pplk8s-lab-001. Safe to paste again: what exists answers 409 and is kept.
# Docs: https://docs.cloud.google.com/knowledge-catalog/docs/manage-glossaries (glossary, terms, column links,
#   REST as the page gives it, read __READ__); https://cloud.google.com/bigquery/pricing#free (table copies free).
P=pplk8s-lab-001; L=us; G=__GLOSSARY__; D=__COPY__
NUM=$(gcloud projects describe $P --format='value(projectNumber)')
API=https://dataplex.googleapis.com/v1
TOKEN=$(gcloud auth print-access-token)
# The docs' gcurl, as a function that prints the HTTP status and keeps the body in ~/bet-360/last.json.
gcurl() { curl -sS -o ~/bet-360/last.json -w "%{http_code}" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"; }
mkdir -p ~/bet-360 && cd ~/bet-360
cat > plan.json <<'JSON'
__PLAN__
JSON
# 1. The copies the links point at (BigQuery copy jobs are free; only the copied bytes' storage counts).
bq --location=US mk --dataset $P:$D 2>/dev/null || true
for t in $(jq -r '.tables[]' plan.json); do bq cp -n $P:silver.$t $P:$D.$t >/dev/null 2>&1 || true; done
for t in $(jq -r '.tables[]' plan.json); do
  E=projects/$NUM/locations/$L/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/$P/datasets/$D/tables/$t
  for i in $(seq 1 30); do c=$(gcurl "$API/projects/$P/locations/$L:lookupEntry?entry=$E"); [ "$c" = 200 ] && break; sleep 10; done
  echo "entry $D.$t $c"
done
TOKEN=$(gcloud auth print-access-token)
# 2. The glossary (a long-running operation), then wait until it reads back.
c=$(gcurl -X POST "$API/projects/$P/locations/$L/glossaries?glossary_id=$G" --data "$(jq -c '.glossary|{displayName,description}' plan.json)"); echo "glossary $c"; [ "$c" = 200 ] || [ "$c" = 409 ] || cat last.json
for i in $(seq 1 30); do c=$(gcurl "$API/projects/$P/locations/$L/glossaries/$G"); [ "$c" = 200 ] && break; sleep 5; done
TOKEN=$(gcloud auth print-access-token)
# 3. One term per metric and per business term.
jq -c '.terms[]' plan.json | while read -r t; do
  id=$(jq -r .id <<<"$t")
  c=$(gcurl -X POST "$API/projects/$P/locations/$L/glossaries/$G/terms?term_id=$id" --data "$(jq -c --arg p "projects/$P/locations/$L/glossaries/$G" '{displayName,description,parent:$p}' <<<"$t")")
  echo "term $id $c"; case $c in 200|409) ;; *) head -c 300 last.json; echo;; esac
done
TOKEN=$(gcloud auth print-access-token)
# 4. Each term linked to the columns it reads (a definition entry link from the table's column to the term).
jq -c '.links[]' plan.json | while read -r k; do
  id=$(jq -r .id <<<"$k"); t=$(jq -r .table <<<"$k"); col=$(jq -r .column <<<"$k"); term=$(jq -r .term <<<"$k")
  body=$(jq -nc --arg s "projects/$NUM/locations/$L/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/$P/datasets/$D/tables/$t" \
    --arg path "Schema.$col" --arg g "projects/$NUM/locations/$L/entryGroups/@dataplex/entries/projects/$NUM/locations/$L/glossaries/$G/terms/$term" \
    '{entry_link_type:"projects/dataplex-types/locations/global/entryLinkTypes/definition",entry_references:[{name:$s,path:$path,type:"SOURCE"},{name:$g,type:"TARGET"}]}')
  for i in 1 2 3 4 5 6; do c=$(gcurl -X POST "$API/projects/$NUM/locations/$L/entryGroups/@bigquery/entryLinks?entry_link_id=$id" --data "$body"); case $c in 200|409) break;; esac; sleep 10; done
  echo "link $t.$col -> $term $c"; case $c in 200|409) ;; *) head -c 300 last.json >&2; echo >&2;; esac
done | tee links.log | awk '{print $NF}' | sort | uniq -c
echo "done: $(jq '.terms|length' plan.json) terms, $(jq '.links|length' plan.json) links; tell the agent 'kc-max pasted'"
"""

UNDO = r"""# Undo bet-kc-max (#360): the column links, the terms, the glossary, the copies and the data agent.
# Docs: https://docs.cloud.google.com/knowledge-catalog/docs/manage-glossaries (delete link, term, glossary).
P=pplk8s-lab-001; L=us; G=__GLOSSARY__; D=__COPY__
API=https://dataplex.googleapis.com/v1
TOKEN=$(gcloud auth print-access-token)
gcurl() { curl -sS -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" "$@"; }
for id in __LINKS__; do gcurl -X DELETE "$API/projects/$P/locations/$L/entryGroups/@bigquery/entryLinks/$id"; done | sort | uniq -c
for id in __TERMS__; do gcurl -X DELETE "$API/projects/$P/locations/$L/glossaries/$G/terms/$id"; done | sort | uniq -c
gcurl -X DELETE "$API/projects/$P/locations/$L/glossaries/$G"
bq rm -r -f -d $P:$D
gcurl -X DELETE "https://geminidataanalytics.us.rep.googleapis.com/v1/projects/$P/locations/us/dataAgents/__AGENT__"
"""


def compact(plan: dict) -> str:
    """The plan as JSON with one term or link a line, so the paste stays readable."""

    def rows(items: list) -> str:
        return ",\n".join("  " + json.dumps(i, ensure_ascii=False) for i in items)

    return (
        "{\n"
        f' "glossary": {json.dumps(plan["glossary"], ensure_ascii=False)},\n'
        f' "tables": {json.dumps(plan["tables"])},\n'
        f' "terms": [\n{rows(plan["terms"])}\n ],\n'
        f' "links": [\n{rows(plan["links"])}\n ]\n'
        "}"
    )


def paste(plan: dict, read: str) -> tuple[str, str]:
    """The owner's Cloud Shell block and its undo, with the plan inline."""
    block = (
        PASTE.replace("__PLAN__", compact(plan))
        .replace("__GLOSSARY__", GLOSSARY)
        .replace("__COPY__", COPY)
        .replace("__READ__", read)
    )
    undo = (
        UNDO.replace("__GLOSSARY__", GLOSSARY)
        .replace("__COPY__", COPY)
        .replace("__AGENT__", AGENT_ID)
        .replace("__LINKS__", " ".join(k["id"] for k in plan["links"]))
        .replace("__TERMS__", " ".join(t["id"] for t in plan["terms"]))
    )
    return block, undo


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def publisher_module():
    return load("shaped_agent", HERE / "329_shaped_agent.py").load_publish()


def bq(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bq", *args], capture_output=True, text=True, check=False)


def query(send, project: str, sql: str, cap: int, dry: bool) -> tuple[int, dict]:
    """One BigQuery job (jobs.query), capped; a dry run validates it and bills nothing."""
    body = {
        "query": sql,
        "useLegacySql": False,
        "location": "US",
        "dryRun": dry,
        "maximumBytesBilled": str(cap),
    }
    return send(
        "POST",
        f"https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries",
        body,
    )


def describe(proj: Project, project: str) -> int:
    """The copies (missing ones only) and the descriptions on them."""
    publish = publisher_module()
    cap = publish.query_cap()
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    if bq("show", f"{project}:{COPY}").returncode:
        made = bq("mk", "--location=US", "--dataset", f"{project}:{COPY}")
        if made.returncode:
            print(f"360_kc_max: bq mk {COPY}: {made.stdout}{made.stderr}")
            return 2
    for table in proj.tables:
        if bq("show", f"{project}:{COPY}.{table}").returncode:
            done = bq(
                "cp", "-n", f"{project}:{SOURCE}.{table}", f"{project}:{COPY}.{table}"
            )
            print(
                f"360_kc_max: copy {table}: {'ok' if not done.returncode else done.stderr.strip()}"
            )
    statements = proj.ddl(project)
    for sql in statements:
        status, out = query(send, project, sql, cap, dry=True)
        billed = (out.get("totalBytesProcessed") or "0") if status == 200 else None
        if status != 200 or int(billed or 0) > 0:
            print(
                f"360_kc_max: dry run refused or bills bytes ({status}, {billed}): {sql[:120]} {out}"
            )
            return 2
    ran = 0
    for sql in statements:
        status, out = query(send, project, sql, cap, dry=False)
        if status != 200 or out.get("errors"):
            print(
                f"360_kc_max: DDL failed ({status}): {sql[:120]} {json.dumps(out)[:300]}"
            )
            return 2
        ran += 1
    print(f"360_kc_max: {ran} DDL statements on {COPY} (each dry-run first, 0 bytes)")
    return 0


def publish_agent(proj: Project, project: str) -> int:
    publish = publisher_module()
    cap = publish.query_cap()
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    agent = publish.desired(
        context(project, proj.tables, cap),
        None,
        display_name="bet native-kc-max",
        description=(
            "The semantic bet's native-kc-max arm: native-kc's one-line instruction over bet_kcmax (silver copied, "
            "with BigQuery descriptions and a Knowledge Catalog glossary linked to its columns), the time spine "
            "and the legacy tables."
        ),
    )
    publisher = publish.Publisher(send, project, LOCATION, AGENT_ID)
    try:
        writes = publisher.publish(agent)
    except publish.PublishError as error:
        print(f"360_kc_max: {AGENT_ID} publish refused: {error}")
        return 2
    print(f"360_kc_max: {AGENT_ID} writes {writes}")
    return readback(proj, project)


def readback(proj: Project, project: str) -> int:
    """Read-only: the agent's published tables, the copies' descriptions, the glossary and the links per table."""
    publish = publisher_module()
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    base = f"{publish.endpoint(LOCATION)}/v1/projects/{project}/locations/{LOCATION}/dataAgents/{AGENT_ID}"
    status, agent = send("GET", base, None)
    ctx = (
        ((agent.get("dataAnalyticsAgent") or {}).get("publishedContext") or {})
        if status == 200
        else {}
    )
    refs = ((ctx.get("datasourceReferences") or {}).get("bq") or {}).get(
        "tableReferences"
    ) or []
    print(
        f"agent {AGENT_ID} {status}: {len(refs)} tables; instruction {ctx.get('systemInstruction')!r}"
    )
    for table in proj.tables:
        shown = bq("show", "--format=json", f"{project}:{COPY}.{table}")
        if shown.returncode:
            print(f"copy {table}: missing")
            continue
        t = json.loads(shown.stdout)
        cols = t["schema"]["fields"]
        described = sum(1 for c in cols if c.get("description"))
        print(
            f"copy {table}: description {bool(t.get('description'))}, columns described {described}/{len(cols)}"
        )
    api = "https://dataplex.googleapis.com/v1"
    status, terms = send(
        "GET",
        f"{api}/projects/{project}/locations/{LOCATION}/glossaries/{GLOSSARY}/terms?pageSize=1000",
        None,
    )
    print(f"glossary {GLOSSARY} {status}: {len(terms.get('terms', []))} terms")
    status, info = send(
        "GET",
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{project}",
        None,
    )
    number = info.get("projectNumber", project)
    for table in proj.tables:
        entry = (
            f"projects/{number}/locations/{LOCATION}/entryGroups/@bigquery/entries/"
            f"bigquery.googleapis.com/projects/{project}/datasets/{COPY}/tables/{table}"
        )
        status, res = send(
            "POST",
            f"{api}/projects/{project}/locations/{LOCATION}:lookupEntryLinks?"
            + urllib.parse.urlencode(
                {
                    "entry": entry,
                    "entryLinkTypes": "projects/dataplex-types/locations/global/entryLinkTypes/definition",
                }
            ),
            None,
        )
        found = res.get("entryLinks", []) if status == 200 else []
        names = sorted(
            {
                r["name"].rsplit("/", 1)[1]
                for k in found
                for r in k["entryReferences"]
                if r["type"] == "TARGET"
            }
        )
        print(f"links {table} {status}: {len(found)} links, terms {names}")
    return 0


def main(argv: list[str]) -> int:
    args = list(argv)
    target = (
        Path(os.environ.get("TMPDIR", "/tmp")) / "semantic-bet-326" / "dbt" / "target"
    )
    if "--manifests" in args:
        i = args.index("--manifests")
        target = Path(args[i + 1])
        del args[i : i + 2]
    if not (target / "semantic_manifest.json").exists():
        sys.exit(
            f"360_kc_max: no manifests in {target}: run 326_dbt_artifacts.sh first (offline)"
        )
    proj = Project(target)
    terms = proj.terms()
    kept, dropped = links(terms)
    plan = plan_json(proj, terms, kept)
    project = os.environ.get("GCP_PROJECT", PROJECT)
    if "--dry-run" in args:
        print(
            f"copies: {len(proj.tables)} tables {SOURCE} -> {COPY}: {', '.join(proj.tables)}"
        )
        statements = proj.ddl(project)
        print(f"ddl: {len(statements)} statements (dry-run each, then run capped)")
        for sql in statements:
            print("  " + sql)
        print(
            f"terms: {len(terms)} ({sum(t.kind == 'glossary' for t in terms)} business terms, "
            f"{sum(t.kind != 'glossary' for t in terms)} metrics)"
        )
        for t in terms:
            print(f"  {t.id} [{t.kind}] {t.display}: {t.description}")
        tables = sorted({tbl for tbl, _, _ in kept})
        print(
            f"links: {len(kept)} column links over {len(tables)} tables, at most {TERMS_PER_TABLE} terms a table"
        )
        for table in tables:
            on = sorted({term for tbl, _, term in kept if tbl == table})
            print(
                f"  {table}: {len(on)} terms {on}; not linked here (no room) {dropped.get(table, [])}"
            )
        unlinked = sorted({t.id for t in terms} - {term for _, _, term in kept})
        print(f"  terms on no table: {unlinked}")
        size = len(json.dumps(plan).encode())
        print(
            f"metadata: the plan's JSON {size:,} bytes against the free {FREE_METADATA:,} a month "
            "(beside the dbt import's 290,315 bytes, #326)"
        )
        print("agent: " + json.dumps(context(project, proj.tables, None)))
        return 0
    if "--paste" in args:
        out = Path(args[args.index("--paste") + 1])
        out.mkdir(parents=True, exist_ok=True)
        block, undo = paste(plan, "2026-11-03")
        (out / "paste.sh").write_text(block)
        (out / "undo.sh").write_text(undo)
        print(
            f"360_kc_max: wrote {out / 'paste.sh'} ({len(block):,} bytes) and {out / 'undo.sh'} ({len(undo):,} bytes)"
        )
        return 0
    if not os.environ.get("GCP_PROJECT"):
        sys.exit("GCP_PROJECT is required")
    if "--describe" in args:
        return describe(proj, project)
    if "--publish" in args:
        return publish_agent(proj, project)
    if "--readback" in args:
        return readback(proj, project)
    sys.exit(
        "usage: 360_kc_max.py --dry-run | --paste DIR | --describe | --publish | --readback [--manifests DIR]"
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
