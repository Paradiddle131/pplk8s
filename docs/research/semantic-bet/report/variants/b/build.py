#!/usr/bin/env python3
"""Build the semantic-bet console (variant B) from results.json.

Usage:
    python3 build.py results.json [--repo ROOT] [--out index.html]

Reads only `results.json` (first argument) for every score; optionally reads the
per-run logs (`docs/research/semantic-bet/eval-*.jsonl`) and the question sets
(`services/semantic-agent/evals/semantic_bet*.yaml`) under ROOT for example
answers and tool-use counts.  ROOT defaults to the repository that holds
results.json (results.json sits in docs/research/semantic-bet/).
Python 3 standard library only.  No number is written by hand into the page:
every figure is computed in the page's script from the embedded data.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
K = 3  # runs per case under RULE.md § Scoring a run

# Plain words, one sentence per setup ("What this setup is").
DESCRIBE = {
    "native-bare": "Google's data agent on the tables alone: no catalog link, descriptions, glossary or examples. The floor.",
    "native-kc": "Google's data agent grounded by Knowledge Catalog's import of our dbt metrics.",
    "native-kc-max": "The Knowledge Catalog agent plus column descriptions and a linked glossary: every free piece of context.",
    "native-kc-reach": "The Knowledge Catalog agent given the same tables and legacy schema as the generated-context agent.",
    "native-context-bare": "Google's data agent with context we generate from the MetricFlow project, no verified queries.",
    "native-context": "Google's data agent with our generated context plus verified example queries.",
    "native-governed": "Google's data agent over governed tables we generate and keep.",
    "native-shaped": "Google's data agent with views, table functions and verified queries we generate.",
    "native-graph": "Google's data agent with a property graph and its measures beside the tables.",
    "native-mcp": "Our ADK agent on Google's managed Knowledge Catalog and BigQuery MCP servers; it writes SQL.",
    "custom-toolbox": "Our ADK agent on MCP Toolbox tools generated over table functions; it can only ask those shapes.",
    "custom-metricflow": "Our ADK agent on our MetricFlow server: answers only through defined metrics, declines otherwise.",
    "custom-hybrid": "Our ADK agent on MetricFlow first, then read-only SQL for what no metric covers, saying so.",
    "custom-lightdash": "Our ADK agent with one tool over Lightdash's free metric query API.",
    "cc-metricflow": "The same MetricFlow tools called by a Claude Code subagent instead of ADK. Other harness; descriptive only.",
    "baseline": "Plain text-to-SQL that reads the generated docs. The reference, no semantic layer.",
}

# The cost ladder in the owner's words, cheapest to most custom.
LADDER = [
    {"key": "floor", "label": "Bare data agent, tables only", "arms": ["native-bare"]},
    {"key": "kc", "label": "Plus crude context: Knowledge Catalog's dbt import", "arms": ["native-kc", "native-kc-max", "native-kc-reach"]},
    {"key": "ctx", "label": "Plus context generated from MetricFlow", "arms": ["native-context-bare", "native-context"]},
    {"key": "wh", "label": "Plus warehouse objects: governed tables, table functions, graph", "arms": ["native-governed", "native-shaped", "native-graph"]},
    {"key": "mcp", "label": "Our ADK agent on Google's MCP servers or generated tools", "arms": ["native-mcp", "custom-toolbox"]},
    {"key": "mf", "label": "Our ADK agent on a semantic-layer server", "arms": ["custom-metricflow", "custom-lightdash", "cc-metricflow"]},
    {"key": "hy", "label": "The hybrid: MetricFlow first, SQL fallback", "arms": ["custom-hybrid"]},
    {"key": "future", "label": "If compile_query ships: a managed agent querying metrics", "arms": [],
     "note": "Not measurable yet: compile_query and execute_query are advertised by Knowledge Catalog and fail in Google's backend for any request (#349)."},
    {"key": "ref", "label": "Reference: text-to-SQL baseline", "arms": ["baseline"]},
]

RUNG_TEXT = {
    1: "Rung 1: managed agent, configuration only",
    2: "Rung 2: managed agent over warehouse objects we keep",
    3: "Rung 3: our agent on managed or generated tools",
    4: "Rung 4: our agent on our own semantic-layer server",
}

GROUPS = ["covered", "trap", "uncovered", "conversation", "distractor", "planted"]
GROUP_LABEL = {
    "covered": "Covered", "trap": "Hidden-rule", "uncovered": "Uncovered",
    "conversation": "Conversation", "distractor": "Distractor", "planted": "Planted",
}
GROUP_HELP = {
    "covered": "a defined metric answers it",
    "trap": "the obvious SQL is wrong because a business rule isn't visible in the table",
    "uncovered": "no metric answers it; only SQL can",
    "conversation": "multi-turn follow-ups and ambiguous terms",
    "distractor": "a legacy table in reach gives another number",
    "planted": "rows holding instruction-like text (safety, never deciding)",
}

# Sourced constants that results.json does not carry yet (kept here, cited).
POWER = {"frozen": 10, "hard": 15,
         "source": "findings/2026-11-03-356-hard-set.md: smallest accuracy difference detected four times in five at k = 3"}
FREE_TRIAL_UNTIL = "2026-12-31"

SQL_TOOLS = {"generated_sql", "execute_sql_readonly", "execute_query"}
BROWSE_TOOLS = {"get_table_info", "list_table_ids", "list_dataset_ids", "get_dataset_info",
                "get_routine_info_placeholder"}


def family(model):
    if model.startswith("google-data-agent"):
        return "gemini"
    if model.startswith("claude-code"):
        return "cc"
    if model.startswith("claude-"):
        return "claude"
    return "free"


def model_short(model):
    fam = family(model)
    if fam == "gemini":
        inner = model[model.find("(") + 1:model.rfind(")")]
        names = {"MODEL_UNSPECIFIED": "default", "LATEST_GA_MODEL": "latest GA",
                 "THINKING": "thinking", "FAST": "fast"}
        return "Gemini " + ", ".join(names.get(p.strip(), p.strip().lower()) for p in inner.split(","))
    if fam == "cc":
        inner = model[model.find("(") + 1:model.rfind(")")]
        return "Claude Code " + inner.replace("fresh-", "fresh ").capitalize()
    if fam == "claude":
        return "Claude " + model.split("-")[1].capitalize()
    base = model.split("/")[-1].replace(":free", "")
    return "Free " + base.split("-")[0].capitalize()


def kind(rung):
    return {1: "managed", 2: "managed", 3: "tools", 4: "semantic"}.get(rung, "reference")


def role(fam, rung):
    if rung is None:
        return "reference"
    if fam == "gemini":
        return "managed"
    if fam == "free":
        return "decides"
    if fam == "claude":
        return "check"
    return "descriptive"


def parse_spend(spend, arms):
    """Map each Claude pass to (set, arm, model) by its name; probes stay apart."""
    names = sorted(arms, key=len, reverse=True)
    out, loose = {}, []
    for name, v in spend.items():
        toks = [t.strip(",()") for t in name.split()]
        arm = next((a for a in names if a in toks), None)
        if name.startswith("probe") or "smoke" in toks or arm is None:
            loose.append({"pass": name, "model": v["model"], "usd": v["usd"]})
            continue
        st = "hard" if "hard" in toks else "frozen"
        key = (st, arm, v["model"])
        out.setdefault(key, {"usd": 0.0, "passes": []})
        out[key]["usd"] += v["usd"]
        out[key]["passes"].append(name)
    return out, loose


def read_questions(root):
    qs = {}
    for f in glob.glob(os.path.join(root, "services/semantic-agent/evals/semantic_bet*.yaml")):
        text = open(f, encoding="utf-8").read()
        for cid, body in re.findall(r"^- id: (\S+)\n((?:  .*\n|\s*\n)+)", text, re.M):
            m = re.search(r"^\s+(?:- )?(?:question|ask|text|user): (.+)$", body, re.M)
            if m:
                qs[cid] = m.group(1).strip().strip("'\"")
    return qs


def read_logs(root, wanted):
    """Per (set, arm, model): tool-use counts and two example answers."""
    logdir = os.path.join(root, "docs/research/semantic-bet")
    acc = {}
    for f in sorted(glob.glob(os.path.join(logdir, "eval*.jsonl"))):
        st = "hard" if os.path.basename(f).startswith("eval-hard") else "frozen"
        for line in open(f, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            key = (st, r.get("arm"), r.get("model"))
            if key not in wanted:
                continue
            a = acc.setdefault(key, {"logged": 0, "with_calls": 0, "semantic": 0, "sql": 0, "tools": {}, "runs": []})
            a["logged"] += 1
            names = [c.get("tool") for t in r.get("turns", []) for c in (t.get("calls") or [])]
            if names:
                a["with_calls"] += 1
            if any(n in SQL_TOOLS for n in names):
                a["sql"] += 1
            if any(n not in SQL_TOOLS and n not in BROWSE_TOOLS for n in names):
                a["semantic"] += 1
            for n in names:
                a["tools"][n] = a["tools"].get(n, 0) + 1
            a["runs"].append(r)
    return acc


def pick_examples(runs, groups_of, questions):
    def ex(r):
        t = r["turns"][0] if r.get("turns") else {"text": ""}
        call = next((c for tt in r.get("turns", []) for c in (tt.get("calls") or [])), None)
        snippet = None
        if call:
            args = call.get("args") or {}
            body = args.get("sql") or json.dumps(args, ensure_ascii=False)
            snippet = {"tool": call.get("tool"), "body": body[:420]}
        return {"case": r["case"], "question": questions.get(r["case"]), "run": r.get("run"),
                "groups": groups_of.get(r["case"], []), "outcome": r.get("outcome"),
                "turns": len(r.get("turns", [])), "text": (t.get("text") or "").strip()[:520],
                "call": snippet, "at": r.get("at")}
    out = []
    right = [r for r in runs if r.get("outcome") == "right"]
    pref = [r for r in right if "trap" in groups_of.get(r["case"], [])] or right
    if pref:
        out.append(ex(pref[0]))
    fails = {}
    for r in runs:
        if r.get("outcome") != "right":
            fails.setdefault(r.get("outcome"), []).append(r)
    if fails:
        order = sorted(fails, key=lambda o: (o != "confident-wrong", -len(fails[o])))
        top = order[0]
        pool = fails[top]
        unc = [r for r in pool if "uncovered" in groups_of.get(r["case"], [])]
        out.append(ex((unc or pool)[0]))
    return out


def read_groups(root):
    groups = {}
    for f in glob.glob(os.path.join(root, "services/semantic-agent/evals/semantic_bet*.yaml")):
        text = open(f, encoding="utf-8").read()
        m = re.search(r"^groups:\n((?:  .*\n)+)", text, re.M)
        if not m:
            continue
        cur = None
        for line in m.group(1).splitlines():
            if re.match(r"^  \S", line):
                cur = line.strip().rstrip(":")
                groups[cur] = []
            elif cur and line.strip().startswith("- "):
                groups[cur].append(line.strip()[2:])
    return groups


def build(results_path, root, out_path):
    d = json.load(open(results_path, encoding="utf-8"))
    arms_known = sorted({a["arm"] for a in d["arms"]})
    spend, loose = parse_spend(d.get("claude_spend_by_pass", {}), arms_known)
    wanted = {(a["set"], a["arm"], a["model"]) for a in d["arms"]}
    logs = read_logs(root, wanted) if root else {}
    questions = read_questions(root) if root else {}
    groups_of = read_groups(root) if root else {}
    step_two = {(s["set"], s["arm"], s["model"]): s for s in d.get("step_two", [])}

    rows, used_spend = [], set()
    for i, a in enumerate(d["arms"]):
        key = (a["set"], a["arm"], a["model"])
        fam = family(a["model"])
        sp = spend.get(key)
        if sp:
            used_spend.add(key)
        lg = logs.get(key)
        s2 = step_two.get(key)
        rows.append({
            "id": "r%d" % i, "set": a["set"], "arm": a["arm"], "model": a["model"],
            "model_short": model_short(a["model"]), "family": fam, "kind": kind(a["rung"]),
            "role": role(fam, a["rung"]), "rung": a["rung"], "harness": a.get("harness"),
            "session": a.get("session"), "cases": a["cases"], "of_cases": a["of_cases"],
            "runs": a["runs"], "runs_full": a["of_cases"] * K,
            "partial": a["cases"] < a["of_cases"] or a["runs"] < a["of_cases"] * K,
            "acc": a["accuracy"], "cw": a["confident_wrong"], "groups": a.get("groups", {}),
            "pass_all": a.get("pass_all"), "outcomes": a.get("outcomes", {}),
            "model_calls": a.get("model_calls"),
            "spend": {"usd": round(sp["usd"], 6), "passes": sp["passes"]} if sp else None,
            "vs_best": {"acc": s2["accuracy"], "cw": s2["confident_wrong"], "worth": s2["worth"],
                        "cases": s2["cases"], "runs": s2["runs"]} if s2 else None,
            "tools": ({"logged": lg["logged"], "with_calls": lg["with_calls"], "semantic": lg["semantic"],
                       "sql": lg["sql"], "names": lg["tools"]} if lg else None),
            "examples": pick_examples(lg["runs"], groups_of, questions) if lg else [],
        })
    orphan = [{"pass": p, "model": m, "set": s, "arm": a, "usd": round(v["usd"], 6)}
              for (s, a, m), v in spend.items() if (s, a, m) not in used_spend for p in v["passes"]]
    data = {
        "written": d.get("written"), "rule": d.get("rule"), "rows": rows,
        "managed_best": d.get("managed_best", {}), "step_three": d.get("step_three", {}),
        "ladder": LADDER, "rung_text": RUNG_TEXT, "describe": DESCRIBE,
        "groups": GROUPS, "group_label": GROUP_LABEL, "group_help": GROUP_HELP,
        "power": POWER, "free_trial_until": FREE_TRIAL_UNTIL, "k": K,
        "spend_loose": loose, "spend_orphan": orphan,
        "spend_total": round(sum(v["usd"] for v in d.get("claude_spend_by_pass", {}).values()), 6),
        "sets": {s: max(r["of_cases"] for r in rows if r["set"] == s) for s in sorted({r["set"] for r in rows})},
    }
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = tpl.replace("/*__DATA__*/null", blob)
    open(out_path, "w", encoding="utf-8").write(html)
    return len(rows), len(html)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("results")
    p.add_argument("--repo", help="repository root holding the logs and question sets")
    p.add_argument("--out", default=os.path.join(HERE, "index.html"))
    ns = p.parse_args()
    root = ns.repo
    if not root:
        guess = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(ns.results)), "..", "..", ".."))
        root = guess if os.path.isdir(os.path.join(guess, "docs/research/semantic-bet")) else None
    if not root:
        print("note: no --repo; example answers and tool-use counts are left out", file=sys.stderr)
    n, size = build(ns.results, root, ns.out)
    print("wrote %s: %d setup rows, %d bytes" % (ns.out, n, size))


if __name__ == "__main__":
    main()
