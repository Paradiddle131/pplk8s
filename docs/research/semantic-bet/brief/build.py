#!/usr/bin/env python3
"""Build the plain-language Approaches page from the eval's results.json.

The page is the short companion of the technical report (`../report/`): one sortable table of the
approaches a team could take, ordered from the most native to the most custom, each drawn as 100
answers.  It recommends nothing; every number comes from `results.json`, so rerunning this after a
pass refreshes it.

    python3 build.py ../results.json            # writes index.html beside this file
"""
import argparse
import html
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

# What each set is called on the page, and what its button's tooltip says.
SETS = [
    ("frozen", "Everyday", "Plain business questions across the domains: totals, shares, rates, "
     "trends, follow-ups, and some no defined metric answers."),
    ("hard", "Hard to interpret", "Questions hard to read without knowing the business: jargon, "
     "periods, unstated filters, ambiguous follow-ups. Hard for an AI that lacks our definitions, "
     "not necessarily harder SQL."),
]

# Plain-language approaches, most native first.  Each pools the setups that implement it; the
# setup with the most right answers on a set stands for the approach on that set.
APPROACHES = [
    ("Google's data agent, tables only", ["bq"], ["native-bare"],
     "Google's data agent pointed at our tables, with nothing else."),
    ("Google's data agent + Google's catalog", ["bq", "catalog"], ["native-kc", "native-kc-max", "native-kc-reach"],
     "Google's data agent grounded by Google's catalog, which imports our metric definitions."),
    ("Google's data agent + generated definitions", ["bq", "doc"], ["native-context-bare", "native-context"],
     "Google's data agent given business definitions written automatically from our metric layer."),
    ("Google's data agent + purpose-built tables", ["bq", "table"], ["native-governed", "native-shaped", "native-graph"],
     "Google's data agent over tables, views or a graph we build from our metrics."),
    ("Our agent on Google's tools", ["adk", "mcp"], ["native-mcp", "custom-toolbox"],
     "An agent we build, calling Google's managed data tools."),
    ("Our agent writing its own SQL", ["adk", "sql"], ["baseline"],
     "An agent we build that writes its own database queries, as most teams start."),
    ("Our agent on Lightdash", ["adk", "lightdash"], ["custom-lightdash"],
     "An agent we build, querying metrics through Lightdash's free API."),
    ("Our agent on our metric layer", ["adk", "metric"], ["custom-metricflow", "custom-metricflow-compute"],
     "An agent we build that answers only through our defined metrics."),
    ("Our agent on our metric layer, SQL as fallback", ["adk", "metric", "sql"], ["custom-hybrid"],
     "Our metric-layer agent, allowed to write SQL when no metric answers, and saying so."),
]
# Another harness (Claude Code) and a setup that repeats another: in results.json, not on the page.
LEFT_OUT = {"cc-metricflow", "cc-metricflow-compute", "cc-native-mcp", "native-context-python"}

COLUMNS = [  # key, header, mark class, tooltip
    ("right", "Right", "d-ok", "The number matches the warehouse."),
    ("declined", "Couldn't answer", "d-no", "No number: it said it cannot answer, or asked which meaning."),
    ("wrong", "Wrong", "d-warn", "A wrong number it flagged as uncertain, or an answer with no clear number."),
    ("sure_wrong", "Wrong & sure", "d-bad", "A wrong number stated as fact, with no warning."),
]

ICON_NAMES = {"bq": "BigQuery", "adk": "Agent Development Kit", "mcp": "Model Context Protocol",
              "lightdash": "Lightdash", "catalog": "Catalog", "doc": "Definitions", "table": "Tables",
              "metric": "Metric layer", "sql": "SQL"}
LOGO_FILES = {"bq": "googlebigquery.svg", "adk": "adk.svg", "mcp": "mcp.svg", "lightdash": "lightdash.svg"}
# Plain marks where no official logo exists (MetricFlow has none) or none is meant (a concept).
GLYPHS = {
    "catalog": '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h11"/><path d="M9 8h6"/>',
    "doc": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M10 12h5M10 16h5"/>',
    "table": '<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M4 10h16M4 14.5h16M10 10v9"/>',
    "metric": '<path d="M4 19h16"/><path d="M7 19v-5M12 19V8M17 19v-9"/><circle cx="12" cy="5" r="1.4"/>',
    "sql": '<path d="m9 8-4 4 4 4M15 8l4 4-4 4"/><path d="m13 6-2 12"/>',
}


def per100(outcomes, runs):
    """Outcome counts over runs as whole answers out of 100 (largest remainder, so they sum to 100)."""
    groups = {"right": outcomes.get("right", 0), "declined": outcomes.get("declined", 0),
              "wrong": outcomes.get("wrong", 0) + outcomes.get("unclear", 0),
              "sure_wrong": outcomes.get("confident-wrong", 0)}
    raw = {k: 100 * v / runs for k, v in groups.items()}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - int(raw[k]), reverse=True)[: 100 - sum(out.values())]:
        out[k] += 1
    return out


def stands_for(arms, names, setname):
    """The complete run of a pooled setup with the largest share right on a set, or None."""
    rows = [a for a in arms if a["set"] == setname and a["arm"] in names and a["cases"] == a["of_cases"]]
    return max(rows, key=lambda a: (a["outcomes"].get("right", 0) / a["runs"], a["runs"])) if rows else None


def table_rows(arms, setname):
    rows = []
    for rank, (name, icons, names, plain) in enumerate(APPROACHES):
        arm = stands_for(arms, names, setname)
        rows.append({"rank": rank, "name": name, "icons": icons, "plain": plain,
                     "counts": per100(arm["outcomes"], arm["runs"]) if arm else None})
    return rows


def icon(key):
    label = ICON_NAMES[key]
    if key in LOGO_FILES:
        svg = (HERE / "logos" / LOGO_FILES[key]).read_text().strip()
        svg = svg.replace("<svg ", f'<svg class="logo" role="img" aria-label="{label}" fill="currentColor" ', 1)
        return re.sub(r'\s(width|height)="\d+"', "", svg, count=2)
    return (f'<svg class="logo glyph" role="img" aria-label="{label}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{GLYPHS[key]}</svg>')


def dots(c):
    marks = "".join(f'<i class="{cls}"></i>' * c[key] for key, _, cls, _ in COLUMNS)
    label = ", ".join(f"{c[key]} {head.lower()}" for key, head, _, _ in COLUMNS)
    return f'<span class="dots" role="img" aria-label="{label}, out of 100">{marks}</span>'


def render_table(rows, setname, hidden):
    heads = "".join(
        f'<th scope="col" class="num" aria-sort="none"><button type="button" data-key="{k}" title="{html.escape(tip)}">'
        f'<i class="{cls}"></i>{html.escape(h)}</button></th>' for k, h, cls, tip in COLUMNS)
    body = []
    for r in rows:
        c = r["counts"]
        cells = (f'<td class="dots-cell">{dots(c)}</td>' + "".join(f'<td class="num k-{k}">{c[k]}</td>' for k, *_ in COLUMNS)
                 if c else '<td class="dots-cell">Not run on this set</td>' + "".join(f'<td class="num k-{k}">–</td>' for k, *_ in COLUMNS))
        data = " ".join(f'data-{k.replace("_", "-")}="{c[k] if c else -1}"' for k, *_ in COLUMNS)
        body.append(
            f'<tr data-rank="{r["rank"]}" {data}><th scope="row"><span class="cell" title="{html.escape(r["plain"])}">'
            f'<span class="icons">{"".join(icon(i) for i in r["icons"])}</span>'
            f'<span class="name">{html.escape(r["name"])}<span class="sr">. {html.escape(r["plain"])}</span></span>'
            f'</span></th>{cells}</tr>')
    return (f'<table class="approaches" data-set="{setname}"{" hidden" if hidden else ""}>'
            f'<thead><tr><th scope="col" aria-sort="none"><button type="button" data-key="rank" '
            f'title="Most native first">Approach</button></th><th scope="col" class="dots-head"><span class="hd">100 answers</span></th>{heads}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def build(results):
    data = json.loads(Path(results).read_text())
    arms = [a for a in data["arms"] if a["arm"] not in LEFT_OUT]
    pooled = {n for _, _, names, _ in APPROACHES for n in names}
    unmapped = sorted({a["arm"] for a in arms} - pooled)
    if unmapped:
        raise SystemExit(f"setups with no approach on the page: {', '.join(unmapped)}")
    sets = [(s, label, tip, len(data["sets"][s]["cases"])) for s, label, tip in SETS]
    toggle = "".join(
        f'<button type="button" data-set="{s}" aria-pressed="{"true" if i == 0 else "false"}" title="{html.escape(tip)}">'
        f'{html.escape(label)} <b>{n}</b></button>' for i, (s, label, tip, n) in enumerate(sets))
    tables = "".join(render_table(table_rows(arms, s), s, i > 0) for i, (s, *_) in enumerate(sets))
    page = (HERE / "template.html").read_text()
    return page.replace("@@TOGGLE@@", toggle).replace("@@TABLES@@", tables)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("results", nargs="?", default=str(HERE.parent / "results.json"))
    p.add_argument("--out", default=str(HERE / "index.html"))
    args = p.parse_args()
    Path(args.out).write_text(build(args.results))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
