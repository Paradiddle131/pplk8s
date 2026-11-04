#!/usr/bin/env python3
"""Build the "every answer visible" report page from results.json and the per-run logs.

    python3 build.py RESULTS_JSON [LOGS_DIR] [SETS_DIR]

RESULTS_JSON  docs/research/semantic-bet/results.json (or a snapshot of it): every summary number.
LOGS_DIR      the directory holding eval-*.jsonl and judge.jsonl; default: beside RESULTS_JSON,
              then /home/user/pplk8s/docs/research/semantic-bet.
SETS_DIR      the directory holding semantic_bet.yaml and semantic_bet_hard.yaml (questions and
              groups); default: LOGS_DIR/../../../services/semantic-agent/evals.

Writes index.html beside this script.  Standard library only.

Every number on the page comes from RESULTS_JSON, from the logs, or from a computation below that
is named on the page as this page's own (the per-column and paired-against-the-floor intervals).
The logs' runs are scored as the eval scores them on read, as far as this script can reproduce:
the blind judge's two verdicts (judge.jsonl) are applied to the turns they decided; the dated
re-wordings of `bet_eval.recode` are not reproduced, so a few runs can differ from the scored
tally; the page states that difference per setup.
"""
from __future__ import annotations

import glob
import hashlib
import html
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_LOGS = "/home/user/pplk8s/docs/research/semantic-bet"

# Facts the page states that results.json does not carry; each names its source.
FACTS = {
    "power": {"frozen": 10, "hard": 15},  # RULE.md § Comparing two arms; findings/2026-11-03-356-hard-set.md
    "trial": "Gemini's data agents ran on Google's free trial (billed $0.00)",  # BRIEF.md, cost hints
    "compile_query": "#349",  # README Q1/Q3: compile_query is advertised and fails in Google's backend
}

ARM_WHAT = {
    "native-bare": "Google's data agent over the tables only: no catalog link, no descriptions, no glossary, no verified queries. The floor.",
    "native-kc": "The data agent grounded by Knowledge Catalog's import of our dbt MetricFlow project.",
    "native-kc-max": "Knowledge Catalog's import plus BigQuery column descriptions and a glossary linked to the columns.",
    "native-kc-reach": "The Knowledge Catalog setup, given the same tables and legacy schema as the generated-context setup.",
    "native-context-bare": "The data agent with context we generate from the MetricFlow definitions, without verified queries.",
    "native-context": "The generated context plus verified queries (worked SQL examples the agent may reuse).",
    "native-governed": "The data agent over governed tables we build and keep, one per metric.",
    "native-shaped": "The data agent over views, table functions and verified queries shaped like the metrics.",
    "native-graph": "The data agent with a BigQuery graph and its measures beside the tables.",
    "native-mcp": "Our ADK agent on Google's managed Knowledge Catalog and BigQuery MCP servers.",
    "custom-toolbox": "Our ADK agent on MCP Toolbox tools generated over the table functions; it cannot go outside their shapes.",
    "custom-metricflow": "Our ADK agent on our own MetricFlow server: it answers only through defined metrics and declines the rest.",
    "custom-hybrid": "MetricFlow tools first, then a read-only SQL fallback for what no metric covers, saying so in the answer.",
    "custom-lightdash": "Our ADK agent with one tool over Lightdash's free metric API (36 of 56 metrics translated).",
    "cc-metricflow": "The same three MetricFlow tools called by a Claude Code subagent; another harness, shown for comparison only.",
    "baseline": "Plain text-to-SQL that reads the generated docs; the reference every rule comparison started from.",
}
ARM_NAME = {
    "native-bare": "Data agent, tables only",
    "native-kc": "Data agent + catalog import",
    "native-kc-max": "Data agent + import, descriptions, glossary",
    "native-kc-reach": "Data agent + import, equal reach",
    "native-context-bare": "Data agent + generated context",
    "native-context": "Data agent + context + verified queries",
    "native-governed": "Data agent on governed tables",
    "native-shaped": "Data agent on views and table functions",
    "native-graph": "Data agent with a graph",
    "native-mcp": "ADK on Google's MCP servers",
    "custom-toolbox": "ADK on generated Toolbox tools",
    "custom-metricflow": "ADK on MetricFlow",
    "custom-hybrid": "ADK on MetricFlow + SQL fallback",
    "custom-lightdash": "ADK on Lightdash",
    "cc-metricflow": "Claude Code on MetricFlow",
    "baseline": "Text-to-SQL baseline",
}
ARM_ORDER = list(ARM_NAME)
TIERS = [  # (tier key, heading, arms)
    ("floor", "The floor", ["native-bare"]),
    ("r1", "Rung 1 · managed agent, configuration only", ["native-kc", "native-kc-max", "native-kc-reach", "native-context-bare", "native-context"]),
    ("r2", "Rung 2 · managed agent over warehouse objects we keep", ["native-governed", "native-shaped", "native-graph"]),
    ("r3", "Rung 3 · our agent on managed or generated tools", ["native-mcp", "custom-toolbox"]),
    ("r4", "Rung 4 · our agent on our own semantic-layer server", ["custom-metricflow", "custom-hybrid", "custom-lightdash"]),
    ("ref", "References outside the rule", ["baseline", "cc-metricflow"]),
]
LADDER = [  # the cost ladder in plain words, cheapest first; arms read against native-bare
    ("Bare data agent", ["native-bare"]),
    ("Plus crude context: the catalog import", ["native-kc", "native-kc-max", "native-kc-reach"]),
    ("Plus context generated from MetricFlow", ["native-context-bare", "native-context"]),
    ("Plus warehouse objects", ["native-governed", "native-shaped", "native-graph"]),
    ("ADK on Google's MCP servers", ["native-mcp", "custom-toolbox"]),
    ("ADK on MetricFlow", ["custom-metricflow", "custom-lightdash"]),
    ("The hybrid", ["custom-hybrid"]),
]
BUCKETS = [  # each question sits in exactly one column
    ("plain", "Covered", "A defined metric answers it; no hidden rule, no legacy table, one turn."),
    ("trap", "Hidden-rule", "Covered, but the obvious SQL is wrong: a business rule the table does not show."),
    ("distractor", "Distractor", "Covered, and a legacy table in reach gives another number."),
    ("conversation", "Conversation", "Covered, asked as a follow-up in a multi-turn chat."),
    ("planted", "Planted", "Covered, with instruction-like text planted in the data. Safety, never deciding."),
    ("uncovered", "Uncovered", "No metric answers it; only SQL over the tables can."),
]
OUTCODE = {"right": 0, "declined": 1, "wrong": 2, "unclear": 3, "confident-wrong": 4}
MODEL_ORDER = ["nvidia", "claude-haiku", "claude-sonnet", "claude-opus", "claude-code (haiku)", "claude-code (fresh",
               "claude-code (sonnet)", "claude-code (opus)", "(MODEL_UNSPECIFIED)", "(LATEST_GA", "THINKING", "FAST"]


def model_rank(m: str) -> int:
    for i, k in enumerate(MODEL_ORDER):
        if k in m:
            return i
    return 99


def model_label(m: str) -> str:
    if m.startswith("nvidia/"):
        return "free model (Nemotron)"
    if m.startswith("claude-code"):
        return "Claude Code · " + m[m.index("(") + 1:-1]
    if m.startswith("claude-"):
        return "Claude " + m.split("-")[1].capitalize()
    if m.startswith("google-data-agent"):
        return "Gemini · " + m[m.index("(") + 1:-1].replace("MODEL_UNSPECIFIED", "default").replace("LATEST_GA_MODEL", "latest GA").replace("_", " ").lower()
    return m


def role(m: str) -> str:
    if m.endswith(":free"):
        return "decides"
    if m.startswith("claude-code"):
        return "other harness"
    if m.startswith("claude-"):
        return "check"
    return "Google's model"


# ---------------------------------------------------------------- the sets (questions, groups)

def parse_set(path: str) -> dict:
    lines = open(path, encoding="utf-8").read().split("\n")
    groups: dict[str, list[str]] = {}
    i = lines.index("groups:") + 1
    cur = None
    while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
        ln = lines[i]
        m = re.match(r"^  (\S+):\s*(.*)$", ln)
        if m:
            cur = m.group(1)
            rest = m.group(2).strip()
            groups[cur] = [g.strip() for g in rest.strip("[]").split(",") if g.strip()] if rest.startswith("[") else []
        else:
            m = re.match(r"^  - (\S+)$", ln)
            if m and cur:
                groups[cur].append(m.group(1))
        i += 1
    qs: dict[str, list[str]] = {}
    start = lines.index("questions:") + 1
    cur = None
    j = start
    while j < len(lines):
        ln = lines[j]
        m = re.match(r"^- id: (\S+)", ln)
        if m:
            cur = m.group(1)
            qs[cur] = []
            j += 1
            continue
        m = re.match(r"^(\s*)(?:- )?question: ?(.*)$", ln)
        if m and cur:
            ind = len(m.group(1)) + (2 if "- question" in ln else 0)
            val = m.group(2)
            parts = [] if val in (">-", "|-", ">", "|") else [val]
            k = j + 1
            while k < len(lines) and lines[k].strip() and (len(lines[k]) - len(lines[k].lstrip())) > ind \
                    and not re.match(r"^\s*(?:- )?\w+:( |$)", lines[k]):
                parts.append(lines[k].strip())
                k += 1
            text = " ".join(parts).strip()
            if len(text) > 1 and text[0] in "'\"" and text[-1] == text[0]:
                text = text[1:-1].replace("''", "'")
            qs[cur].append(text)
            j = k
            continue
        j += 1
    return {"groups": groups, "questions": qs}


def bucket(gs: list[str]) -> str:
    for b in ("uncovered", "conversation", "planted", "trap", "distractor"):
        if b in gs:
            return b
    return "plain"


# ---------------------------------------------------------------- scoring the logs as the eval does

def run_outcome(turns: list[str]) -> str:
    if "confident-wrong" in turns:
        return "confident-wrong"
    if all(t == "right" for t in turns):
        return "right"
    if "wrong" in turns:
        return "wrong"
    if "unclear" in turns:
        return "unclear"
    return "declined"


def two_verdicts(a, b):
    return "unclear" if a is None or a != b else a


def hedge_verdicts(a, b):
    if a is None or a != b or a == "right":
        return "unclear"
    return "wrong" if a == "declined" else a


def read_judge(path: str) -> dict:
    v: dict[tuple, list] = {}
    if not os.path.exists(path):
        return v
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        key = (r.get("set", "frozen"), r["arm"], r["model"], r["case"], r["run"], r["turn"], r["answer"])
        att = v.setdefault(key, [None, None])
        if 1 <= r["n"] <= 2:
            att[r["n"] - 1] = r["verdict"] or ""
    return v


def judged(entry: dict, setname: str, verdicts: dict) -> dict:
    turns = entry.get("turns") or []
    out = []
    for i, t in enumerate(turns):
        o = t["outcome"]
        if o in ("unclear", "confident-wrong"):
            h = hashlib.sha256(t["text"].encode()).hexdigest()[:16]
            att = verdicts.get((setname, entry["arm"], entry["model"], entry["case"], entry["run"], i, h))
            if att and None not in att:
                a, b = (x or None for x in att)
                o2 = two_verdicts(a, b) if o == "unclear" else hedge_verdicts(a, b)
                t = {**t, "outcome": o2, "judged": att, "coded": o}
        out.append(t)
    return {**entry, "turns": out, "outcome": run_outcome([t["outcome"] for t in out]) if out else entry["outcome"]}


# ---------------------------------------------------------------- statistics computed here

def bootstrap_mean(vals: list[float], n: int, seed: int) -> list[float]:
    if not vals:
        return [None, None, None]
    m = sum(vals) / len(vals)
    if len(vals) == 1:
        return [m, m, m]
    rng = random.Random(seed)
    k = len(vals)
    means = sorted(sum(vals[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return [m, means[int(0.025 * n)], means[int(0.975 * n) - 1]]


def trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def compact_calls(calls: list) -> list:
    out = []
    for c in (calls or [])[:10]:
        args = c.get("args")
        if isinstance(args, dict) and set(args) == {"sql"}:
            a = trunc(str(args["sql"]), 700)
        else:
            a = trunc(json.dumps(args, ensure_ascii=False), 300)
        out.append([c.get("tool", "?"), a])
    if calls and len(calls) > 10:
        out.append(["…", f"{len(calls) - 10} more calls in the log"])
    return out


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    results_path = sys.argv[1]
    logs = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(results_path))
    if not glob.glob(os.path.join(logs, "eval-*.jsonl")):
        logs = FALLBACK_LOGS
    sets_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.normpath(os.path.join(logs, "../../../services/semantic-agent/evals"))
    snap = json.load(open(results_path, encoding="utf-8"))
    sets = {"frozen": parse_set(os.path.join(sets_dir, "semantic_bet.yaml")),
            "hard": parse_set(os.path.join(sets_dir, "semantic_bet_hard.yaml"))}
    verdicts = read_judge(os.path.join(logs, "judge.jsonl"))

    raw = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(logs, "eval-*.jsonl"))):
        s = "hard" if os.path.basename(f).startswith("eval-hard-") else "frozen"
        for line in open(f, encoding="utf-8"):
            if line.strip():
                r = json.loads(line)
                raw[(s, r["arm"], r["model"])].append(r)

    # cases per set, ordered by column then by the order of the set file
    case_index = {}
    cases_out = {}
    for s, d in sets.items():
        ids = list(d["questions"]) or list(d["groups"])
        order = {b[0]: i for i, b in enumerate(BUCKETS)}
        ids.sort(key=lambda c: order[bucket(d["groups"].get(c, []))])
        case_index[s] = {c: i for i, c in enumerate(ids)}
        cases_out[s] = [{"id": c, "b": bucket(d["groups"].get(c, [])), "g": d["groups"].get(c, []),
                         "q": d["questions"].get(c, [])} for c in ids]

    # spend per (set, arm, model) from the pass names; probes and smoke passes are not attributed
    spend = defaultdict(float)
    unattributed = 0.0
    for name, v in snap.get("claude_spend_by_pass", {}).items():
        arm = next((a for a in sorted(ARM_NAME, key=len, reverse=True) if a in name), None)
        if arm is None or "probe" in name or "smoke" in name:
            unattributed += v["usd"]
            continue
        spend[("hard" if " hard " in f" {name} " else "frozen", arm, v["model"])] += v["usd"]

    runs_detail = []  # [set, caseIdx, run, at, outcome, model_calls, turns]
    rows = []
    warnings = []
    for a in snap["arms"]:
        s = a["set"]
        entries = sorted(raw.get((s, a["arm"], a["model"]), []), key=lambda r: r.get("at", ""))
        extra = max(0, len(entries) - a["runs"])
        entries = [judged(e, s, verdicts) for e in entries[: a["runs"]]]
        tally = Counter(e["outcome"] for e in entries)
        moved = sum(abs(tally.get(k, 0) - a["outcomes"].get(k, 0)) for k in OUTCODE) // 2
        if moved:
            warnings.append(f"{s} {a['arm']} {a['model']}: {moved} runs differ from results.json")
        per_case = defaultdict(list)
        units = []
        for e in entries:
            ci = case_index[s].get(e["case"])
            if ci is None:
                continue
            di = len(runs_detail)
            runs_detail.append([e.get("run"), e.get("at", ""), OUTCODE[e["outcome"]], e.get("model_calls"),
                                [[trunc(t.get("text", ""), 1100), OUTCODE.get(t["outcome"], 2),
                                  compact_calls(t.get("calls")), t.get("coded"), t.get("judged")] for t in e["turns"]]])
            units.append([ci, OUTCODE[e["outcome"]], di])
            per_case[ci].append(e["outcome"])
        # per-column share right and confident-wrong, mean over cases, bootstrap over cases
        cols = {}
        for bi, (b, _, _) in enumerate(BUCKETS):
            cis = [ci for ci in per_case if cases_out[s][ci]["b"] == b]
            rv = [sum(o == "right" for o in per_case[ci]) / len(per_case[ci]) for ci in cis]
            cv = [sum(o == "confident-wrong" for o in per_case[ci]) / len(per_case[ci]) for ci in cis]
            seed = int(hashlib.sha256(f"{s}{a['arm']}{a['model']}{b}".encode()).hexdigest()[:8], 16)
            cols[b] = {"acc": bootstrap_mean(rv, 2000, seed), "cw": bootstrap_mean(cv, 2000, seed + 1),
                       "cases": len(cis), "runs": sum(len(per_case[ci]) for ci in cis)}
        usd = spend.get((s, a["arm"], a["model"]))
        free = a["model"].endswith(":free") or a["model"].startswith("google-data-agent")
        rows.append({
            "set": s, "arm": a["arm"], "model": a["model"], "ml": model_label(a["model"]), "role": role(a["model"]),
            "name": ARM_NAME.get(a["arm"], a["arm"]), "what": ARM_WHAT.get(a["arm"], ""),
            "harness": a.get("harness"), "session": a.get("session"), "rung": a.get("rung"),
            "cases": a["cases"], "of": a["of_cases"], "runs": a["runs"], "acc": a["accuracy"],
            "cw": a["confident_wrong"], "outcomes": a["outcomes"], "groups": a["groups"],
            "pass_all": a.get("pass_all"), "calls": a.get("model_calls"),
            "usd": usd, "free": free, "sub": a["model"].startswith("claude-code"),
            "moved": moved, "extra": extra, "units": units, "pc": None, "cols": cols,
        })
        rows[-1]["_pc"] = per_case

    # paired against the floor (native-bare on the same set), per case on the cases both reached
    for s in sets:
        floor = next((r for r in rows if r["set"] == s and r["arm"] == "native-bare"), None)
        if not floor:
            continue
        fpc = floor["_pc"]
        for r in rows:
            if r["set"] != s:
                continue
            common = [ci for ci in r["_pc"] if ci in fpc]
            d_acc = [sum(o == "right" for o in r["_pc"][ci]) / len(r["_pc"][ci]) - sum(o == "right" for o in fpc[ci]) / len(fpc[ci]) for ci in common]
            d_cw = [sum(o == "confident-wrong" for o in r["_pc"][ci]) / len(r["_pc"][ci]) - sum(o == "confident-wrong" for o in fpc[ci]) / len(fpc[ci]) for ci in common]
            r["vsfloor"] = {"acc": bootstrap_mean(d_acc, 4000, 325), "cw": bootstrap_mean(d_cw, 4000, 326), "cases": len(common)}

    # paired per column against the managed best, for the map's takeaway (ties are ties)
    for s in sets:
        mb = snap["managed_best"].get(s)
        best = next((r for r in rows if r["set"] == s and mb and r["arm"] == mb[0] and r["model"] == mb[1]), None)
        for r in rows:
            r["_vsbest"] = r.get("_vsbest", {})
            if r["set"] != s or not best:
                continue
            for b, _, _ in BUCKETS:
                common = [ci for ci in r["_pc"] if ci in best["_pc"] and cases_out[s][ci]["b"] == b]
                d = [sum(o == "right" for o in r["_pc"][ci]) / len(r["_pc"][ci]) - sum(o == "right" for o in best["_pc"][ci]) / len(best["_pc"][ci]) for ci in common]
                r["cols"][b]["vsbest"] = bootstrap_mean(d, 2000, 327) if d else None

    for r in rows:
        r.pop("_pc", None)
        r.pop("_vsbest", None)

    tier_of = {arm: t for t, _, arms in TIERS for arm in arms}
    rows.sort(key=lambda r: ([t for t, _, _ in TIERS].index(tier_of.get(r["arm"], "ref")),
                             ARM_ORDER.index(r["arm"]) if r["arm"] in ARM_ORDER else 99, model_rank(r["model"])))
    for r in rows:
        r["tier"] = tier_of.get(r["arm"], "ref")

    data = {
        "written": snap.get("written"), "rule": snap.get("rule"),
        "managed_best": snap.get("managed_best"), "step_three": snap.get("step_three"),
        "step_two": snap.get("step_two"), "spend": snap.get("claude_spend_by_pass"),
        "unattributed": unattributed, "facts": FACTS,
        "tiers": [[t, h] for t, h, _ in TIERS], "ladder": LADDER, "buckets": BUCKETS,
        "outcodes": list(OUTCODE), "cases": cases_out, "rows": rows, "runs": runs_detail,
        "nlogged": len(runs_detail), "warnings": warnings,
    }
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    out = tpl.replace("/*__DATA__*/null", blob).replace("__WRITTEN__", html.escape(str(snap.get("written"))))
    with open(os.path.join(HERE, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"wrote index.html: {len(rows)} setups, {len(runs_detail)} runs, {len(out) / 1e6:.1f} MB")
    for w in warnings:
        print("  reconcile:", w)


if __name__ == "__main__":
    main()
