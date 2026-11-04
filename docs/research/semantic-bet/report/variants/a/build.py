#!/usr/bin/env python3
"""Build the semantic-bet research memo (variant A) from results.json.

Usage: python3 build.py RESULTS_JSON [LOG_DIR] [OUT_HTML]

RESULTS_JSON  docs/research/semantic-bet/results.json (or a snapshot of it).
LOG_DIR       directory holding the per-run logs eval-*.jsonl; defaults to the
              directory of RESULTS_JSON. Used only for one example answer per
              setup; the page builds without it.
OUT_HTML      defaults to index.html beside this script.

Standard library only. Every number on the page comes from RESULTS_JSON (or
the logs); prose that cites a number is a template filled here.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Facts that are not measurements and so are not in results.json.
# Each names where it comes from.
FREE_TRIAL_END = "2026-12-31"  # Gemini data agents bill $0.00 until then (BRIEF.md, cost hint)
POWER = {"frozen": 10, "hard": 15}  # smallest accuracy gap detected 4 in 5 at k = 3, findings/2026-11-03-356-hard-set.md
SET_LABEL = {"frozen": "Frozen set", "hard": "Hard set"}
GROUPS = [("covered", "Covered"), ("trap", "Hidden-rule"), ("uncovered", "Uncovered"), ("conversation", "Conversation")]

# What each setup is, in plain words (no numbers).
DESC = {
    "native-bare": "Google's data agent over the tables alone: no descriptions, catalog, glossary or examples.",
    "native-kc": "Google's data agent grounded by Knowledge Catalog's import of our dbt metrics.",
    "native-kc-max": "The catalog agent plus BigQuery column descriptions and a glossary linked to the columns.",
    "native-kc-reach": "The catalog agent given the same tables and legacy schema as the context setups.",
    "native-context-bare": "Google's data agent with written context we generate from MetricFlow.",
    "native-context": "The generated-context agent plus verified example queries.",
    "native-governed": "Google's data agent over governed tables we build from the metrics.",
    "native-shaped": "Google's data agent over views, table functions and verified queries.",
    "native-graph": "Google's data agent with a property graph and its measures beside the tables.",
    "native-mcp": "Our ADK agent calling Google's Knowledge Catalog and BigQuery MCP servers.",
    "custom-toolbox": "Our ADK agent on generated MCP Toolbox tools over table functions.",
    "custom-metricflow": "Our ADK agent on MetricFlow tools; it declines what no metric covers.",
    "custom-lightdash": "Our ADK agent with one tool on Lightdash's free metric query API.",
    "custom-hybrid": "MetricFlow tools first, then a read-only SQL fallback that says so.",
    "cc-metricflow": "The same MetricFlow tools called by a Claude Code subagent; another harness, descriptive only.",
    "baseline": "Plain text-to-SQL that reads the generated docs.",
}

FAMILY = {
    "native-bare": "da", "native-kc": "da", "native-kc-max": "da", "native-kc-reach": "da",
    "native-context-bare": "da", "native-context": "da", "native-governed": "da",
    "native-shaped": "da", "native-graph": "da",
    "native-mcp": "gt", "custom-toolbox": "gt",
    "custom-metricflow": "mf", "custom-lightdash": "mf", "custom-hybrid": "mf", "cc-metricflow": "mf",
    "baseline": "ref",
}
FAMILY_LABEL = {
    "da": "Google's managed data agent",
    "gt": "Our ADK agent on Google's tools",
    "mf": "Our agent on a semantic-layer server",
    "ref": "Text-to-SQL baseline",
}

# The cost ladder in the owner's plain words, cheapest first (RULE.md § The cost ladder, BRIEF.md).
LADDER = [
    ("ref", "Reference: plain text-to-SQL", ["baseline"]),
    ("L1", "Bare data agent, tables only (the floor)", ["native-bare"]),
    ("L2", "Plus catalog context: import, descriptions, glossary", ["native-kc", "native-kc-max", "native-kc-reach"]),
    ("L3", "Plus context generated from MetricFlow", ["native-context-bare", "native-context"]),
    ("L4", "Plus warehouse objects: governed tables, table functions, graph", ["native-governed", "native-shaped", "native-graph"]),
    ("L5", "Our ADK agent on Google's MCP servers or generated tools", ["native-mcp", "custom-toolbox"]),
    ("L6", "Our ADK agent on a semantic-layer server", ["custom-metricflow", "custom-lightdash"]),
    ("L7", "The hybrid: MetricFlow first, SQL fallback", ["custom-hybrid"]),
    ("L8", "If compile_query ships in Google's backend", []),
    ("cc", "Another harness: Claude Code subagents on MetricFlow", ["cc-metricflow"]),
]
FREE = "nvidia/nemotron-3.5-super-vl:free"
MIN_CASES_TO_PLOT = 5


def model_info(model):
    """(short label, role) for a model string."""
    if model == FREE:
        return "Nemotron free", "decides"
    m = re.match(r"claude-(haiku|sonnet|opus)-", model)
    if m:
        return m.group(1).capitalize(), "check"
    m = re.match(r"claude-code \((.+)\)", model)
    if m:
        name = m.group(1)
        fresh = name.startswith("fresh-")
        base = name.replace("fresh-", "").capitalize()
        return "Claude Code " + base + (", fresh sessions" if fresh else ""), "cc"
    m = re.match(r"google-data-agent \((.+)\)", model)
    if m:
        parts = [p.strip() for p in m.group(1).split(",")]
        names = {"MODEL_UNSPECIFIED": "default", "LATEST_GA_MODEL": "latest GA", "THINKING": "thinking", "FAST": "fast"}
        return "Gemini " + ", ".join(names.get(p, p.lower()) for p in parts), "gemini"
    return model, "other"


def spend_by_arm(spend, arm_names):
    """Sum Claude dollars per (set, arm, model) from the pass names."""
    out, unmatched = {}, []
    for name, rec in spend.items():
        low = name.lower()
        if low.startswith("probe") or "smoke" in low:
            unmatched.append((name, rec["usd"], "probe or smoke test"))
            continue
        tokens = re.split(r"[\s,()]+", low)
        arm = next((t for t in tokens if t in arm_names), None)
        st = "hard" if "hard" in tokens else "frozen"
        if not arm:
            unmatched.append((name, rec["usd"], "no setup named"))
            continue
        key = (st, arm, rec["model"])
        out[key] = out.get(key, 0.0) + rec["usd"]
    return out, unmatched


def strip_md(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_examples(log_dir):
    """One example answer per (set, arm, model): the first confident-wrong run,
    else the first declined, else wrong, else right."""
    rank = {"confident-wrong": 0, "declined": 1, "wrong": 2, "unclear": 3, "right": 4}
    best = {}
    for path in sorted(glob.glob(os.path.join(log_dir, "eval-*.jsonl"))):
        st = "hard" if os.path.basename(path).startswith("eval-hard") else "frozen"
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                key = (st, r.get("arm"), r.get("model"))
                oc = r.get("outcome")
                if oc not in rank:
                    continue
                turns = r.get("turns") or []
                turn = next((t for t in turns if t.get("outcome") == oc), turns[-1] if turns else None)
                if not turn or not turn.get("text"):
                    continue
                if key in best and rank[best[key]["outcome"]] <= rank[oc]:
                    continue
                text = strip_md(turn["text"])
                if len(text) > 260:
                    text = text[:257].rsplit(" ", 1)[0] + "..."
                tools = sorted({c.get("tool") for c in (turn.get("calls") or []) if c.get("tool")})
                best[key] = {"case": r.get("case"), "run": r.get("run"), "outcome": oc, "text": text, "tools": tools}
    return best


def pct(x):
    return round(100 * x)


def fmt_iv(v):
    return "%d%% [%d, %d]" % (pct(v[0]), pct(v[1]), pct(v[2]))


def pts(x):
    v = round(100 * x)
    return ("+" + str(v)) if v > 0 else ("\u2212" + str(-v)) if v < 0 else "0"


def build(results_path, log_dir, out_path):
    with open(results_path, encoding="utf-8") as fh:
        R = json.load(fh)
    arm_names = {a["arm"] for a in R["arms"]}
    spend, unmatched_spend = spend_by_arm(R.get("claude_spend_by_pass", {}), arm_names)
    examples = load_examples(log_dir) if log_dir and os.path.isdir(log_dir) else {}
    step2 = {(s["set"], s["arm"], s["model"]): s for s in R.get("step_two", [])}

    sets = {}
    for st in ("frozen", "hard"):
        mb_arm, mb_model, _ = R["managed_best"][st]
        rows = []
        for a in R["arms"]:
            if a["set"] != st:
                continue
            label, role = model_info(a["model"])
            expected = a["of_cases"] * 3
            partial = None
            if a["cases"] < a["of_cases"]:
                partial = "%d of %d cases, %d runs" % (a["cases"], a["of_cases"], a["runs"])
            elif a["runs"] < expected:
                partial = "%d of %d runs" % (a["runs"], expected)
            major = a["cases"] < a["of_cases"] or a["runs"] < 0.9 * expected
            usd = spend.get((st, a["arm"], a["model"]))
            if role == "gemini":
                cost = {"usd": 0.0, "label": "$0.00", "note": "Gemini free trial, until " + FREE_TRIAL_END}
            elif role == "decides":
                cost = {"usd": 0.0, "label": "$0.00", "note": "free model; %d requests" % a.get("model_calls", 0)}
            elif role == "cc":
                cost = {"usd": None, "label": "subscription", "note": "Claude Code on the owner's subscription; not metered"}
            elif usd is not None:
                cost = {"usd": usd, "per100": usd / a["runs"] * 100, "label": "$%.2f" % (usd / a["runs"] * 100),
                        "note": "$%.2f spent over this setup's passes, reruns included" % usd}
            else:
                cost = {"usd": None, "label": "n/a", "note": "no spend recorded for this pass"}
            s2 = step2.get((st, a["arm"], a["model"]))
            rows.append({
                "id": "%s|%s|%s" % (st, a["arm"], a["model"]),
                "arm": a["arm"], "model": a["model"], "modelLabel": label, "role": role,
                "family": FAMILY.get(a["arm"], "ref"), "desc": DESC.get(a["arm"], ""),
                "rung": a.get("rung"), "harness": a.get("harness"), "session": a.get("session"),
                "acc": a["accuracy"], "cw": a["confident_wrong"], "groups": a["groups"],
                "cases": a["cases"], "of": a["of_cases"], "runs": a["runs"], "expected": expected,
                "passAll": a.get("pass_all"), "outcomes": a["outcomes"], "calls": a.get("model_calls"),
                "partial": partial, "major": major, "plotted": a["cases"] >= MIN_CASES_TO_PLOT,
                "cost": cost, "example": examples.get((st, a["arm"], a["model"])),
                "managedBest": a["arm"] == mb_arm and a["model"] == mb_model,
                "step2": s2,
            })
        # Primary row per setup: the free model decides; a data agent shows the managed best's
        # model when it is that setup, else Gemini default; then Haiku, Sonnet, Opus, Claude Code.
        order = lambda r: (
            0 if r["role"] == "decides" else
            0 if r["managedBest"] else
            1 if r["model"].endswith("(MODEL_UNSPECIFIED)") else
            2 if "haiku" in r["model"] and r["role"] == "check" else
            3 if "sonnet" in r["model"] else 4 if "opus" in r["model"] else
            5 if r["role"] == "gemini" else 6,
            -r["cases"])
        for arm in {r["arm"] for r in rows}:
            cand = sorted([r for r in rows if r["arm"] == arm and r["plotted"]], key=order)
            if cand:
                cand[0]["primary"] = True
        for r in rows:
            r.setdefault("primary", False)

        mb = next(r for r in rows if r["managedBest"])
        floor = next(r for r in rows if r["arm"] == "native-bare" and r["primary"])
        mf = next((r for r in rows if r["arm"] == "custom-metricflow" and r["primary"]), None)
        sentences = make_sentences(st, rows, mb, floor, mf)
        sets[st] = {"rows": rows, "managedBest": mb["id"], "floor": floor["id"], "mf": mf["id"] if mf else None,
                    "sentences": sentences, "power": POWER[st],
                    "cases": max(r["of"] for r in rows),
                    "groupCases": {g: max((r["groups"].get(g, [0, 0])[1] for r in rows if r["cases"] == r["of"]), default=0) for g, _ in GROUPS},
                    "unplotted": [r["id"] for r in rows if not r["plotted"]]}

    row_keys = {(st, r["arm"], r["model"]) for st in sets for r in sets[st]["rows"]}
    for key, usd in spend.items():
        if key not in row_keys:
            unmatched_spend.append(("%s %s on %s" % key, usd, "no scored row"))
    data = {
        "written": R.get("written"), "rule": R.get("rule"), "sets": sets,
        "ladder": [{"key": k, "label": l, "arms": a} for k, l, a in LADDER],
        "groups": [{"key": k, "label": l} for k, l in GROUPS],
        "familyLabel": FAMILY_LABEL, "freeTrialEnd": FREE_TRIAL_END,
        "spendTotal": round(sum(v["usd"] for v in R.get("claude_spend_by_pass", {}).values()), 2),
        "spendUnmatched": [{"name": n, "usd": u, "why": w} for n, u, w in unmatched_spend],
        "stepThree": R.get("step_three", {}),
        "examplesLoaded": bool(examples),
    }
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    with open(os.path.join(HERE, "template.html"), encoding="utf-8") as fh:
        page = fh.read()
    page = page.replace("/*__DATA__*/null", payload)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("wrote %s (%d bytes, %d examples)" % (out_path, len(page), len(examples)))


def make_sentences(st, rows, mb, floor, mf):
    """Takeaway sentences, filled from the data for one set."""
    n = max(r["of"] for r in rows)
    def g(r, k):
        v = r["groups"].get(k)
        return pct(v[0]) if v else None
    S = {}
    mbname = "%s on %s" % (mb["arm"], mb["modelLabel"])
    if mf:
        s2 = mf["step2"]
        diff = ""
        if s2:
            a = s2["accuracy"]
            verdict = "an interval that excludes zero" if (a[1] > 0 or a[2] < 0) else "an interval that includes zero, so no difference"
            diff = ", a paired difference of %s points [%s, %s], %s" % (pts(a[0]), pts(a[1]), pts(a[2]), verdict)
        S["abstract"] = (
            "On the %s (%d questions), the best managed setup is %s at %s right. "
            "Our ADK agent on MetricFlow, on the free model that decides, is right on %s%s; "
            "it is confidently wrong on %d%% of runs against the managed best's %d%%."
            % (SET_LABEL[st].lower(), n, mbname, fmt_iv(mb["acc"]), fmt_iv(mf["acc"]), diff,
               pct(mf["cw"][0]), pct(mb["cw"][0])))
        def best_da(k):
            cand = [r for r in rows if r["family"] == "da" and r["plotted"] and k in r["groups"]]
            top = max(cand, key=lambda r: r["groups"][k][0])
            return g(top, k), top["arm"]
        def rel(x, y):
            return "level with" if abs(x - y) <= 5 else ("%d points above" % (x - y) if x > y else "%d points below" % (y - x))
        parts = []
        for k, name in (("covered", "covered"), ("trap", "hidden-rule"), ("uncovered", "uncovered")):
            v = g(mf, k)
            bv, barm = best_da(k)
            parts.append((name, v, bv, barm, rel(v, bv)))
        (n1, v1, b1, a1, r1), (n2, v2, b2, a2, r2), (n3, v3, b3, a3, r3) = parts
        S["map"] = ("On the free model, MetricFlow is %s the best managed agent on covered questions (%d%% right against %s's %d%%) and %s it on hidden-rule ones (%d%% against %d%%); "
                    "on uncovered questions, where it declines by design, it is %s (%d%% against %s's %d%%)."
                    % (r1, v1, a1, b1, r2, v2, b2, r3, v3, a3, b3))
        if s2:
            a = s2["accuracy"]
            ok = a[1] > 0 or a[2] < 0
            S["forest"] = ("Paired by case, the MetricFlow agent on the free model is %s points %s the managed best (%s), %s; "
                           "its confident-wrong rate is %s." % (abs(round(100 * a[0])), "below" if a[0] < 0 else "above", mbname,
                           "a difference the interval confirms" if ok else "a tie within this set's power",
                           fmt_iv(mf["cw"])))
        else:
            S["forest"] = "The MetricFlow agent on the free model scores %s against the managed best's %s." % (fmt_iv(mf["acc"]), fmt_iv(mb["acc"]))
    # Slope: range of the MetricFlow family on covered and uncovered, against the managed best.
    fam = [r for r in rows if r["family"] == "mf" and r["plotted"] and "covered" in r["groups"] and "uncovered" in r["groups"]]
    if fam:
        cov = [g(r, "covered") for r in fam]
        unc = [g(r, "uncovered") for r in fam]
        S["slope"] = ("Setups on a semantic-layer server are right on %d%% to %d%% of covered questions and drop to %d%% to %d%% on uncovered ones; "
                      "the managed best holds level, %d%% and %d%%." % (min(cov), max(cov), min(unc), max(unc), g(mb, "covered"), g(mb, "uncovered")))
    # Ladder: the biggest increment over the floor and the rung it sits on.
    rung_of = {a: k for k, _, arms in LADDER for a in arms}
    climb = [r for r in rows if r["primary"] and rung_of.get(r["arm"], "").startswith("L") and r["arm"] != "native-bare"]
    if climb:
        top = max(climb, key=lambda r: r["acc"][0])
        top_rung = rung_of[top["arm"]]
        above = [r for r in climb if rung_of[r["arm"]] > top_rung]
        best_above = max(above, key=lambda r: r["acc"][0]) if above else None
        tail = ""
        if best_above:
            tail = "; the best rung above it, %s, adds %s." % (best_above["arm"], pts(best_above["acc"][0] - floor["acc"][0]))
        S["ladder"] = ("Over the bare agent's %d%%, the largest lift is %s points, from %s on %s, at %s per 100 questions%s"
                       % (pct(floor["acc"][0]), pts(top["acc"][0] - floor["acc"][0]), top["arm"], top["modelLabel"],
                          top["cost"]["label"], tail if tail else "."))
    return S


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    res = sys.argv[1]
    logs = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(res))
    out = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "index.html")
    build(res, logs, out)
