"""Each setup's declared tools, and the check that a run called only those (#388).

A setup is an arm, or a Claude Code variant of one (RULE.md § Changes since freezing). Its declared
tools are the names its harness can call, read from the code that builds it:

- the ADK arms: the tools their `build_agent` passes (`sql_baseline.agent`, `toolset_metricflow`,
  `hybrid`, the probes' agents);
- `native-mcp`: the read-only filter `probes/328_mcp_agent.py` puts on Google's two MCP servers;
- the data agents: the steps the Conversational Analytics chat stream reports and
  `probes/354_data_agent.py` logs as calls, `generated_sql` and `matched_query` (the agent loop's
  other steps, schema lookups, charts, Python analysis, carry no figure and are counted by
  `probes/388_parity.py --sample`);
- the Claude Code variants: the same names as the arm they mirror, as the MCP server lists them.

`outside(arm, turns)` names every call a run made outside its setup's list; a call the harness
refused because no such tool exists (ADK's "no tool with that name is available") gained nothing
and is named by `refused` instead. A runner never scores a run with a call outside its list: it
writes the run to `faults.jsonl` beside the logs and leaves it for a later pass
(`bet_live.run_live`, `bet_eval.run_bet`). `python -m semantic_agent.bet_tools` checks every log
already written and exits 1 when a run in force (not redacted) called outside its list.
"""

from __future__ import annotations

import datetime
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

METRICFLOW = frozenset({"list_metrics", "describe_metric", "query_metrics"})
# probes/328_mcp_agent.py's BIGQUERY_TOOLS and CATALOG_TOOLS (tests/test_bet_tools.py checks).
GOOGLE_MCP = frozenset(
    {
        "list_dataset_ids",
        "list_table_ids",
        "get_dataset_info",
        "get_table_info",
        "execute_sql_readonly",
        "get_job",
        "get_query_results",
        "search_entries",
        "lookup_context",
        "lookup_entry",
        "lookup_entry_links",
        "list_entries",
        "get_glossary",
        "get_operation",
        "compile_query",
        "execute_query",
    }
)
# probes/330_tools.yaml's toolset `bet-shaped`.
TOOLBOX = frozenset(
    {
        "daily_sales",
        "net_sales_daily",
        "sales_by_country_daily",
        "orders_by_status",
        "returns_by_reason",
        "damaged_returns_daily",
        "channel_performance",
    }
)
DATA_AGENT = frozenset({"generated_sql", "matched_query"})
DATA_AGENT_ARMS = (
    "native-context",
    "native-governed",
    "native-kc",
    "native-shaped",
    "native-graph",
    "native-kc-max",
    "native-bare",
    "native-kc-reach",
    "native-context-bare",
)

DECLARED: dict[str, frozenset[str]] = {
    "baseline": frozenset({"execute_sql"}),
    "custom-metricflow": METRICFLOW,
    "custom-hybrid": METRICFLOW | {"execute_sql"},
    "custom-toolbox": TOOLBOX,
    "custom-lightdash": frozenset({"query_metrics"}),
    "native-mcp": GOOGLE_MCP,
    **{arm: DATA_AGENT for arm in DATA_AGENT_ARMS},
    # The Claude Code setups: the shell-tool subagents (#374, calls self-reported) and the two
    # variants the strict headless runner gives exactly these tools (#387).
    "cc-metricflow": METRICFLOW,
    "cc-native-mcp": GOOGLE_MCP,
}

# What a harness answers when a model calls a tool it does not have.
REFUSED = (
    "no tool with that name is available",
    "is not found in the tools_dict",
    "No such tool available",  # Claude Code's answer to a tool it was not given
)
FAULTS = "faults.jsonl"


def declared(arm: str) -> frozenset[str]:
    """The setup's tools; an arm with no entry is a programming error, never an empty list."""
    try:
        return DECLARED[arm]
    except KeyError:
        raise KeyError(f"bet_tools: no declared tools for setup {arm!r}") from None


def bare(name: str) -> str:
    """A tool's name without Claude Code's `mcp__<server>__` prefix."""
    return name.split("__", 2)[2] if name.startswith("mcp__") and name.count("__") >= 2 else name


def _calls(turns: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [c for t in turns for c in t.get("calls") or []]


def refused(call: Mapping[str, Any]) -> bool:
    return any(phrase in str(call.get("result", "")) for phrase in REFUSED)


def outside(arm: str, turns: Sequence[Mapping[str, Any]]) -> list[str]:
    """Every call the run made outside the setup's declared tools, refused attempts left out."""
    allowed = declared(arm)
    return [
        bare(str(c.get("tool")))
        for c in _calls(turns)
        if bare(str(c.get("tool"))) not in allowed and not refused(c)
    ]


def refused_attempts(arm: str, turns: Sequence[Mapping[str, Any]]) -> list[str]:
    allowed = declared(arm)
    return [
        bare(str(c.get("tool")))
        for c in _calls(turns)
        if bare(str(c.get("tool"))) not in allowed and refused(c)
    ]


def write_fault(row: Mapping[str, Any], calls: Sequence[str], directory: Path) -> None:
    """A run left unscored because it called outside its setup's tools."""
    at = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with (directory / FAULTS).open("a") as out:
        out.write(json.dumps({**row, "fault": "tools", "outside": list(calls), "at": at}) + "\n")


def check(directory: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Every runs log's census per (log, setup, model): runs in force, runs with calls recorded,
    calls outside the setup's list, refused attempts; and one line per run in force that called
    outside its list (the redacted ones are read through the overlay and do not count)."""
    from semantic_agent.bet_eval import RESEARCH, SETS, read_log

    directory = directory or RESEARCH
    rows: list[dict[str, Any]] = []
    faults: list[str] = []
    for path in sorted(directory.glob("eval-*.jsonl")):
        prefix = max((s.prefix for s in SETS.values() if path.name.startswith(s.prefix)), key=len)
        file_arm = None if path.name.endswith("local.jsonl") else path.stem.removeprefix(prefix)
        census: dict[tuple[str, str], dict[str, Any]] = {}
        for run in read_log(path):
            arm = run.get("arm") or file_arm
            entry = census.setdefault(
                (arm, run["model"]),
                {"log": path.name, "setup": arm, "model": run["model"], "runs": 0, "with_calls": 0}
                | {"outside": {}, "refused": {}},
            )
            if "turns" not in run:
                continue
            entry["runs"] += 1
            turns = run["turns"]
            if any("calls" in t for t in turns):
                entry["with_calls"] += 1
            for name in outside(arm, turns):
                entry["outside"][name] = entry["outside"].get(name, 0) + 1
                where = f"{arm} {run['model']} {run['case']} run {run['run']}"
                faults.append(f"{path.name}: {where}: {name}")
            for name in refused_attempts(arm, turns):
                entry["refused"][name] = entry["refused"].get(name, 0) + 1
        rows += census.values()
    return rows, faults


def main(argv: Sequence[str]) -> int:
    rows, faults = check(Path(argv[0]) if argv else None)
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    for line in faults:
        print(f"OUTSIDE: {line}")
    print(f"bet_tools: {len(faults)} runs in force called outside their setup's tools")
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
