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
    (
        "frozen",
        "Everyday",
        (
            "Plain business questions across the domains: totals, shares, rates, "
            "trends, follow-ups, and some no defined metric answers."
        ),
    ),
    (
        "hard",
        "Hard to interpret",
        (
            "Questions hard to read without knowing the business: jargon, "
            "periods, unstated filters, ambiguous follow-ups. Hard for an AI that lacks our definitions, "
            "not necessarily harder SQL."
        ),
    ),
]

# Plain-language approaches, most native first.  Each pools the setups that implement it; the
# setup with the most right answers on a set stands for the approach on that set.
APPROACHES = [
    (
        "Google's data agent, tables only",
        ["bq"],
        ["native-bare"],
        "Google's data agent pointed at our tables, with nothing else.",
    ),
    (
        "Google's data agent + Google's catalog",
        ["bq", "catalog"],
        ["native-kc", "native-kc-max", "native-kc-reach"],
        "Google's data agent grounded by Google's catalog, which imports our metric definitions.",
    ),
    (
        "Google's data agent + generated definitions",
        ["bq", "doc"],
        ["native-context-bare", "native-context"],
        "Google's data agent given business definitions written automatically from our metric layer.",
    ),
    (
        "Google's data agent + purpose-built tables",
        ["bq", "table"],
        ["native-governed", "native-shaped", "native-graph"],
        "Google's data agent over tables, views or a graph we build from our metrics.",
    ),
    (
        "Our agent on Google's tools",
        ["adk", "mcp"],
        ["native-mcp", "custom-toolbox"],
        "An agent we build, calling Google's managed data tools.",
    ),
    (
        "Our agent writing its own SQL",
        ["adk", "sql"],
        ["baseline"],
        "An agent we build that writes its own database queries, as most teams start.",
    ),
    (
        "Our agent on Lightdash",
        ["adk", "lightdash"],
        ["custom-lightdash"],
        "An agent we build, querying metrics through Lightdash's free API.",
    ),
    (
        "Our agent on our metric layer",
        ["adk", "metric"],
        ["custom-metricflow", "custom-metricflow-compute"],
        "An agent we build that answers only through our defined metrics.",
    ),
    (
        "Our agent on our metric layer, SQL as fallback",
        ["adk", "metric", "sql"],
        ["custom-hybrid"],
        "Our metric-layer agent, allowed to write SQL when no metric answers, and saying so.",
    ),
]
# Another harness (Claude Code) and a setup that repeats another: in results.json, not on the page.
LEFT_OUT = {"cc-metricflow", "cc-metricflow-compute", "cc-native-mcp", "native-context-python"}

COLUMNS = [  # key, header, mark class, tooltip
    ("right", "Right", "d-ok", "The number matches the warehouse."),
    ("declined", "Couldn't answer", "d-no", "No number: it said it cannot answer, or asked which meaning."),
    ("wrong", "Wrong", "d-warn", "A wrong number it flagged as uncertain, or an answer with no clear number."),
    ("sure_wrong", "Wrong & sure", "d-bad", "A wrong number stated as fact, with no warning."),
]

ICON_NAMES = {
    "bq": "BigQuery",
    "adk": "Agent Development Kit",
    "mcp": "Model Context Protocol",
    "lightdash": "Lightdash",
    "catalog": "Catalog",
    "doc": "Definitions",
    "table": "Tables",
    "metric": "Metric layer",
    "sql": "SQL",
}
LOGO_FILES = {"bq": "googlebigquery.svg", "adk": "adk.svg", "mcp": "mcp.svg", "lightdash": "lightdash.svg"}
# Plain marks where no official logo exists (MetricFlow has none) or none is meant (a concept).
GLYPHS = {
    "catalog": (
        '<path d="M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3z"/><path d="M5 17a3 3 0 0 1 3-3h11"/><path d="M9 8h6"/>'
    ),
    "doc": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M10 12h5M10 16h5"/>',
    "table": '<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M4 10h16M4 14.5h16M10 10v9"/>',
    "metric": '<path d="M4 19h16"/><path d="M7 19v-5M12 19V8M17 19v-9"/><circle cx="12" cy="5" r="1.4"/>',
    "sql": '<path d="m9 8-4 4 4 4M15 8l4 4-4 4"/><path d="m13 6-2 12"/>',
}


def per100(outcomes, runs):
    """Outcome counts over runs as whole answers out of 100 (largest remainder, so they sum to 100)."""
    groups = {
        "right": outcomes.get("right", 0),
        "declined": outcomes.get("declined", 0),
        "wrong": outcomes.get("wrong", 0) + outcomes.get("unclear", 0),
        "sure_wrong": outcomes.get("confident-wrong", 0),
    }
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
        rows.append(
            {
                "rank": rank,
                "name": name,
                "icons": icons,
                "plain": plain,
                "counts": per100(arm["outcomes"], arm["runs"]) if arm else None,
            }
        )
    return rows


def icon(key):
    label = ICON_NAMES[key]
    if key in LOGO_FILES:
        svg = (HERE / "logos" / LOGO_FILES[key]).read_text().strip()
        svg = svg.replace("<svg ", f'<svg class="logo" role="img" aria-label="{label}" fill="currentColor" ', 1)
        return re.sub(r'\s(width|height)="\d+"', "", svg, count=2)
    return (
        f'<svg class="logo glyph" role="img" aria-label="{label}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{GLYPHS[key]}</svg>'
    )


def dots(c):
    marks = "".join(f'<i class="{cls}"></i>' * c[key] for key, _, cls, _ in COLUMNS)
    label = ", ".join(f"{c[key]} {head.lower()}" for key, head, _, _ in COLUMNS)
    return f'<span class="dots" role="img" aria-label="{label}, out of 100">{marks}</span>'


SORT_ICON = (
    '<svg class="sort" viewBox="0 0 10 14" aria-hidden="true" fill="none" stroke="currentColor" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path class="up" d="M1.5 5 5 1.5 8.5 5"/>'
    '<path class="dn" d="M1.5 9 5 12.5 8.5 9"/></svg>'
)


def tip(tid, text):
    """The definition shown on hover or focus: the visible bubble is drawn by the page script from data-tip;
    this copy, kept in a hidden block outside the table, is what assistive technology reads (aria-describedby)."""
    return f'<span id="{tid}">{html.escape(text)}</span>'


def render_table(rows, setname, hidden):
    order_tip = "From the most native (Google's own data agent) to the most custom (an agent the team builds)."
    heads = "".join(
        f'<th scope="col" class="num" data-key="{k}" aria-sort="none"><button type="button" data-key="{k}" '
        f'data-tip="{html.escape(t)}" aria-describedby="t-{setname}-{k}">'
        f'<i class="{cls}"></i>{html.escape(h)}{SORT_ICON}</button>'
        "</th>"
        for k, h, cls, t in COLUMNS
    )
    descs = [tip(f"t-{setname}-rank", order_tip)] + [tip(f"t-{setname}-{k}", t) for k, _, _, t in COLUMNS]
    body = []
    for r in rows:
        c = r["counts"]
        cells = (
            f'<td class="dots-cell">{dots(c)}</td>' + "".join(f'<td class="num k-{k}">{c[k]}</td>' for k, *_ in COLUMNS)
            if c
            else '<td class="dots-cell">Not run on this set</td>'
            + "".join(f'<td class="num k-{k}">–</td>' for k, *_ in COLUMNS)
        )
        data = " ".join(f'data-{k.replace("_", "-")}="{c[k] if c else -1}"' for k, *_ in COLUMNS)
        rid = f"d-{setname}-{r['rank']}"
        body.append(
            f'<tr data-rank="{r["rank"]}" {data}><th scope="row"><span class="stop" aria-hidden="true"></span>'
            f'<span class="cell" tabindex="0" data-tip="{html.escape(r["plain"])}" aria-describedby="{rid}">'
            f'<span class="icons">{"".join(icon(i) for i in r["icons"])}</span>'
            f'<span class="name">{html.escape(r["name"])}</span></span></th>{cells}</tr>'
        )
        descs.append(tip(rid, r["plain"]))
    return (
        f'<table class="approaches" data-set="{setname}" data-route="on"{" hidden" if hidden else ""}>'
        f'<thead><tr><th scope="col" class="name-head" data-key="rank" aria-sort="ascending">'
        f'<button type="button" data-key="rank" '
        f'data-tip="{html.escape(order_tip)}" aria-describedby="t-{setname}-rank">Approach{SORT_ICON}</button>'
        f'</th><th scope="col" class="dots-head">100 answers</th>{heads}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table><div hidden>{''.join(descs)}</div>"
    )


MODEL_NAMES = [
    (":free", "A free model"),
    ("haiku", "Claude Haiku"),
    ("sonnet", "Claude Sonnet"),
    ("opus", "Claude Opus"),
]
# The programs that run the same agent, in plain words (Takeaway: the program running the AI matters too).
HARNESSES = [
    ("custom-metricflow", "adk-anthropic-api", "claude-haiku-5-5", "Google's agent kit (ADK)"),
    ("cc-metricflow", "claude-code-headless", "claude-code-strict (haiku)", "Claude Code, run as a script"),
    ("cc-metricflow", "claude-code-subagent", "claude-code (fresh-haiku)", "Claude Code, started by another agent"),
]


def model_name(model):
    return next((name for key, name in MODEL_NAMES if key in model), model)


def right100(arm):
    return round(100 * arm["outcomes"].get("right", 0) / arm["runs"])


def whole(arms, setname):
    return [a for a in arms if a["set"] == setname and a["cases"] == a["of_cases"]]


def unclear_note(runs, arm):
    """Why a score on covered questions sits under 100, when the gap is answers still awaiting the judge."""
    covered = [
        r
        for r in runs
        if r["arm"] == arm["arm"]
        and r["model"] == arm["model"]
        and r["set"] == arm["set"]
        and "covered" in r.get("groups", [])
    ]
    unclear = sum(r["outcome"] == "unclear" for r in covered)
    missed = sum(r["outcome"] != "right" for r in covered)
    if not unclear:
        return ""
    lead = (
        f"{unclear} of {len(covered)} answers here"
        if unclear == missed
        else f"{unclear} of the {missed} answers not counted right"
    )
    return (
        f"{lead} were scored unclear: the automatic check could not read them and the judging model has not "
        "settled them yet, so they count as not right for now."
    )


def takeaways(data, runs=()):
    """Plain-language observations over results.json; each is left out when its runs are missing.

    Each entry: key, headline, body, and the figures its picture draws.
    """
    every, out = data["arms"], []
    arm_name = {n: name for name, _, names, _ in APPROACHES for n in names}
    everyday = whole(every, "frozen")

    # The free model's best setup within each approach, so each figure matches a row's name on the table.
    best_free = {}
    for a in everyday:
        if a["model"].endswith(":free") and a["arm"] in arm_name:
            name = arm_name[a["arm"]]
            if name not in best_free or right100(a) > right100(best_free[name]):
                best_free[name] = a
    free = list(best_free.values())
    one_setup = sorted(
        (a for a in everyday if a["arm"] == "native-mcp" and a["harness"].startswith("adk")), key=lambda a: right100(a)
    )
    if len(free) > 1 and len(one_setup) > 1:
        lo, hi = min(free, key=right100), max(free, key=right100)
        out.append(
            {
                "key": "setup",
                "headline": "The setup moves the score more than the AI model",
                "body": f"With one free model, the setups ranged from {right100(lo)} to {right100(hi)} "
                f"right answers in 100. "
                f"With one setup, {len(one_setup)} models ranged from {right100(one_setup[0])} "
                f"to {right100(one_setup[-1])}.",
                "ranges": [
                    {
                        "label": "Same AI model, different setups",
                        "lo": right100(lo),
                        "hi": right100(hi),
                        "lo_name": arm_name[lo["arm"]],
                        "hi_name": arm_name[hi["arm"]],
                    },
                    {
                        "label": "Same setup, different AI models",
                        "lo": right100(one_setup[0]),
                        "hi": right100(one_setup[-1]),
                        "lo_name": model_name(one_setup[0]["model"]),
                        "hi_name": model_name(one_setup[-1]["model"]),
                    },
                ],
            }
        )

    strict = {
        model_name(a["model"]): a
        for a in everyday
        if a["arm"] == "custom-metricflow" and a["harness"].startswith("adk")
    }
    order = [name for _, name in MODEL_NAMES if name in strict]
    if len(order) > 1:
        rows = [
            {
                "model": m,
                "covered": round(100 * strict[m]["groups"]["covered"][0]),
                "covered_note": unclear_note(runs, strict[m]),
                "uncovered": round(100 * strict[m]["groups"]["uncovered"][0]),
            }
            for m in order
        ]
        n = strict[order[0]]["groups"]["uncovered"][1]
        cov = [r["covered"] for r in rows]
        out.append(
            {
                "key": "rules",
                "headline": "A pricier model can score lower by following the rules",
                "body": f"Told to answer only through our metrics, every model got the questions a metric covers right "
                f"({min(cov)} to {max(cov)} in 100). On the {n} questions no metric covers, the pricier models "
                f"declined, as told, and so scored lower.",
                "models": rows,
            }
        )

    pair = {}
    for key, names in (("without", ["native-bare"]), ("with", ["native-context-bare", "native-context"])):
        got = [stands_for(every, names, s) for s, *_ in SETS]
        if all(got):
            pair[key] = [per100(a["outcomes"], a["runs"]) for a in got]
    if len(pair) == 2:
        (wo_e, wo_h), (w_e, w_h) = pair["without"], pair["with"]
        out.append(
            {
                "key": "definitions",
                "headline": "Questions are hard to interpret only without our definitions",
                "body": f"Without definitions, Google's data agent fell from {wo_e['right']} to {wo_h['right']} "
                f"right in 100 "
                f"on hard-to-interpret questions, and wrong and sure rose from {wo_e['sure_wrong']} to "
                f"{wo_h['sure_wrong']}. With them it held at {w_e['right']} and {w_h['right']}.",
                "lines": [
                    {"label": "Without definitions", "everyday": wo_e, "hard": wo_h},
                    {"label": "With generated definitions", "everyday": w_e, "hard": w_h},
                ],
            }
        )

    hard = whole(every, "hard")
    runs = []
    for arm, harness, model, label in HARNESSES:
        a = next((a for a in hard if a["arm"] == arm and a["harness"] == harness and a["model"] == model), None)
        if a:
            runs.append({"label": label, "right": right100(a)})
    if len(runs) == len(HARNESSES):
        out.append(
            {
                "key": "harness",
                "headline": "The program running the AI matters too",
                "body": "Same tools, same rule, same model (Claude Haiku): on hard-to-interpret questions it got "
                + ", ".join(str(r["right"]) for r in runs[:-1])
                + f" or {runs[-1]['right']} right in 100, "
                "depending on the program running it.",
                "programs": runs,
            }
        )
    return out


SR = '<span class="sr">{}</span>'.format


def tipped(tid, text, inner, cls="tipped"):
    """A focusable word or number that shows its definition in the page's bubble (data-tip + aria-describedby)."""
    return (
        f'<span class="{cls}" tabindex="0" data-tip="{html.escape(text)}" aria-describedby="{tid}">{inner}</span>',
        tip(tid, text),
    )


def spread(values, gap=18):
    """Label heights on a 0-100 scale, pushed at least `gap` apart and kept inside 0-100.

    Two numbers drawn this close never overlap.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    at = [float(values[i]) for i in order]
    for i in range(1, len(at)):
        at[i] = max(at[i], at[i - 1] + gap)
    if at and at[-1] > 100:
        at[-1] = 100.0
        for i in range(len(at) - 2, -1, -1):
            at[i] = min(at[i], at[i + 1] - gap)
    out = [0.0] * len(values)
    for i, v in zip(order, at, strict=True):
        out[i] = round(v, 1)
    return out


def bar(v, sr_before="", note=None):
    """One right-answers-in-100 bar: the track is the whole 100, the fill is the share right.

    `note` is (id, text, descs): the number then shows `text` in the page's bubble on hover, focus or tap.
    """
    num = f"<b>{v}</b>"
    if note:
        tid, text, descs = note
        num, d = tipped(tid, text, num, "tipped num-tip")
        descs.append(d)
    return (
        f'<span class="bar">{SR(html.escape(sr_before)) if sr_before else ""}'
        f'<span class="track" aria-hidden="true"><span class="fill" style="--v:{v}"></span></span>'
        f"{num}{SR(' right in 100')}</span>"
    )


def pic_setup(t, descs):
    rows = []
    for i, r in enumerate(t["ranges"]):
        at_lo, at_hi = spread([r["lo"], r["hi"]], gap=16)
        lo, d1 = tipped(f"t-tk-setup-{i}-lo", r["lo_name"], str(r["lo"]), "end tipped")
        hi, d2 = tipped(f"t-tk-setup-{i}-hi", r["hi_name"], str(r["hi"]), "end tipped")
        descs += [d1, d2]
        rows.append(
            f'<div class="rng"><span class="pl">{html.escape(r["label"])}</span>'
            '<span class="ruler"><span class="axis" aria-hidden="true">0</span>'
            f'<span class="scale" style="--lo:{r["lo"]};--hi:{r["hi"]}"><span class="span" aria-hidden="true"></span>'
            f'{SR(" ranged from ")}<span class="at" style="--p:{at_lo}">{lo}</span>{SR(" to ")}'
            f'<span class="at" style="--p:{at_hi}">{hi}</span>{SR(" right in 100")}</span>'
            '<span class="axis" aria-hidden="true">100</span></span></div>'
        )
    return f'<div class="pic pic-setup">{"".join(rows)}</div>'


def pic_rules(t, descs):
    heads = ("Questions a metric covers", "Questions no metric covers")
    rows = []
    for i, m in enumerate(t["models"]):
        note = (f"t-tk-rules-{i}", m["covered_note"], descs) if m.get("covered_note") else None
        rows.append(
            f'<li><span class="pl">{html.escape(m["model"])}</span>'
            f"{bar(m['covered'], heads[0] + ': ', note)}{bar(m['uncovered'], heads[1] + ': ')}</li>"
        )
    rows = "".join(rows)
    cols = "".join(f"<span>{h}</span>" for h in heads)
    return f'<div class="pic pic-rules"><div class="heads" aria-hidden="true">{cols}</div><ul>{rows}</ul></div>'


def pic_definitions(t, descs):
    panels, said = [], []
    for line in t["lines"]:
        e, h = line["everyday"], line["hard"]
        left, right = spread([e["right"], e["sure_wrong"]]), spread([h["right"], h["sure_wrong"]])
        lines = "".join(
            f'<line class="ln {cls}" x1="0" y1="{100 - a}" x2="100" y2="{100 - b}" vector-effect="non-scaling-stroke"/>'
            for cls, a, b in (("ln-bad", e["sure_wrong"], h["sure_wrong"]), ("ln-ok", e["right"], h["right"]))
        )
        marks = "".join(
            f'<i class="pt {cls}" style="--x:{x};--y:{v[k]}"></i>'
            for k, cls in (("sure_wrong", "d-bad"), ("right", "d-ok"))
            for x, v in ((0, e), (100, h))
        )
        nums = "".join(
            f'<b class="n {side}" style="--y:{y}">{v}</b>'
            for side, vals, ys in (
                ("l", (e["right"], e["sure_wrong"]), left),
                ("r", (h["right"], h["sure_wrong"]), right),
            )
            for v, y in zip(vals, ys, strict=True)
        )
        panels.append(
            f'<div class="slope"><span class="pl" aria-hidden="true">{html.escape(line["label"])}</span>'
            '<div class="plot" aria-hidden="true">'
            '<svg viewBox="0 0 100 100" preserveAspectRatio="none" focusable="false">'
            f"{lines}</svg>{marks}{nums}</div>"
            f'<div class="xl" aria-hidden="true"><span>{SETS[0][1]}</span><span>{SETS[1][1]}</span></div></div>'
        )
        said.append(
            f"{line['label']}: {SETS[0][1].lower()} questions {e['right']} right and {e['sure_wrong']} wrong and sure; "
            f"{SETS[1][1].lower()} questions {h['right']} right and {h['sure_wrong']} wrong and sure, in 100."
        )
    key = []
    for k, head, cls, text in COLUMNS:
        if k in ("right", "sure_wrong"):
            el, d = tipped(f"t-tk-def-{k}", text, f'<i class="{cls}" aria-hidden="true"></i>{html.escape(head)}')
            key.append(el)
            descs.append(d)
    return (
        f'<div class="pic pic-definitions"><div class="slopes">{"".join(panels)}</div>'
        f'<p class="sr">{html.escape(" ".join(said))}</p><p class="key">{"".join(key)}</p></div>'
    )


def pic_harness(t):
    rows = "".join(
        f'<li><span class="pl">{html.escape(r["label"])}</span>{bar(r["right"])}</li>' for r in t["programs"]
    )
    return f'<div class="pic pic-harness"><ul>{rows}</ul></div>'


def render_takeaways(items):
    """Each takeaway as one row under the table: its headline and sentence, and one small picture of its figures.

    Every picture is drawn on the same 0-100 scale as the table; text stays HTML so it keeps the page's two sizes.
    """
    if not items:
        return ""
    descs, rows = [], []
    for t in items:
        k = t["key"]
        if k == "setup":
            pic = pic_setup(t, descs)
        elif k == "definitions":
            pic = pic_definitions(t, descs)
        elif k == "rules":
            pic = pic_rules(t, descs)
        else:
            pic = pic_harness(t)
        rows.append(
            f'<li data-key="{k}"><div class="tk-text"><h3>{html.escape(t["headline"])}</h3>'
            f"<p>{html.escape(t['body'])}</p></div>{pic}</li>"
        )
    return (
        '<section class="takeaways" aria-labelledby="takeaways-h">'
        f'<h2 id="takeaways-h">Takeaways</h2><ul class="tk">{"".join(rows)}</ul>'
        f"<div hidden>{''.join(descs)}</div></section>"
    )


def scored_runs(results, data):
    """The per-run log beside results.json (scored-runs.jsonl), each run tagged with its question's groups."""
    path = Path(results).parent / "scored-runs.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        r = json.loads(line)
        r["groups"] = data["sets"].get(r["set"], {}).get("groups", {}).get(r["case"], [])
        out.append(r)
    return out


def build(results):
    data = json.loads(Path(results).read_text())
    arms = [a for a in data["arms"] if a["arm"] not in LEFT_OUT]
    pooled = {n for _, _, names, _ in APPROACHES for n in names}
    unmapped = sorted({a["arm"] for a in arms} - pooled)
    if unmapped:
        raise SystemExit(f"setups with no approach on the page: {', '.join(unmapped)}")
    sets = [(s, label, tip, len(data["sets"][s]["cases"])) for s, label, tip in SETS]
    toggle = "".join(
        f'<button type="button" data-set="{s}" aria-pressed="{"true" if i == 0 else "false"}" '
        f'data-tip="{html.escape(f"{n} questions. {t}")}" '
        f'aria-describedby="t-set-{s}">{html.escape(label)} <b>{n}<span class="sr"> questions</span></b></button>'
        for i, (s, label, t, n) in enumerate(sets)
    ) + (f"<div hidden>{''.join(tip(f't-set-{s}', f'{n} questions. {t}') for s, _, t, n in sets)}</div>")
    tables = "".join(render_table(table_rows(arms, s), s, i > 0) for i, (s, *_) in enumerate(sets))
    page = (HERE / "template.html").read_text()
    return (
        page.replace("@@TOGGLE@@", toggle)
        .replace("@@TABLES@@", tables)
        .replace("@@TAKEAWAYS@@", render_takeaways(takeaways(data, scored_runs(results, data))))
    )


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("results", nargs="?", default=str(HERE.parent / "results.json"))
    p.add_argument("--out", default=str(HERE / "index.html"))
    args = p.parse_args()
    Path(args.out).write_text(build(args.results))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
