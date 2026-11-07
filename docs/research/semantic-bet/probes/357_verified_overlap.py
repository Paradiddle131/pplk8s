"""Which cases of a question set match one of bet-context's verified queries, by wording or by SQL shape (#357, Q8)?

`native-context`'s generated context carries verified queries (dbt/scripts/build_catalog.py's example_queries:
one "What is <metric> by day?" per metric, then each saved query's `meta.question`, each as MetricFlow compiles
it). A frozen case that reads like one, or whose expected SQL is one of them with only a date filter added, is a
case the agent may answer by recall of a worked example rather than by reading the definitions; this lists them.

Per turn of each case, against every verified query:
- `wording`: the question's content words (dates, numbers and stop words dropped) overlap the verified
  question's by a Jaccard index of at least WORDING;
- `label`: every content word of the verified question, two or more, is in the turn's question (it names the
  metric's label; a one-word label, "orders", would match nearly every case);
- `metric`: the verified query computes every metric the turn names (its `metrics`, `define` or `ambiguous`);
- `shape`: `metric`, and every non-time dimension its SQL returns is one the turn's expected SQL filters or groups
  by, and every one the turn filters or groups by it returns or filters on, so the verified SQL answers the turn
  with at most a date filter and a dimension value added.
A case matches a tier when any of its turns does. `--logs` adds, per tier, each arm's share of runs right on the
matching and the other cases, and how often the data agent said it matched a verified query (`matched_query`).

Offline (system Python with PyYAML, from the repo root):
  python3 -I docs/research/semantic-bet/probes/357_verified_overlap.py <set.yaml> \
    [--queries findings/2026-11-03-357-verified-queries.json] [--logs eval-<arm>.jsonl...] [--json out.json]
Live, read only (one GET of the agent; run inside the cost and usage checks):
  GCP_PROJECT=pplk8s-lab-001 python3 -I docs/research/semantic-bet/probes/357_verified_overlap.py \
    --fetch [bet-context] [--queries <snapshot.json>]
writes the agent's published verified queries to the snapshot, so later runs (another question set) need no GCP.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parent
SNAPSHOT = RESEARCH / "findings" / "2026-11-03-357-verified-queries.json"
AGENT = "bet-context"
# The Jaccard index of content words at or above which two questions read alike.
WORDING = 0.5
STOP_WORDS = """a about after all also an and any are as at be before between by can could day days did do does
each every for from had has have how i in is it its many me much of on or our over per placed same so than that
the their them there these this those through to total up us was we were what when where which who whose with
within would you your"""
STOP = set(STOP_WORDS.split())
MONTH_NAMES = """january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec"""
MONTHS = MONTH_NAMES.split()
DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}(st|nd|rd|th)?\b|\b\d{4}\b|\b("
    + "|".join(MONTHS)
    + r")\b",
    re.IGNORECASE,
)
WORD = re.compile(r"[a-z][a-z_']*")
# Columns that carry time, never a dimension a verified query groups by (its metric_time).
TIME = re.compile(r"(^|_)(date|day|week|month|year|time|period|start|end)($|_)")


def words(question: str) -> set[str]:
    """A question's content words: lower case, dates, numbers and stop words dropped, a plural kept singular."""
    text = DATE.sub(" ", question.lower())
    found = set()
    for w in WORD.findall(text):
        w = w.strip("'").removesuffix("'s")
        if w in STOP or len(w) < 2:
            continue
        found.add(
            w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 3 else w
        )
    return found


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def sql_text(sql: str) -> str:
    """SQL lower-cased, without comments, string literals or backticks, whitespace collapsed."""
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"'(?:[^']|'')*'", "'?'", sql)
    return " ".join(sql.replace("`", "").lower().split())


def outermost_select(sql: str) -> str:
    """The select list of a query's outermost SELECT (the one at depth 0, after any CTEs)."""
    text = sql_text(sql)
    depth, start, end = 0, None, None
    for match in re.finditer(r"[()]|\bselect\b|\bfrom\b", text):
        token = match.group()
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif depth == 0 and token == "select":
            start, end = match.end(), None
        elif depth == 0 and token == "from" and start is not None and end is None:
            end = match.start()
    return "" if start is None else text[start:end]


# SQL type names a CAST(... AS <type>) leaves after `as`.
TYPES = {
    "float64",
    "int64",
    "numeric",
    "bignumeric",
    "string",
    "date",
    "timestamp",
    "bool",
}
# A MetricFlow dimension: `entity__dimension` (metric_time__<grain> is time).
DIMENSION = re.compile(r"\b([a-z][a-z0-9_]*?)__([a-z][a-z0-9_]*)\b")


def verified_metrics(sql: str) -> set[str]:
    """The metrics a MetricFlow-compiled query returns: its outermost aliases that are neither a dimension
    (MetricFlow names those `entity__dimension` or `metric_time__grain`) nor a CAST's type."""
    aliases = re.findall(r"\bas\s+([a-z_][a-z0-9_]*)", outermost_select(sql))
    return {a for a in aliases if "__" not in a and a not in TYPES}


def _dimensions(text: str) -> set[str]:
    return {
        dim
        for entity, dim in DIMENSION.findall(text)
        if entity != "metric_time" and entity
    }


def verified_dimensions(sql: str) -> set[str]:
    """The non-time dimensions a MetricFlow-compiled query returns, by their column (`customer__country` → country)."""
    return _dimensions(outermost_select(sql))


def verified_filters(sql: str) -> set[str]:
    """The non-time dimensions any WHERE of the query filters on (a saved query's filter, a metric's own)."""
    text = sql_text(sql)
    found: set[str] = set()
    for clause in re.findall(r"\bwhere\b(.*?)(?=\bgroup\b|\border\b|\)|$)", text):
        found |= _dimensions(clause)
    return found


def expected_dimensions(sql: str, columns: set[str]) -> set[str]:
    """The non-time columns an expected SQL filters or groups by, among the dimension columns the verified queries
    know (so a table's own key or a metric column is never counted)."""
    text = sql_text(sql)
    used = set()
    for clause in re.findall(
        r"\b(?:where|and|or|group by|on)\s+([^()]*?)(?=\bwhere\b|\bgroup\b|\border\b|$|\))",
        text,
    ):
        used |= {c.split(".")[-1] for c in re.findall(r"[a-z_][a-z0-9_.]*", clause)}
    return {c for c in used & columns if not TIME.search(c)}


def load_set(path: Path) -> list[dict[str, Any]]:
    """The set's cases as {id, groups, turns: [{question, expected_sql, metrics}]}, in questions.yaml's shape."""
    spec = yaml.safe_load(path.read_text())
    groups = spec.get("groups") or {}
    cases = []
    for item in spec["questions"]:
        turns = item.get("turns") or [item]
        cases.append(
            {
                "id": item["id"],
                "groups": groups.get(item["id"], []),
                "turns": [
                    {
                        "question": t["question"],
                        "expected_sql": t.get("expected_sql") or "",
                        "metrics": sorted(
                            {
                                *t.get("metrics", []),
                                *t.get("define", []),
                                *t.get("ambiguous", []),
                            }
                        ),
                    }
                    for t in turns
                ],
            }
        )
    return cases


TIERS = ("wording", "label", "metric", "shape")


def match_case(
    case: dict[str, Any], queries: Sequence[dict[str, Any]]
) -> dict[str, Any]:
    """The case's best verified query per tier (by wording score), or None."""
    columns = set().union(*(q["dimensions"] | q["filters"] for q in queries))
    best: dict[str, tuple[float, str] | None] = dict.fromkeys(TIERS)
    for turn in case["turns"]:
        mine = words(turn["question"])
        dims = expected_dimensions(turn["expected_sql"], columns)
        for q in queries:
            theirs = words(q["question"])
            score = round(jaccard(mine, theirs), 2)
            hits = {
                "wording": score >= WORDING,
                "label": len(theirs) >= 2 and theirs <= mine,
                "metric": bool(turn["metrics"])
                and set(turn["metrics"]) <= q["metrics"],
            }
            # Its output dimensions are the turn's, and any other the turn filters on, the query filters on too.
            hits["shape"] = (
                hits["metric"]
                and q["dimensions"] <= dims
                and dims <= q["dimensions"] | q["filters"]
            )
            for tier, hit in hits.items():
                if hit and (best[tier] is None or score > best[tier][0]):
                    best[tier] = (score, q["question"])
    return {
        "id": case["id"],
        "groups": case["groups"],
        **{tier: (hit[1] if hit else None) for tier, hit in best.items()},
        "wording_score": max(
            (
                round(jaccard(words(t["question"]), words(q["question"])), 2)
                for t in case["turns"]
                for q in queries
            ),
            default=0.0,
        ),
    }


def read_queries(path: Path) -> list[dict[str, Any]]:
    snapshot = json.loads(path.read_text())
    return [
        {
            "question": q["naturalLanguageQuestion"],
            "sql": q["sqlQuery"],
            "metrics": verified_metrics(q["sqlQuery"]),
            "dimensions": verified_dimensions(q["sqlQuery"]),
            "filters": verified_filters(q["sqlQuery"]),
        }
        for q in snapshot["exampleQueries"]
    ]


def read_log(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def share(rows: Iterable[dict[str, Any]]) -> str:
    rows = list(rows)
    if not rows:
        return "-"
    right = sum(r.get("outcome") == "right" for r in rows)
    return f"{100 * right / len(rows):.1f}% ({len(rows)})"


def report(
    path: Path,
    cases: list[dict[str, Any]],
    matched: list[dict[str, Any]],
    logs: Sequence[Path],
) -> str:
    groups = sorted({g for c in cases for g in c["groups"]})
    lines = [
        f"# {path.name} against {AGENT}'s verified queries",
        "",
        f"{len(cases)} cases. A case counts in a tier when any of its turns matches (the probe's docstring).",
        "",
        "| Tier | Cases | " + " | ".join(f"`{g}`" for g in groups) + " |",
        "|---|---|" + "---|" * len(groups),
    ]
    for tier in TIERS:
        hit = [m for m in matched if m[tier]]
        per = [
            f"{sum(g in m['groups'] for m in hit)} of {sum(g in c['groups'] for c in cases)}"
            for g in groups
        ]
        lines.append(
            f"| `{tier}` | {len(hit)} of {len(cases)} | " + " | ".join(per) + " |"
        )
    lines += [
        "",
        "| Case | Groups | Best wording | Wording match | Label | Shape |",
        "|---|---|---|---|---|---|",
    ]
    for m in matched:
        lines.append(
            f"| `{m['id']}` | {', '.join(m['groups'])} | {m['wording_score']:.2f} | "
            f"{m['wording'] or ''} | {m['label'] or ''} | {m['shape'] or ''} |"
        )
    if logs:
        tier_of = {m["id"]: m for m in matched}
        lines += [
            "",
            "Each arm's runs right, on the cases a tier matches and on the others (runs counted):",
            "",
            "| Arm | Tier | Matching | Others | Runs with `matched_query` |",
            "|---|---|---|---|---|",
        ]
        for log in logs:
            rows = [
                r
                for r in read_log(log)
                if r.get("case") in tier_of and not r.get("error")
            ]
            arm = log.stem.removeprefix("eval-")
            used = sum(
                any(
                    c.get("tool") == "matched_query"
                    for t in r.get("turns", [])
                    for c in t.get("calls", [])
                )
                for r in rows
            )
            for tier in ("wording", "shape"):
                inside = [r for r in rows if tier_of[r["case"]][tier]]
                outside = [r for r in rows if not tier_of[r["case"]][tier]]
                lines.append(
                    f"| `{arm}` | `{tier}` | {share(inside)} | {share(outside)} | {used} of {len(rows)} |"
                )
    return "\n".join(lines) + "\n"


def fetch(agent_id: str, out: Path) -> int:
    """Write the agent's published verified queries (and its tables) to the snapshot: one GET, read only."""
    project = os.environ.get("GCP_PROJECT") or sys.exit("GCP_PROJECT is required")
    spec = importlib.util.spec_from_file_location(
        "bet_shaped_probe", HERE / "329_shaped_agent.py"
    )
    shaped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shaped)  # type: ignore[union-attr]
    publish = shaped.load_publish()
    send = publish.http_transport(publish.access_token(dict(os.environ)), project)
    name = f"projects/{project}/locations/{shaped.LOCATION}/dataAgents/{agent_id}"
    status, agent = send("GET", f"{publish.endpoint(shaped.LOCATION)}/v1/{name}", None)
    if status != 200:
        print(
            f"357_verified_overlap: GET {agent_id}: HTTP {status}: {json.dumps(agent)[:300]}"
        )
        return 2
    context = (agent.get("dataAnalyticsAgent") or {}).get("publishedContext") or {}
    refs = ((context.get("datasourceReferences") or {}).get("bq") or {}).get(
        "tableReferences"
    ) or []
    snapshot = {
        "agent": agent_id,
        "read_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "tables": [f"{r['datasetId']}.{r['tableId']}" for r in refs],
        "exampleQueries": context.get("exampleQueries") or [],
    }
    out.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n")
    print(
        f"357_verified_overlap: {agent_id}: {len(snapshot['exampleQueries'])} verified queries to {out}"
    )
    return 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "set", nargs="?", type=Path, help="a question set in questions.yaml's shape"
    )
    parser.add_argument(
        "--fetch", nargs="?", const=AGENT, help="read the agent's verified queries live"
    )
    parser.add_argument("--queries", type=Path, default=SNAPSHOT)
    parser.add_argument("--logs", nargs="*", type=Path, default=[])
    parser.add_argument(
        "--json", type=Path, help="also write every case's matches here"
    )
    args = parser.parse_args(argv)
    if args.fetch:
        return fetch(args.fetch, args.queries)
    if not args.set:
        parser.error("a question set (or --fetch) is required")
    cases = load_set(args.set)
    queries = read_queries(args.queries)
    matched = [match_case(c, queries) for c in cases]
    if args.json:
        args.json.write_text(json.dumps(matched, indent=1) + "\n")
    print(report(args.set, cases, matched, args.logs), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
