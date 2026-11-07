#!/usr/bin/env python3
"""Build the semantic-bet research memo from results.json and the per-run logs.

The question sets part (#390): `question_guide` gives the set profiles, the guide's three lists and its card's fixed fields at <!--QUESTIONS--> (in the Question sets part, before the appendix), followed by questions.html, the section's style and script; its data is window.REPORT.questionGuide.
Sections contract: every sections/<name>/section.html (one <section> with scoped <style> and <script>) is inserted in name order at <!--SECTIONS-->, the page's Setups part (after Figure 6's part, before the question sets and "Method, briefly"); a missing directory inserts nothing. The appendix of other question sets goes at <!--APPENDIX-->.
The page gives them window.REPORT (the data), window.reportReady(fn), window.reportTheme() plus a "report-theme" event on document, delegated data-setup / data-term tooltips and .focusable hover-to-focus over .mk[data-arm|data-key|data-fam], and stable tokens (--paper ... --code).

Usage: python3 build.py [--show SET] [--template FILE] [--section FILE ...] [--out FILE] RESULTS_JSON [LOG_DIR] [SETS_DIR]

RESULTS_JSON  docs/research/semantic-bet/results.json (or a snapshot of it): every summary number.
LOG_DIR       directory holding eval-*.jsonl and judge.jsonl; default: beside RESULTS_JSON, else
              /home/user/pplk8s/docs/research/semantic-bet. Gives one square per run, the paired
              intervals computed here, and one example answer per setup.
SETS_DIR      directory holding semantic_bet.yaml and semantic_bet_hard.yaml (question text and
              groups); default: LOG_DIR/../../../services/semantic-agent/evals.
--show SET    the version of its set family the page shows (RULE.md § Set versions): `hard` (v1, the
              default until the owner's go on #380) or `hard-v2`; the family's other version goes to
              the appendix, labelled, with its own numbers. Also BET_REPORT_SHOW.

Writes index.html beside this script, from template.html, with the vendored Observable Plot and d3
(vendor/, checked by sha256) inlined. Standard library only.
Every number on the page comes from RESULTS_JSON or from the logs; prose that cites a number is a
template filled here. Intervals computed here (paired against the floor, per question group, ties
in the winners band) are percentile bootstraps over questions, seeded.
"""
import glob
import hashlib
import json
import os
import random
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK_LOGS = "/home/user/pplk8s/docs/research/semantic-bet"
# Observable Plot and its d3, inlined at <!--VENDOR--> so the page stays one file; see vendor/README.md.
VENDOR = [("vendor/d3-7.9.0.min.js", "f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539"),
          ("vendor/plot-0.6.17.umd.min.js", "4358086467740777dd788d6b27a95cebdbaefdd50c730a3060117073bd7134cb")]

SET_LABEL = {"frozen": "Frozen set", "hard": "Hard set", "hard-v2": "Extended hard set"}
# Set families (RULE.md § Set versions): each family's versions, oldest first. The page shows one
# version per family (SHOWN, or --show); the others go to the appendix. A set in no family is shown.
FAMILIES = {"hard": ["hard", "hard-v2"]}
# v1 until the owner's go on #380's comparison; #381 flips it to hard-v2.
SHOWN = {"hard": "hard"}
# Each set's log prefix, longest first: eval-hard-v2-* is hard-v2's, eval-hard-* hard's, eval-* frozen's.
LOG_PREFIX = [("eval-hard-v2-", "hard-v2"), ("eval-hard-", "hard"), ("eval-", "frozen")]
SET_FILE = {"frozen": "semantic_bet.yaml", "hard": "semantic_bet_hard.yaml", "hard-v2": "semantic_bet_hard_v2.yaml"}
GROUPS = [("covered", "Covered"), ("trap", "Hidden-rule"), ("uncovered", "Uncovered"), ("conversation", "Conversation")]
GROUPS_ALL = [("covered", "Covered"), ("trap", "Hidden-rule"), ("uncovered", "Uncovered"),
              ("conversation", "Conversation"), ("distractor", "Distractor"), ("planted", "Planted")]
GROUP_HELP = {
    "covered": "A metric of the semantic layer answers it.",
    "trap": "Covered, but the obvious SQL gives another number: a business rule the table does not show.",
    "uncovered": "No metric answers it; only SQL over the tables can.",
    "conversation": "A follow-up or an ambiguous term inside a multi-turn chat.",
    "distractor": "Covered, with a legacy table in reach that gives another number.",
    "planted": "Covered, with instruction-like text planted in the data.",
}
# Plate columns: each question in exactly one.
BUCKETS = [("plain", "Covered", "A metric answers it; no hidden rule, no legacy table, one turn."),
           ("trap", "Hidden-rule", "Covered, but the obvious SQL is wrong."),
           ("other", "Other covered", "Covered, asked as a follow-up, beside a legacy table, or with planted text."),
           ("uncovered", "Uncovered", "No metric answers it; only SQL over the tables can.")]

DESC = {
    "native-bare": "Google's data agent over the tables alone: no descriptions, catalog, glossary or examples.",
    "native-kc": "Google's data agent grounded by Knowledge Catalog's import of our dbt metrics.",
    "native-kc-max": "The catalog agent plus BigQuery column descriptions and a glossary linked to the columns.",
    "native-kc-reach": "The catalog agent given the same tables and legacy schema as the context setups.",
    "native-context-bare": "Google's data agent with written context we generate from MetricFlow.",
    "native-context": "The generated-context agent plus verified example queries.",
    "native-context-python": "The generated-context agent with verified queries, allowed to run Python on its query results.",
    "native-governed": "Google's data agent over governed tables we build from the metrics.",
    "native-shaped": "Google's data agent over views, table functions and verified queries.",
    "native-graph": "Google's data agent with a property graph and its measures beside the tables.",
    "native-mcp": "Our ADK agent calling Google's Knowledge Catalog and BigQuery MCP servers.",
    "custom-toolbox": "Our ADK agent on generated MCP Toolbox tools over table functions.",
    "custom-metricflow": "Our ADK agent on MetricFlow tools, told to answer only through the metrics.",
    "custom-metricflow-compute": "Our ADK agent on MetricFlow tools, allowed sums, differences and ratios of the metric results it fetched, as Google's agents compute in their SQL.",
    "custom-lightdash": "Our ADK agent with one tool on Lightdash's free metric query API.",
    "custom-hybrid": "MetricFlow tools first, then a read-only SQL fallback that says so.",
    "cc-metricflow": "The same MetricFlow tools called from Claude Code; another harness, shown for comparison only.",
    "cc-metricflow-compute": "The MetricFlow tools with arithmetic over their results, called from headless Claude Code; another harness, shown for comparison only.",
    "cc-native-mcp": "Google's BigQuery and Knowledge Catalog MCP tools called from headless Claude Code, behind the same cost guard; another harness, shown for comparison only.",
    "baseline": "Plain text-to-SQL that reads the generated docs.",
}
FAMILY = {
    "native-bare": "da", "native-kc": "da", "native-kc-max": "da", "native-kc-reach": "da",
    "native-context-bare": "da", "native-context": "da", "native-context-python": "da", "native-governed": "da",
    "native-shaped": "da", "native-graph": "da",
    "native-mcp": "gt", "custom-toolbox": "gt",
    "custom-metricflow": "mf", "custom-lightdash": "mf", "custom-hybrid": "mf", "cc-metricflow": "mf", "cc-native-mcp": "gt",
    "custom-metricflow-compute": "mf", "cc-metricflow-compute": "mf",
    "baseline": "ref",
}
FAMILY_LABEL = {"da": "Google's managed data agent", "gt": "Our agent on Google's tools",
                "mf": "Our agent on a semantic-layer server", "ref": "Text-to-SQL baseline", "other": "Another setup"}
UNDESCRIBED = "Not yet described."
# The setup "MetricFlow on the free model" reads (owner, 2026-11-06, #400: "yes"): the MetricFlow
# setup allowed arithmetic over its metric results once its free-model runs cover the set, else the first.
HEADLINE_MF = ("custom-metricflow-compute", "custom-metricflow")
COMPARISON_ONLY = {"cc-metricflow", "cc-native-mcp", "cc-metricflow-compute"}  # another harness: shown, never deciding
HARNESS = {"adk-openrouter": "ADK runner, model through OpenRouter",
           "adk-anthropic-api": "ADK runner, model through the Anthropic API",
           "claude-code-subagent": "Claude Code subagent (a different harness)",
           "claude-code-headless": "Claude Code, run headless: one fresh session a run, only the setup's tools, no shell, file or web tool",
           "google-data-agent": "Google's data agent, Google's harness"}
# The cost ladder in plain words, cheapest first.
LADDER = [
    ("ref", "Reference: plain text-to-SQL", ["baseline"]),
    ("L1", "Bare data agent, tables only (the floor)", ["native-bare"]),
    ("L2", "Plus catalog context: import, descriptions, glossary", ["native-kc", "native-kc-max", "native-kc-reach"]),
    ("L3", "Plus context generated from MetricFlow", ["native-context-bare", "native-context", "native-context-python"]),
    ("L4", "Plus warehouse objects: governed tables, table functions, graph", ["native-governed", "native-shaped", "native-graph"]),
    ("L5", "Our ADK agent on Google's MCP servers or generated tools", ["native-mcp", "custom-toolbox"]),
    ("L6", "Our ADK agent on a semantic-layer server", ["custom-metricflow", "custom-metricflow-compute", "custom-lightdash"]),
    ("L7", "The hybrid: MetricFlow first, SQL fallback", ["custom-hybrid"]),
    ("L8", "A data agent running the imported metrics itself: not measurable yet, the tool fails in Google's backend", []),
    ("cc", "Another harness: Claude Code on the same tools", ["cc-metricflow", "cc-metricflow-compute", "cc-native-mcp"]),
]
PILLAR_EXCLUDE = {"baseline", "cc-metricflow", "cc-native-mcp", "cc-metricflow-compute"}  # references outside the decision
SET_ORDER = ["frozen", "hard", "hard-v2"]
# Glossary terms: one short sentence each, the glossary and every term tooltip read these.
TERMS = [
    ("setup", "Setup", "One way of answering: an agent, the tools and context it is given, and the tables in its reach."),
    ("covered", "Covered", "A question a metric of the semantic layer answers."),
    ("hidden-rule", "Hidden-rule", "A covered question whose obvious SQL gives another number, because a business rule is not visible in the table."),
    ("uncovered", "Uncovered", "A question no metric answers, though SQL over the tables can."),
    ("conversation", "Conversation", "A follow-up or an ambiguous term inside a multi-turn chat."),
    ("confident-wrong", "Confident-wrong", "A wrong number stated with no hedge: the failure a business user feels. A lower rate counts only when accuracy ties."),
    ("floor", "The floor", "Google's data agent over the tables alone, with no context; every gain is read against it."),
    ("over-the-floor", "Over the floor", "A setup's share right minus the floor's, paired by question, in points."),
    ("managed-best", "Managed best", "The most accurate of Google's managed setups, the bar each of ours is paired against."),
    ("decides", "Decides", "Our setups run on a free model, which decides; Google's agents run on Gemini only."),
    ("check", "Check", "Claude Haiku, Sonnet and Opus repeat our setups, as a check on whether a gap is the model's."),
    ("pending", "Pending", "A setup that has run on Claude only, the check; it enters headlines and the winners once its deciding run exists."),
    ("partial", "Partial", "Rests on fewer questions than the set, or on fewer than three runs per question, so its interval is wider."),
    ("declined", "Declined", "The setup gave no number: it said it could not answer, or asked a question back."),
    ("unclear", "Unclear", "Neither the scoring code nor the blind judge could settle whether the answer was right."),
    ("interval", "95% interval", "A percentile bootstrap over questions: the range the mean would likely fall in on another draw of questions like these."),
    ("exact", "Exact bound", "When every run of every question is right, or none is, the bootstrap has no spread; the page then gives the exact two-sided 95% (Clopper-Pearson) bound over the questions instead."),
    ("frozen", "Frozen set", "The first question set, fixed before any setup was scored; its uncovered questions are medians, times between events, peaks, and ratios of two measures."),
    ("hard", "Hard set", "A second, harder question set, fixed before any setup ran on it: hard on business language (jargon, fiscal and relative periods, implicit definitions, ambiguity), and its uncovered questions are mostly ratios and differences of two measures. It detects only larger gaps."),
    ("hard-v2", "Extended hard set", "The hard set's questions plus more that are hard to write in SQL, where the obvious query gives another number; questions answered by arithmetic over a few metric results form their own group, composable."),
    # Question groups beyond the four headline ones, and the unit plate's catch-all column (#395)
    ("groups", "Groups", "What a question asks of a setup: whether a metric answers it, arithmetic over metrics, or only SQL, and whether it hides a rule or comes in a chat. A question sits in one group or two."),
    ("composable", "Composable", "No single metric answers it, but arithmetic over a few metric results does, such as a ratio or a difference of two."),
    ("distractor", "Distractor", "A covered question with an older, replaced table in reach that gives another number."),
    ("planted", "Planted", "A covered question whose data holds text written like an instruction to the agent, which it must ignore."),
    ("other-covered", "Other covered", "Covered questions asked as a follow-up, beside an older replaced table, or with planted text."),
    # What makes a hard-set question hard (a question can be several)
    ("jargon", "Jargon", "The question uses a business term, such as AOV or churn, instead of the metric's name."),
    ("period", "Period", "The period is relative or fiscal (last month, last quarter, the week before) and must be worked out from a date."),
    ("multi-metric", "Several metrics", "The answer needs more than one metric, or a metric of a metric."),
    ("segment", "Segment", "The question compares or ranks segments, such as channels, countries or customer groups."),
    ("implicit", "Implicit definition", "The question leaves a definition unsaid that the business has fixed, such as which orders count."),
    ("ambiguous-followup", "Ambiguous follow-up", "A follow-up in a chat, or a term with more than one meaning that the agent should ask about."),
    ("multi-step", "Multi-step", "The answer needs one result before the next can be asked for."),
    ("hard-to-interpret", "Hard to interpret", "What makes a question hard to read right before any number is fetched: business words, periods, segments, several metrics or steps, unsaid definitions, ambiguity."),
    ("sql-hard", "Hard in SQL", "The obvious SQL gives another number, for one of the reasons below."),
    # Why the obvious SQL goes wrong (the hard-in-SQL rubric)
    ("obvious-sql", "Obvious SQL", "The query most people would write first. On some questions it gives another number than the right one."),
    ("fan-out-join", "Fan-out join", "A join repeats rows, so a sum over the joined table counts some values twice."),
    ("distinct-across-join", "Distinct across a join", "A count must stay distinct across a join that repeats rows."),
    ("ratio-of-sums", "Ratio of sums", "The rate is a sum divided by a sum, not the average of each row's ratio."),
    ("window", "Window", "The answer needs a running or ranked value over ordered rows."),
    ("median-percentile", "Median or percentile", "The answer is a middle or a percentile value, which no plain sum or average gives."),
    ("sessions-gaps-islands", "Sessions and gaps", "Events must be grouped into runs separated by gaps in time."),
    ("cohort-retention", "Cohort retention", "Customers are grouped by when they started and followed over later periods."),
    ("anti-join", "Anti-join", "The question asks for what has no match, such as sign-ups that never ordered."),
    ("date-spine", "Date spine", "Days with no rows must still count, as zeros, so the days need generating."),
    ("fiscal-timezone", "Fiscal or time-zone boundary", "A period starts on a fiscal date or in a local time zone, not on UTC calendar days."),
    # Who answers: the setup families and the model roles
    ("family-da", "Google's managed data agent", "Google's own agent in BigQuery, on Gemini; we only change what it is given to read."),
    ("family-gt", "Our agent on Google's tools", "Our own agent (built with Google's Agent Development Kit, or Claude Code for comparison) calling Google's MCP servers or tools generated over the tables."),
    ("family-mf", "Our agent on a semantic-layer server", "Our own agent (ADK, or Claude Code for comparison) asking a semantic layer, MetricFlow or Lightdash, for metrics instead of writing SQL."),
    ("family-ref", "Text-to-SQL baseline", "A plain agent that reads the table docs and writes SQL; the reference the others are read against."),
    ("claude-code", "Claude Code", "Anthropic's agent harness, run headless with only the setup's tools; shown for comparison, never deciding."),
]
# Each glossary term's type, so the glossary reads as groups, not one long list (owner, 2026-11-06); in this order.
TERM_TYPES = ["Question sets", "Question groups", "What makes a question hard", "Why the obvious SQL goes wrong",
              "Setups and models", "Measures and statistics"]
TERM_TYPE = {
    "frozen": 0, "hard": 0, "hard-v2": 0,
    "covered": 1, "hidden-rule": 1, "uncovered": 1, "conversation": 1, "composable": 1, "distractor": 1,
    "planted": 1, "other-covered": 1, "groups": 1,
    "jargon": 2, "period": 2, "multi-metric": 2, "segment": 2, "implicit": 2, "ambiguous-followup": 2,
    "multi-step": 2, "sql-hard": 2, "hard-to-interpret": 2,
    "fan-out-join": 3, "distinct-across-join": 3, "ratio-of-sums": 3, "window": 3, "median-percentile": 3,
    "obvious-sql": 3, "sessions-gaps-islands": 3, "cohort-retention": 3, "anti-join": 3, "date-spine": 3, "fiscal-timezone": 3,
    "setup": 4, "floor": 4, "managed-best": 4, "decides": 4, "check": 4, "pending": 4, "family-da": 4,
    "family-gt": 4, "family-mf": 4, "family-ref": 4, "claude-code": 4,
    "confident-wrong": 5, "declined": 5, "unclear": 5, "over-the-floor": 5, "partial": 5, "interval": 5, "exact": 5,
}
# Each key a page shows a term for, mapped to its TERMS key where the data names it otherwise (#395).
TERM_ALIAS = {"trap": "hidden-rule", "plain": "covered", "other": "other-covered", "cc": "claude-code"}


def term_key(key):
    """The TERMS key for a group, bucket, kind, rubric kind or role key as the data spells it."""
    return TERM_ALIAS.get(key, key.replace("_", "-"))


# A question's fields that are process, never shown to a reader (#393): whether it was retired, and in which version it was added.
READER_HIDDEN = {"retired", "new"}
# What a set in the appendix tests, in a reader's words (what it holds, never its history: #393).
APPENDIX_ABOUT = {
    "hard-v2": "The hard set's questions plus fifteen that are hard to write in SQL (joins that multiply rows, "
               "ratios of sums, windows, medians, date spines); questions answered by arithmetic over two metrics "
               "form their own group, composable.",
}
# What each set's uncovered questions ask, for the "Uncovered questions" pillar; a set not listed shows none.
UNCOVERED_KIND = {
    "frozen": "Its uncovered questions: medians, times between events, peaks, ratios of two measures.",
    "hard": "Its uncovered questions: mostly ratios and differences of two measures.",
    "hard-v2": "Its uncovered questions need row-level SQL (medians, rankings, first orders, anti-joins, date spines, time zones); its composable ones are arithmetic over metric results.",
}
FEW_QUESTIONS = 20  # a pillar figure resting on fewer questions than this reads only large gaps
FREE = "nvidia/nemotron-3.5-super-vl:free"
MIN_CASES_TO_PLOT = 5
OUTCODE = {"right": "0", "declined": "1", "wrong": "2", "unclear": "3", "confident-wrong": "4"}
NBOOT = 2000


def model_info(model):
    if model == FREE:
        return "Nemotron free", "decides"
    if model.endswith(":free"):  # another free OpenRouter model: the free lane decides
        return model.split("/")[-1].replace(":free", "") + " free", "decides"
    m = re.match(r"claude-(haiku|sonnet|opus)-", model)
    if m:
        return m.group(1).capitalize(), "check"
    m = re.match(r"claude-code-strict \((.+)\)", model)
    if m:  # the strict headless runner (#387): one fresh session a run, only the setup's MCP tools
        return "Claude Code " + m.group(1).capitalize(), "cc"
    m = re.match(r"claude-code \((.+)\)", model)
    if m:
        name = m.group(1)
        if name.startswith("subject-"):  # the Bash-and-Read-only bet-subject agent type, fresh per case
            return "Claude Code " + name[len("subject-"):].capitalize() + ", Bash and Read only", "cc"
        base = name.replace("fresh-", "").capitalize()
        return "Claude Code " + base + (", fresh sessions" if name.startswith("fresh-") else ""), "cc"
    m = re.match(r"google-data-agent \((.+)\)", model)
    if m:
        names = {"MODEL_UNSPECIFIED": "default", "LATEST_GA_MODEL": "latest GA", "THINKING": "thinking", "FAST": "fast"}
        return "Gemini " + ", ".join(names.get(p.strip(), p.strip().lower()) for p in m.group(1).split(",")), "gemini"
    return model, "other"


# ---------------------------------------------------------------- question sets

def parse_set(path):
    """Groups per case and question text per case from a set file (no YAML library)."""
    lines = open(path, encoding="utf-8").read().split("\n")
    groups, cur = {}, None
    i = lines.index("groups:") + 1
    while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
        m = re.match(r"^  (\S+):\s*(.*)$", lines[i])
        if m:
            cur = m.group(1)
            rest = m.group(2).strip()
            groups[cur] = [g.strip() for g in rest.strip("[]").split(",") if g.strip()] if rest.startswith("[") else []
        else:
            m = re.match(r"^  - (\S+)$", lines[i])
            if m and cur:
                groups[cur].append(m.group(1))
        i += 1
    qs, cur = {}, None
    j = lines.index("questions:") + 1
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


def bucket(gs):
    # hard-v2's composable cases are uncovered ones in RULE.md's sense (no single metric answers them).
    if "uncovered" in gs or "composable" in gs:
        return "uncovered"
    if "trap" in gs:
        return "trap"
    if any(g in gs for g in ("conversation", "planted", "distractor")):
        return "other"
    return "plain"


# ---------------------------------------------------------------- scoring the logs as the eval does

def run_outcome(turns):
    if "confident-wrong" in turns:
        return "confident-wrong"
    if all(t == "right" for t in turns):
        return "right"
    if "wrong" in turns:
        return "wrong"
    if "unclear" in turns:
        return "unclear"
    return "declined"


def read_judge(path):
    v = {}
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


def judged_outcome(entry, setname, verdicts):
    """The run's outcome with the blind judge's two verdicts applied to the turns they decided."""
    turns = entry.get("turns") or []
    outs = []
    for i, t in enumerate(turns):
        o = t.get("outcome")
        if o in ("unclear", "confident-wrong") and t.get("text"):
            h = hashlib.sha256(t["text"].encode()).hexdigest()[:16]
            att = verdicts.get((setname, entry["arm"], entry["model"], entry["case"], entry["run"], i, h))
            if att and None not in att:
                a, b = (x or None for x in att)
                if o == "unclear":
                    o = "unclear" if a is None or a != b else a
                else:
                    o = "unclear" if (a is None or a != b or a == "right") else ("wrong" if a == "declined" else a)
        outs.append(o)
    return run_outcome(outs) if outs else entry.get("outcome")


def strip_md(text):
    return re.sub(r"\s+", " ", re.sub(r"\*\*(.+?)\*\*", r"\1", text)).strip()


# ---------------------------------------------------------------- statistics computed here

def boot(vals, seed, n=NBOOT):
    if not vals:
        return None
    m = sum(vals) / len(vals)
    if len(vals) == 1:
        return [m, m, m]
    rng = random.Random(seed)
    k = len(vals)
    means = sorted(sum(vals[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    return [m, means[int(0.025 * n)], means[int(0.975 * n) - 1]]


def share(lst, what):
    return sum(o == what for o in lst) / len(lst)


def seed_of(*parts):
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16)


def paired(pc_a, pc_b, cases, what, seed):
    """Mean over the cases both reached of share(a) - share(b), with a bootstrap interval."""
    common = [c for c in cases if c in pc_a and c in pc_b]
    d = [share(pc_a[c], what) - share(pc_b[c], what) for c in common]
    r = boot(d, seed)
    return (r + [len(common)]) if r else None


def exact(iv, n):
    """The two-sided 95% Clopper-Pearson interval over n questions, when a bootstrap interval has
    collapsed because every question's share is 0 or every one is 1; None otherwise."""
    if not iv or not n or iv[1] != iv[2] or iv[0] not in (0, 1):
        return None
    b = 0.025 ** (1.0 / n)
    return [b, 1.0] if iv[0] == 1 else [0.0, 1.0 - b]


def pct(x):
    return round(100 * x)


def fmt_iv(v):
    return "%d%% [%d, %d]" % (pct(v[0]), pct(v[1]), pct(v[2]))


def pts(x):
    v = round(100 * x)
    return ("+" + str(v)) if v > 0 else ("−" + str(-v)) if v < 0 else "0"


# ---------------------------------------------------------------- build


def set_label(st):
    return SET_LABEL.get(st, st.capitalize() + " set")


def decides(r):
    """A row on the model that decides for its setup: the free model for ours; a data agent
    runs only on Google's model, so its Gemini rows are its deciding rows."""
    return r["role"] == "decides" or r["role"] == "gemini"


def pick_order(r):
    return (0 if r["role"] == "decides" else 0 if r["managedBest"] else
            1 if r["model"].endswith("(MODEL_UNSPECIFIED)") else
            2 if "haiku" in r["model"] and r["role"] == "check" else
            3 if "sonnet" in r["model"] else 4 if "opus" in r["model"] else 5 if r["role"] == "gemini" else 6,
            -r["cases"])


def load_scored(path):
    """scored-runs.jsonl (bet_eval.write_scored_runs) by (set, arm, model), as load_logs gives."""
    raw = defaultdict(list)
    for line in open(path, encoding="utf-8"):
        if line.strip():
            r = json.loads(line)
            raw[(r["set"], r.get("arm"), r.get("model"))].append(r)
    return raw


def load_logs(log_dir):
    raw = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(log_dir, "eval-*.jsonl"))):
        name = os.path.basename(path)
        st = next(s for p, s in LOG_PREFIX if name.startswith(p))
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            raw[(r.get("set") or st, r.get("arm"), r.get("model"))].append(r)
    return raw


def family_of(st):
    return next((f for f, versions in FAMILIES.items() if st in versions), None)


def shown_sets(every, show):
    """The sets the page shows (one version per family: `show`'s, else SHOWN's) and the others, each
    with its reader-facing label; why a version is not shown is process, kept out of the page (#393)."""
    chosen = {**SHOWN, **show}
    present, appendix = [], []
    for st in every:
        fam = family_of(st)
        if fam is None or chosen.get(fam) == st:
            present.append(st)
            continue
        appendix.append((st, set_label(st)))
    return present, appendix


def appendix_html(R, appendix):
    """The appendix: each set the page does not show, its setups' two numbers and group accuracies
    as results.json has them, so a superseded or not yet adopted version is never lost."""
    if not appendix:
        return ""
    pc = lambda v: "–" if v is None else "%d%%" % round(100 * v)
    out = ['<section class="apx" id="other-set-versions" aria-labelledby="apx-h">',
           "<style>.apx table { border-collapse: collapse; font-family: var(--label); font-size: 13.5px; width: 100%; }"
           " .apx th, .apx td { text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }"
           " .apx th { color: var(--ink-3); font-weight: 500; } .apx td.n { font-variant-numeric: tabular-nums; white-space: nowrap; }"
           " .apx td:first-child { white-space: nowrap; } .apx .apx-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; } .apx h3 { margin: 18px 0 6px; }</style>",
           '<h2 id="apx-h">Appendix: more question sets</h2>',
           '<p class="col">More question sets, with each setup\'s numbers from the same runs; the figures draw the frozen and hard sets only.</p>']
    glabel = dict(GROUPS_ALL)
    for st, label in appendix:
        rows = [a for a in strict_view(R.get("arms", [])) if a["set"] == st]
        groups = [g for g in [k for k, _ in GROUPS_ALL] + sorted({g for a in rows for g in a.get("groups", {})}) if any(g in a.get("groups", {}) for a in rows)]
        groups = list(dict.fromkeys(groups))
        if APPENDIX_ABOUT.get(st):
            out.append('<p class="col">%s</p>' % html_escape(APPENDIX_ABOUT[st]))
        out.append('<h3>%s</h3><div class="apx-scroll"><table><thead><tr><th scope="col">Setup</th><th scope="col">Model</th>'
                   '<th scope="col">Questions</th><th scope="col">Accuracy</th><th scope="col">Confident-wrong</th>%s</tr></thead><tbody>'
                   % (html_escape(label), "".join('<th scope="col">%s</th>' % html_escape(glabel.get(g, g.capitalize())) for g in groups)))
        for a in sorted(rows, key=lambda a: (a["arm"], a["model"])):
            cells = "".join('<td class="n">%s</td>' % (pc(a["groups"][g][0]) if g in a.get("groups", {}) else "–") for g in groups)
            out.append('<tr><td>%s</td><td>%s</td><td class="n">%d of %d</td><td class="n">%s</td><td class="n">%s</td>%s</tr>'
                       % (html_escape(a["arm"]), html_escape(model_info(a["model"])[0]), a["cases"], a.get("of_cases") or a["cases"],
                          pc(a["accuracy"][0]), pc(a["confident_wrong"][0]), cells))
        out.append("</tbody></table></div>")
    out.append("</section>")
    return "\n".join(out)


# ---------------------------------------------------------------- the question sets part (#390)

# What each set holds, in a reader's words (never its history: #393); {extra} is the count of questions the
# extended hard set adds to the hard set's.
SET_ABOUT = {
    "frozen": "Everyday questions a shop owner asks about orders, revenue, marketing, service and hiring. "
              "Most are answered by one metric, the rest only by SQL over the tables; some hide a business rule, "
              "follow up in a chat, put an older table in reach or plant text in the data.",
    "hard": "Questions in a business user's own words: jargon, relative and fiscal periods, several metrics at once, "
            "segments, unsaid definitions and follow-ups. Its uncovered questions are mostly ratios and differences "
            "of two measures.",
    "hard-v2": "The hard set's questions plus {extra} that are hard to write in SQL, where the obvious query gives "
               "another number. Questions that arithmetic over a few metric results answers form their own group.",
}
# The three lists of the guide: a title (a glossary term) and where its categories come from.
QS_LISTS = [("groups", "Groups"), ("hard-to-interpret", "Hard to interpret"), ("sql-hard", "Hard in SQL")]
QS_GROUP_ORDER = ["covered", "trap", "composable", "uncovered", "conversation", "distractor", "planted"]
QS_KIND_ORDER = ["jargon", "period", "ambiguous_followup", "implicit", "segment", "multi_metric", "multi_step"]
QS_RUBRIC_ORDER = ["fan_out_join", "distinct_across_join", "ratio_of_sums", "window", "median_percentile",
                   "sessions_gaps_islands", "cohort_retention", "anti_join", "date_spine", "fiscal_timezone"]
# A question's id as a short name: the set prefixes go, business acronyms and proper names are spelled out.
NAME_PREFIX = ("hard_", "hv2_", "bet_")
NAME_WORD = {"followup": "follow-up", "aov": "AOV", "cpa": "CPA", "cpl": "CPL", "mqls": "MQLs", "roas": "ROAS", "gmv": "GMV", "q3": "Q3",
             "wow": "week on week", "mtd": "month to date", "ytd": "year to date", "vs": "vs",
             "germany": "Germany", "turkey": "Turkey", "turkish": "Turkish", "dutch": "Dutch",
             "amsterdam": "Amsterdam", "august": "August", "september": "September", "october": "October"}


def question_name(qid):
    for p in NAME_PREFIX:
        if qid.startswith(p):
            qid = qid[len(p):]
            break
    words = [NAME_WORD.get(w, w) for w in qid.split("_")]
    text = " ".join(words)
    return text[:1].upper() + text[1:]


def question_guide(qsets, sets, order):
    """The question sets part: one record per scored question across the sets, the guide's categories (each
    with its questions in example order), and the static markup (set profiles, the three lists, the card's
    fixed fields). Retired questions are not in `qsets` (#394), so they are absent here too."""
    sts = [s for s in order if s in qsets]
    q = {}
    for st in sts:
        spec = qsets[st]
        for item in spec["questions"]:
            rec = q.setdefault(item["id"], {
                "name": question_name(item["id"]), "turns": item.get("turns") or [],
                "expected": item.get("expected") or [], "sets": [], "groups": {}, "kinds": [], "rubric": [],
                "naive": False, "runs": None, "_i": len(q)})
            rec["sets"].append(st)
            rec["groups"][st] = list(spec["groups"].get(item["id"]) or item.get("groups") or [])
            rec["kinds"] += [k for k in item.get("kinds") or [] if k != "sql_hard" and k not in rec["kinds"]]
            rec["rubric"] += [k for k in item.get("rubric") or [] if k not in rec["rubric"]]
            rec["naive"] = rec["naive"] or bool(item.get("naive"))
            if rec["runs"] is None and st in sets and any(c["id"] == item["id"] for c in sets[st]["cases"]):
                rec["runs"] = st
    # How a question split the setups: each setup's first row in the plate's order, its right share.
    for rec_id, rec in q.items():
        st = rec["runs"]
        rec["_split"], rec["_cw"] = -1.0, 0
        if not st:
            continue
        ci = next(i for i, c in enumerate(sets[st]["cases"]) if c["id"] == rec_id)
        units = "".join(r["units"][ci * 3: ci * 3 + 3] for r in sets[st]["rows"] if r.get("primary"))
        ran = [u for u in units if u != "."]
        if ran:
            p = ran.count("0") / len(ran)
            rec["_split"], rec["_cw"] = min(p, 1 - p), ran.count("4")
    all_groups = {g for rec in q.values() for gs in rec["groups"].values() for g in gs}
    cats = []
    for li, keys, has in (
            (0, [g for g in QS_GROUP_ORDER if g in all_groups] + sorted(all_groups - set(QS_GROUP_ORDER)),
             lambda rec, k: any(k in gs for gs in rec["groups"].values())),
            (1, QS_KIND_ORDER + sorted({k for r in q.values() for k in r["kinds"]} - set(QS_KIND_ORDER)),
             lambda rec, k: k in rec["kinds"]),
            (2, QS_RUBRIC_ORDER + sorted({k for r in q.values() for k in r["rubric"]} - set(QS_RUBRIC_ORDER)),
             lambda rec, k: k in rec["rubric"])):
        for k in keys:
            ids = [i for i, rec in q.items() if has(rec, k)]
            if not ids:
                continue
            tags = lambda i: len({g for gs in q[i]["groups"].values() for g in gs}) + len(q[i]["kinds"]) + len(q[i]["rubric"])
            # Example order: a question the figures have runs on first, then the plainest (fewest tags), then the
            # one that splits the setups most, then the most confident-wrong runs, then the sets' own order.
            ids.sort(key=lambda i: (q[i]["runs"] is None, tags(i), -q[i]["_split"], -q[i]["_cw"], q[i]["_i"]))
            key = term_key(k)
            cats.append({"key": key, "list": li, "label": next((l for t, l, _ in TERMS if t == key), k), "ids": ids})
    for rec in q.values():
        for k in ("_i", "_split", "_cw"):
            rec.pop(k)
    guide = {"lists": [{"key": k, "label": l} for k, l in QS_LISTS], "cats": cats, "q": q,
             "setLabel": {st: set_label(st) for st in sts}}
    return guide, questions_html(guide, qsets, sts, set(sets))


def questions_html(guide, qsets, sts, drawn):
    e = html_escape
    term = lambda key, text=None: '<span class="term" data-term="%s" tabindex="0">%s</span>' % (
        e(key), e(text if text is not None else next(l for t, l, _ in TERMS if t == key)))
    out = ['<section class="qs" id="question-guide" aria-labelledby="qs-h">',
           '<h2 id="qs-h">The questions</h2>',
           '<p class="qs-lede">Every setup answers the same questions about one test shop, in sets. '
           'Each set below says what it holds; the guide under it shows each kind of question by example, '
           'with the number a right answer must carry and how each setup did on it.</p>',
           '<div class="qs-sets">']
    gorder = QS_GROUP_ORDER + sorted({g for st in sts for gs in qsets[st]["groups"].values() for g in gs} - set(QS_GROUP_ORDER))
    for st in sts:
        groups = qsets[st]["groups"]
        n = len(qsets[st]["questions"])
        extra = len([i for i in groups if not any(i in qsets[o]["groups"] for o in sts if o != st)])
        mix = [(g, sum(1 for gs in groups.values() if g in gs)) for g in gorder]
        mix = [(g, c) for g, c in mix if c]
        where = ('<p class="qs-where">Drawn in every figure</p>' if st in drawn else
                 '<p class="qs-where">Not drawn in the figures; <a href="#other-set-versions">its setups\' totals are in the appendix</a></p>')
        out.append('<article class="qs-set" id="qs-%s" aria-labelledby="qs-%s-h">' % (e(st), e(st)))
        out.append('<h3 id="qs-%s-h">%s</h3>' % (e(st), term(term_key(st), set_label(st)) if term_key(st) in TERM_TYPE else e(set_label(st))))
        out.append('<p class="qs-about">%s</p>' % e(SET_ABOUT.get(st, "").format(extra=extra)))
        out.append('<p class="qs-n"><b>%d</b> questions</p>' % n)
        out.append('<dl class="qs-mix" aria-label="Questions per group in the %s">' % e(set_label(st).lower()))
        top = max((c for _, c in mix), default=1)
        for g, c in mix:
            out.append('<dt>%s</dt><dd><span class="bar" aria-hidden="true"><i style="width:%.1f%%"></i></span><span class="c">%d</span></dd>'
                       % (term(term_key(g)), 100.0 * c / top, c))
        out.append('</dl><p class="qs-mixnote">A question can sit in two groups.</p>')
        out.append(where + '</article>')
    out.append('</div>')
    out.append('<h3 class="qs-gh" id="qs-guide-h">Questions by kind</h3>')
    out.append('<p class="qs-sub">Pick a kind of question to see a real one of that kind; '
               'Previous and Next, or the arrow keys, step through the others.</p>')
    out.append('<div class="qs-guide">')
    out.append('<nav class="qs-nav" id="qs-nav" aria-labelledby="qs-guide-h">')
    for li, (lk, ll) in enumerate(QS_LISTS):
        out.append('<div class="qs-list"><h4 id="qs-l%d">%s</h4><ul aria-labelledby="qs-l%d">' % (li, term(lk, ll), li))
        for c in guide["cats"]:
            if c["list"] == li:
                out.append('<li><button type="button" class="qs-cat" data-cat="%s" aria-pressed="false" tabindex="-1">'
                           '<span class="l">%s</span><span class="c">%d</span></button></li>' % (e(c["key"]), e(c["label"]), len(c["ids"])))
        out.append('</ul></div>')
    out.append('</nav>')
    out.append('<div class="qs-panel" id="qs-panel" aria-labelledby="qs-cat-h">')
    out.append('<div class="qs-head"><h4 id="qs-cat-h" tabindex="-1"></h4><p class="qs-def" id="qs-def"></p></div>')
    out.append('<div class="qs-step" id="qs-step">'
               '<button type="button" class="qs-btn" data-step="-1" aria-label="Previous example">'
               '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5L4 6l3.5 3.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>Previous</button>'
               '<span class="qs-pos" id="qs-pos" aria-live="polite"></span>'
               '<button type="button" class="qs-btn" data-step="1" aria-label="Next example">Next'
               '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5L8 6 4.5 9.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg></button>')
    # One "See all N" per category opens the full list of its questions. That browser is not built yet (#397):
    # the buttons stay hidden until it lands, and each dispatches CustomEvent("qs:see-all", {detail: {category}}).
    out.append('<span class="qs-seeall-set">')
    for c in guide["cats"]:
        out.append('<button type="button" class="qs-seeall" data-category="%s" hidden>See all %d</button>' % (e(c["key"]), len(c["ids"])))
    out.append('</span></div>')
    fields = [("asked", "Asked"), ("groups", term("groups", "Groups")), ("hard", "What makes it hard"),
              ("sql", term("obvious-sql", "Obvious SQL")), ("runs", "How each setup did")]
    out.append('<article class="qs-card" id="qs-card" aria-labelledby="qs-name">'
               '<div class="qs-title" data-field="title"><h5 class="qs-name" id="qs-name"></h5><p class="qs-in"></p></div><dl class="qs-dl">')
    for k, lab in fields:
        out.append('<dt>%s</dt><dd data-field="%s"></dd>' % (lab, k))
    out.append('</dl></article></div></div></section>')
    return "\n".join(out)


def html_escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


STRICT_WHOLE = ("claude-code-strict (haiku)", "claude-code-strict (sonnet)")


def strict_view(arms):
    """The Claude Code rows the page shows (#387; owner, 2026-11-06: replace the old rows only when the new
    numbers are ready). A setup's strict rows (`claude-code-strict (...)`) show on a set once its Haiku and
    Sonnet rows are whole there at k = 3; from then the setup's subagent rows (batched, fresh, shell tools)
    leave that set's page. Until then the strict rows stay off the page and the old rows stand. Every row
    stays in results.json."""
    def whole(a):
        of = a.get("of_cases") or a["cases"]
        return a["cases"] >= of and a["runs"] >= 3 * of
    ready = {(a["set"], a["arm"]) for a in arms if a["model"] == STRICT_WHOLE[0] and whole(a)}
    ready &= {(a["set"], a["arm"]) for a in arms if a["model"] == STRICT_WHOLE[1] and whole(a)}
    out = []
    for a in arms:
        if a["model"].startswith("claude-code-strict") and (a["set"], a["arm"]) not in ready:
            continue
        if a["model"].startswith("claude-code (") and (a["set"], a["arm"]) in ready:
            continue
        out.append(a)
    return out


def build(results_path, log_dir, sets_dir, out_path, show=None, extra_sections=(), template=None):
    R = json.load(open(results_path, encoding="utf-8"))
    arms_all = strict_view(R.get("arms", []))
    every = sorted({a["set"] for a in arms_all}, key=lambda s: (SET_ORDER.index(s) if s in SET_ORDER else 99, s))
    present, appendix = shown_sets(every, show or {})
    setfiles = SET_FILE
    qsets = {}
    for st in present:
        try:
            qsets[st] = parse_set(os.path.join(sets_dir, setfiles.get(st, "semantic_bet_%s.yaml" % st)))
        except (OSError, ValueError):
            qsets[st] = {"groups": {}, "questions": {}}
    # The runs as bet_eval scores them now (#382): retired cases, redacted runs and the judge's
    # verdicts already applied, every turn scored by the current rule, so the page shows only the
    # current data. Without that file (an older results.json), the logs are read and judged here.
    scored = os.path.join(log_dir, "scored-runs.jsonl")
    fresh = os.path.exists(scored)
    verdicts = {} if fresh else read_judge(os.path.join(log_dir, "judge.jsonl"))
    raw = load_scored(scored) if fresh else load_logs(log_dir)
    # Each set's cases and groups as scored (the overlay's retirements and labels), from results.json.
    for st, spec in (R.get("sets") or {}).items():
        if st in qsets:
            keep = set(spec.get("cases") or [])
            qsets[st]["questions"] = {c: t for c, t in qsets[st]["questions"].items() if c in keep}
            qsets[st]["groups"] = {c: g for c, g in (spec.get("groups") or {}).items() if c in keep}
    step2 = {(x.get("set"), x.get("arm"), x.get("model")): x for x in R.get("step_two", [])}
    rank = {"confident-wrong": 0, "declined": 1, "wrong": 2, "unclear": 3, "right": 4}
    known = {a for _, _, arms in LADDER for a in arms}
    ladder = [{"key": k, "label": l, "arms": list(a)} for k, l, a in LADDER]
    new_arms = sorted({a["arm"] for a in arms_all} - known)
    if new_arms:
        ladder.append({"key": "new", "label": "Not yet placed on the ladder", "arms": new_arms})

    sets = {}
    for st in present:
        q = qsets[st]
        seen = [e.get("case") for (s2, _, _), es in raw.items() if s2 == st for e in es]
        ids = list(q["questions"]) or list(q["groups"]) or list(dict.fromkeys(c for c in seen if c))
        order_b = {b[0]: i for i, b in enumerate(BUCKETS)}
        ids.sort(key=lambda c: order_b[bucket(q["groups"].get(c, []))])
        cidx = {c: i for i, c in enumerate(ids)}
        cases = [{"id": c, "b": bucket(q["groups"].get(c, [])),
                  "q": " / ".join(q["questions"].get(c, []))[:240]} for c in ids]
        mbr = (R.get("managed_best") or {}).get(st) or [None, None, None]
        rows = []
        for a in arms_all:
            if a["set"] != st:
                continue
            label, role = model_info(a["model"])
            of = a.get("of_cases") or a.get("cases") or 0
            expected = of * 3
            # Shown only when a reader should read the interval as wider: fewer questions than the set, or
            # clearly fewer than three runs a question; a run or two missing is no news to a reader (#393).
            partial = None
            if a["cases"] < of:
                partial = "%d of %d questions" % (a["cases"], of)
            elif a["runs"] <= a["cases"]:
                partial = "one run per question"
            elif a["runs"] < 0.9 * expected:
                partial = "fewer runs per question"
            entries = sorted(raw.get((st, a["arm"], a["model"]), []), key=lambda e: e.get("at", ""))[: a["runs"]]
            pc = defaultdict(list)
            example = None
            for e in entries:
                oc = e.get("outcome") if fresh else judged_outcome(e, st, verdicts)
                if e.get("case") not in cidx or oc not in OUTCODE:
                    continue
                pc[e["case"]].append(oc)
                turns = e.get("turns") or []
                turn = next((t for t in turns if t.get("outcome") == e.get("outcome")), turns[-1] if turns else None)
                if turn and turn.get("text") and (example is None or rank[example["outcome"]] > rank[oc]):
                    text = strip_md(turn["text"])
                    if len(text) > 240:
                        text = text[:237].rsplit(" ", 1)[0] + "..."
                    tools = turn.get("tools") or sorted({c.get("tool") for c in (turn.get("calls") or []) if c.get("tool")})
                    example = {"case": e["case"], "outcome": oc, "text": text, "tools": tools}
            units = "".join("".join(OUTCODE[o] for o in pc.get(c, [])[:3]).ljust(3, ".") for c in ids)
            rows.append({
                "id": "%s|%s|%s" % (st, a["arm"], a["model"]), "key": "%s|%s" % (a["arm"], a["model"]), "set": st,
                "arm": a["arm"], "model": a["model"], "modelLabel": label, "role": role,
                "family": FAMILY.get(a["arm"], "other"), "desc": DESC.get(a["arm"], UNDESCRIBED),
                "harness": HARNESS.get(a.get("harness"), a.get("harness") or "not recorded"), "session": a.get("session"),
                "acc": a["accuracy"], "cw": a["confident_wrong"], "groups": a.get("groups") or {},
                "cases": a["cases"], "of": of, "runs": a["runs"], "expected": expected,
                "outcomes": a.get("outcomes") or {}, "partial": partial,
                "major": a["cases"] < of or a["runs"] < 0.9 * expected,
                "plotted": a["cases"] >= MIN_CASES_TO_PLOT, "example": example,
                "managedBest": a["arm"] == mbr[0] and a["model"] == mbr[1],
                "exact": {k: exact(a[f], a["cases"]) for k, f in (("acc", "accuracy"), ("cw", "confident_wrong")) if exact(a[f], a["cases"])},
                "step2": step2.get((st, a["arm"], a["model"])), "units": units, "_pc": pc,
            })
        for arm in {r["arm"] for r in rows}:
            mine = [r for r in rows if r["arm"] == arm and r["plotted"]]
            cand = sorted(mine, key=pick_order)
            if cand:
                cand[0]["primary"] = True
            dec = sorted([r for r in mine if decides(r)], key=pick_order)
            if dec:
                dec[0]["deciding"] = True
            for r in rows:
                if r["arm"] == arm:
                    r["status"] = ("comparison" if arm in COMPARISON_ONLY else "decided" if dec else "pending")
        for r in rows:
            r.setdefault("primary", False)
            r.setdefault("deciding", False)
        mb = next((r for r in rows if r["managedBest"]), None)
        if mb is None:  # no managed best recorded: the most accurate managed data agent
            da = [r for r in rows if r["family"] == "da" and r["deciding"]]
            mb = max(da, key=lambda r: r["acc"][0]) if da else None
            if mb:
                mb["managedBest"] = True
        floor = next((r for r in rows if r["arm"] == "native-bare" and r["deciding"]), None)
        mf = next((r for a in HEADLINE_MF for r in rows if r["arm"] == a and r["deciding"]
                   and (a == HEADLINE_MF[-1] or not r["partial"])), None)
        for r in rows:
            sd = seed_of(st, r["arm"], r["model"])
            r["vsFloor"] = None if (floor is None or r is floor) else {
                "acc": paired(r["_pc"], floor["_pc"], ids, "right", sd),
                "cw": paired(r["_pc"], floor["_pc"], ids, "confident-wrong", sd + 1)}
        gcount = {g: sum(1 for c in ids if g in q["groups"].get(c, [])) for g, _ in GROUPS_ALL}
        for g, _ in GROUPS_ALL:  # no set file: fall back on the largest group count a row reports
            if not gcount[g]:
                gcount[g] = max((r["groups"].get(g, [0, 0])[1] for r in rows), default=0)
        sets[st] = {"label": set_label(st), "rows": rows, "cases": cases, "nCases": len(ids) or max((r["of"] for r in rows), default=0),
                    "managedBest": mb["id"] if mb else None, "floor": floor["id"] if floor else None,
                    "mf": mf["id"] if mf else None, "groupCases": gcount,
                    "pillars": make_pillars(st, rows, ids, q["groups"], floor, mf),
                    "parts": make_parts(st, rows, mb, floor, mf)}
        for r in rows:
            r.pop("_pc", None)

    data = {"written": R.get("written"), "setOrder": present, "sets": sets, "ladder": ladder,
            "sentences": combine(sets, present),
            "groups": [{"key": k, "label": l} for k, l in GROUPS],
            "groupsAll": [{"key": k, "label": l, "help": GROUP_HELP[k]} for k, l in GROUPS_ALL],
            "buckets": [{"key": k, "label": l, "help": h} for k, l, h in BUCKETS],
            "familyLabel": FAMILY_LABEL, "desc": DESC, "undescribed": UNDESCRIBED,
            "terms": [{"key": k, "label": l, "text": t, "type": TERM_TYPES[TERM_TYPE[k]]} for k, l, t in TERMS],
            "termTypes": TERM_TYPES,
            "termAlias": TERM_ALIAS,
            # Every set, shown or not (#390), as its reader sees it (#393, #394): its scored questions and groups only;
            # retired questions, hashes, freeze dates and version lineage stay in RULE.md and results.json.
            "questionSets": {st: {"label": set_label(st), "shown": st in present, "appendix": st in {a for a, _ in appendix},
                                  "groups": {c: g for c, g in (spec.get("groups") or {}).items() if c in set(spec.get("cases") or [])},
                                  "questions": [{k: v for k, v in q.items() if k not in READER_HIDDEN}
                                                for q in spec.get("questions") or [] if q.get("id") in set(spec.get("cases") or [])]}
                             for st, spec in (R.get("sets") or {}).items()},
            "abstract": make_abstract(sets, present), "twin": make_twins(sets, present)}
    # The question sets part (#390): its data for the page's script, its markup at <!--QUESTIONS-->.
    data["questionGuide"], qs_html = question_guide(data["questionSets"], sets, [s for s in SET_ORDER if s in data["questionSets"]]
                                                    + sorted(s for s in data["questionSets"] if s not in SET_ORDER))
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    page = open(template or os.path.join(HERE, "template.html"), encoding="utf-8").read().replace("/*__DATA__*/null", payload)
    sections = []
    for path in sorted(glob.glob(os.path.join(HERE, "sections", "*", "section.html"))):
        sections.append(open(path, encoding="utf-8").read())
    for path in extra_sections:  # a design variant previewed beside the page's own sections (#390)
        sections.append(open(path, encoding="utf-8").read())
    # The appendix goes at <!--APPENDIX--> (the template's question-sets part); a template without one gets it after the sections.
    apx = appendix_html(R, appendix)
    if "<!--QUESTIONS-->" in page:  # the section's markup, then its own style and script (questions.html)
        page = page.replace("<!--QUESTIONS-->", qs_html + "\n" + open(os.path.join(HERE, "questions.html"), encoding="utf-8").read())
    if "<!--APPENDIX-->" in page:
        page = page.replace("<!--SECTIONS-->", "\n".join(sections)).replace("<!--APPENDIX-->", apx)
    else:
        page = page.replace("<!--SECTIONS-->", "\n".join(sections + [apx]))
    page = page.replace("<!--VENDOR-->", vendor_scripts())
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("wrote %s (%d bytes)" % (out_path, len(page.encode("utf-8"))))


def vendor_scripts():
    """The vendored libraries as inline scripts, each checked against its pinned sha256."""
    out = []
    for rel, want in VENDOR:
        raw = open(os.path.join(HERE, rel), "rb").read()
        got = hashlib.sha256(raw).hexdigest()
        if got != want:
            sys.exit("%s: sha256 %s, expected %s (see vendor/README.md)" % (rel, got, want))
        text = raw.decode("utf-8")
        if "</script" in text.lower():
            sys.exit("%s holds a closing script tag; it cannot be inlined" % rel)
        out.append("<script>\n%s\n</script>" % text.rstrip("\n"))
    return "\n".join(out)


def make_pillars(st, rows, ids, groups, floor, mf):
    """Three winners, computed: covered, uncovered, least often confidently wrong.
    Candidates: each setup's deciding row (free model for ours, Gemini for Google's agents),
    references excluded. A tie is a paired interval (candidate minus leader, over the questions
    both reached) that includes zero."""
    cand = [r for r in rows if r["deciding"] and r["arm"] not in PILLAR_EXCLUDE]
    out = []
    for key, title, what, high, why in (
            ("covered", "Covered questions", "right", True, "A defined metric answers these, so setups that read or call the metrics lead."),
            ("uncovered", "Uncovered questions", "right", True, "No metric answers these, so setups that write their own SQL lead."),
            (None, "Least often confidently wrong", "confident-wrong", False, "A wrong number stated without a hedge: the failure a business user feels.")):
        cs = [c for c in ids if key is None or key in groups.get(c, [])]
        stats = []
        for r in cand:
            vals = [share(r["_pc"][c], what) for c in cs if c in r["_pc"]]
            if not cs or len(vals) < max(3, len(cs) // 3):
                continue
            stats.append((r, boot(vals, seed_of(st, r["arm"], r["model"], key or "all", what)), len(vals)))
        if not stats:
            continue
        lead = (max if high else min)(stats, key=lambda t: (t[1][0], t[2]))
        tied = []
        for r, iv, n in stats:
            if r is lead[0]:
                continue
            d = paired(r["_pc"], lead[0]["_pc"], cs, what, seed_of(st, "tie", r["arm"], key or "all"))
            if d and d[1] <= 0 <= d[2]:
                tied.append({"id": r["id"], "arm": r["arm"], "model": r["modelLabel"], "v": iv[0]})
        tied.sort(key=lambda t: -t["v"] if high else t["v"])
        def mean_of(r):
            if not r:
                return None
            v = [share(r["_pc"][c], what) for c in cs if c in r["_pc"]]
            return sum(v) / len(v) if v else None
        if key == "uncovered" and mf is not None and mf is not lead[0]:
            contrast = ("MetricFlow on the free model", mean_of(mf))
        else:
            contrast = ("the bare agent with tables only", mean_of(floor))
        runs = sum(len(lead[0]["_pc"][c]) for c in cs if c in lead[0]["_pc"])
        out.append({"title": title, "group": key, "what": what, "n": len(cs), "why": why,
                    "kind": UNCOVERED_KIND.get(st) if key == "uncovered" else None,
                    "lead": {"id": lead[0]["id"], "arm": lead[0]["arm"], "model": lead[0]["modelLabel"],
                             "iv": lead[1], "partial": lead[0]["partial"], "q": lead[2], "runs": runs,
                             "exact": exact(lead[1], lead[2]), "few": lead[2] < FEW_QUESTIONS},
                    "tied": tied, "contrast": [contrast[0], contrast[1]] if contrast[1] is not None else None})
    return out


def make_parts(st, rows, mb, floor, mf):
    """Per-set facts the figure titles are made of."""
    def g(r, k):
        v = (r or {}).get("groups", {}).get(k)
        return pct(v[0]) if v else None
    P = {"label": set_label(st), "n": max((r["of"] for r in rows), default=0)}
    if mb:
        P["mb"] = {"name": "%s on %s" % (mb["arm"], mb["modelLabel"]), "acc": mb["acc"], "cw": mb["cw"], "ex": mb["exact"],
                   "unc": g(mb, "uncovered"), "cov": g(mb, "covered")}
    if mf:
        P["mf"] = {"acc": mf["acc"], "cw": mf["cw"], "ex": mf["exact"], "cov": g(mf, "covered"), "trap": g(mf, "trap"), "unc": g(mf, "uncovered")}
        if mf["step2"]:
            P["mf"]["vsBest"] = mf["step2"]["accuracy"]
            P["mf"]["vsBestCw"] = mf["step2"].get("confident_wrong")
        rel = []
        for k in ("covered", "trap", "uncovered"):
            da = [r for r in rows if r["family"] == "da" and r["deciding"] and k in r["groups"]]
            v = g(mf, k)
            if not da or v is None:
                rel.append(None)
                continue
            bv = g(max(da, key=lambda r: r["groups"][k][0]), k)
            rel.append("level with" if abs(v - bv) <= 5 else ("%d points above" % (v - bv) if v > bv else "%d points below" % (bv - v)))
        P["rel"] = rel
        checks = [r for r in rows if r["arm"] == mf["arm"] and r["role"] == "check" and "uncovered" in r["groups"]]
        if checks:
            P["mfCheckUnc"] = [min(g(r, "uncovered") for r in checks), max(g(r, "uncovered") for r in checks)]
    sl = [r for r in rows if r["family"] == "mf" and r["deciding"] and r["plotted"] and g(r, "covered") is not None and g(r, "uncovered") is not None]
    if sl:
        drops = [g(r, "covered") - g(r, "uncovered") for r in sl]
        P["drop"] = [min(drops), max(drops), len(sl)]
    rung_of = {a: k for k, _, arms in LADDER for a in arms}
    climb = [r for r in rows if r["deciding"] and rung_of.get(r["arm"], "").startswith("L") and r["vsFloor"] and r["vsFloor"]["acc"]]
    if climb and floor:
        top = max(climb, key=lambda r: r["vsFloor"]["acc"][0])
        P["ladder"] = {"floor": floor["acc"][0], "floorCw": floor["cw"][0], "arm": top["arm"], "model": top["modelLabel"],
                       "d": top["vsFloor"]["acc"], "cw": top["cw"][0],
                       "higher": any(rung_of[r["arm"]] > rung_of[top["arm"]] for r in climb)}
    return P


def make_abstract(sets, order):
    """A lead sentence over every set, then one parallel row per set."""
    rows, below, tie, above, less, more = [], [], [], [], [], []
    for s in order:
        P = sets[s]["parts"]
        if "mb" not in P or "mf" not in P:
            continue
        a = P["mf"].get("vsBest")
        c = P["mf"].get("vsBestCw")
        rows.append({"set": s, "label": P["label"], "n": P["n"], "mb": P["mb"]["name"], "mbArm": P["mb"]["name"].split(" on ")[0],
                     "mbAcc": P["mb"]["acc"], "mbCw": P["mb"]["cw"], "mfAcc": P["mf"]["acc"], "mfCw": P["mf"]["cw"], "d": a, "dCw": c,
                     "mbEx": P["mb"]["ex"], "mfEx": P["mf"]["ex"]})
        if a:
            (below if a[2] < 0 else above if a[1] > 0 else tie).append(P["label"].lower())
        if c:
            if c[2] < 0:
                less.append(P["label"].lower())
            elif c[1] > 0:
                more.append(P["label"].lower())
    def names(xs):
        return "both sets" if len(xs) == 2 and len(order) == 2 else " and the ".join(xs)
    parts = []
    if below:
        parts.append("on %s%s the best managed setup is right more often than our ADK agent on MetricFlow on the free model that decides" % ("" if names(below) == "both sets" else "the ", names(below)))
    if tie:
        parts.append("on the %s the two tie" % names(tie))
    if above:
        parts.append("on the %s MetricFlow is right more often" % names(above))
    lead = "; ".join(parts)
    lead = (lead[0].upper() + lead[1:] + ".") if lead else ""
    cw = []
    if less:
        cw.append("less often on the %s" % " and the ".join(less))
    if more:
        cw.append("more often on the %s" % " and the ".join(more))
    if cw:
        lead += " MetricFlow is confidently wrong " + " and ".join(cw) + "."
    return {"lead": lead, "rows": rows}


def make_twins(sets, order):
    """Per-set rows for the two-set figure titles."""
    T = {"map": [], "strip": []}
    for s in order:
        P = sets[s]["parts"]
        if P.get("rel") and None not in P["rel"]:
            T["map"].append({"set": s, "label": P["label"], "cells": P["rel"]})
        if "mf" in P and P["mf"]["unc"] is not None and "mb" in P:
            T["strip"].append({"set": s, "label": P["label"], "cov": P["mf"]["cov"], "trap": P["mf"]["trap"], "unc": P["mf"]["unc"], "mbUnc": P["mb"]["unc"]})
    rows = T["map"]
    if rows:
        lvl = all(r["cells"][0] == "level with" and r["cells"][1] == "level with" for r in rows)
        trap_lvl = all(r["cells"][1] == "level with" for r in rows)
        unc_below = all("below" in r["cells"][2] for r in rows)
        head = ("keeps level with the best managed agent on covered and hidden-rule questions" if lvl else
                "keeps level with the best managed agent on hidden-rule questions" if trap_lvl else
                "trails or ties the best managed agent on covered and hidden-rule questions")
        tail = (", and falls behind on uncovered ones, which no single metric answers, on every set." if unc_below else
                ", and on uncovered questions, which no single metric answers, it is not behind on every set.")
        T["mapLead"] = "On the free model, MetricFlow " + head + tail
    st = T["strip"]
    if st:
        gap = all(r["unc"] < r["cov"] - 15 for r in st)
        T["stripLead"] = ("On every set, MetricFlow on the free model answers far fewer uncovered questions than covered ones, while the managed best answers most of both." if gap and all((r["mbUnc"] or 0) >= 75 for r in st)
                          else "MetricFlow on the free model, covered against uncovered questions, beside the managed best.")
    chk = [sets[s]["parts"]["mfCheckUnc"] for s in order if "mfCheckUnc" in sets[s]["parts"]]
    T["stripNote"] = ("Claude, the check, answers %d to %d%% of uncovered ones." % (min(c[0] for c in chk), max(c[1] for c in chk))) if chk else ""
    return T


def combine(sets, order):
    """Figure titles over every set present, each set named."""
    S = {}
    parts = [sets[s]["parts"] for s in order]
    ab = []
    for P in parts:
        if "mb" in P and "mf" in P:
            t = "On the %s (%d questions), the best managed setup, %s, is right on %s of runs; our ADK agent on MetricFlow, on the free model that decides, is right on %s" % (
                P["label"].lower(), P["n"], P["mb"]["name"], fmt_iv(P["mb"]["acc"]), fmt_iv(P["mf"]["acc"]))
            if "vsBest" in P["mf"]:
                a = P["mf"]["vsBest"]
                t += ", %s points paired by question [%s, %s]" % (pts(a[0]), pts(a[1]), pts(a[2]))
            t += ", and confidently wrong on %d%% against %d%%." % (pct(P["mf"]["cw"][0]), pct(P["mb"]["cw"][0]))
            ab.append(t)
    S["abstract"] = " ".join(ab)
    m = []
    for i, P in enumerate(parts):
        rel = P.get("rel")
        if not rel or None in rel:
            continue
        if not m:
            m.append("On the free model, MetricFlow is %s the best managed agent on covered questions, %s it on hidden-rule ones and %s on uncovered ones, which no single metric answers (%s)" % (rel[0], rel[1], rel[2], P["label"].lower()))
        else:
            m.append("on the %s: %s, %s and %s" % (P["label"].lower(), rel[0], rel[1], rel[2]))
    S["map"] = "; ".join(m) + "." if m else "Share of runs right per question type, per setup."
    f = []
    for P in parts:
        if "mf" in P and "vsBest" in P["mf"]:
            a = P["mf"]["vsBest"]
            tie = a[1] <= 0 <= a[2]
            f.append("%s on the %s (%s)" % ("level with the managed best" if tie else "%d points %s the managed best" % (abs(round(100 * a[0])), "below" if a[0] < 0 else "above"),
                                           P["label"].lower(), "a tie within the interval" if tie else "the interval excludes a tie"))
    S["forest"] = ("Paired by question, MetricFlow on the free model is " + ", and ".join(f) + ".") if f else "Accuracy and confident-wrong per setup and model."
    sc = {}
    for s in order:
        P = sets[s]["parts"]
        if "mf" in P and "mb" in P:
            sc[s] = "MetricFlow on the free model is right on %d%% of runs and confidently wrong on %d%%; the managed best is right on %d%% and confidently wrong on %d%%." % (
                pct(P["mf"]["acc"][0]), pct(P["mf"]["cw"][0]), pct(P["mb"]["acc"][0]), pct(P["mb"]["cw"][0]))
    S["scatter"] = sc
    st = []
    for P in parts:
        if "mf" in P and P["mf"]["unc"] is not None and "mb" in P:
            st.append("%d%% of covered and %d%% of uncovered questions on the %s, where the managed best answers %d%%" % (
                P["mf"]["cov"], P["mf"]["unc"], P["label"].lower(), P["mb"]["unc"] or 0))
    chk = [P["mfCheckUnc"] for P in parts if "mfCheckUnc" in P]
    S["strip"] = ("MetricFlow on the free model answers " + "; and ".join(st) +
                  (" (Claude, the check, answers %d to %d%% of uncovered ones)" % (min(c[0] for c in chk), max(c[1] for c in chk)) if chk else "") + ".") if st else "Share of runs right per question group."
    sl = {}
    for s in order:
        P = sets[s]["parts"]
        if "drop" in P and "mb" in P and P["mb"]["unc"] is not None:
            d = P["drop"]
            sl[s] = "On the free model, %s loses %s points from covered to uncovered questions; the managed best changes by %s." % (
                "every semantic-layer setup" if d[2] > 1 else "MetricFlow", ("%d to %d" % (d[0], d[1])) if d[0] != d[1] else str(d[0]),
                pts((P["mb"]["unc"] - P["mb"]["cov"]) / 100))
    S["slope"] = sl
    ld = {}
    for s in order:
        L = sets[s]["parts"].get("ladder")
        if L:
            ld[s] = "Over the bare agent's %d%%, the largest lift is %s points [%s, %s], from %s on %s, which cuts confident-wrong from %d%% to %d%%%s." % (
                pct(L["floor"]), pts(L["d"][0]), pts(L["d"][1]), pts(L["d"][2]), L["arm"], L["model"], pct(L["floorCw"]), pct(L["cw"]),
                "; no setup further up the ladder adds more" if L["higher"] else "")
    S["ladder"] = ld
    return S


if __name__ == "__main__":
    args = sys.argv[1:]
    show = {}
    picked = os.environ.get("BET_REPORT_SHOW")
    if "--show" in args:
        i = args.index("--show")
        picked = args[i + 1]
        del args[i:i + 2]
    extra, out = [], os.path.join(HERE, "index.html")
    while "--section" in args:  # preview: --section <variant>/section.html --out <page>.html
        i = args.index("--section")
        extra.append(args[i + 1])
        del args[i:i + 2]
    template = None
    if "--template" in args:  # a design variant's copy of template.html (#396)
        i = args.index("--template")
        template = args[i + 1]
        del args[i:i + 2]
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        del args[i:i + 2]
    if picked:
        if family_of(picked) is None:
            sys.exit("--show %s: not a version of a set family (%s)" % (picked, FAMILIES))
        show = {family_of(picked): picked}
    if not args:
        sys.exit(__doc__)
    sys.argv = [sys.argv[0]] + args
    res = sys.argv[1]
    logs = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(res))
    if not glob.glob(os.path.join(logs, "eval-*.jsonl")):
        logs = FALLBACK_LOGS
    sets_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.normpath(os.path.join(logs, "../../../services/semantic-agent/evals"))
    build(res, logs, sets_dir, out, show, extra, template)
