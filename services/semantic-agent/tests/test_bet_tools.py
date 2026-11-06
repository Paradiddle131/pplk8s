"""Each setup's declared tools against the code that builds it, and the check that a run called only
those (#388): offline, through scripted models and probes."""

import asyncio
import importlib.util
import json
from pathlib import Path

import yaml

from semantic_agent import bet_eval, bet_live, bet_tools, hybrid, tools
from semantic_agent.agent import build_agent as semantic_agent
from sql_baseline.agent import build_agent as baseline_agent
from tests.conftest import ScriptedLlm
from tests.test_bet_live import BET, DESCRIBED, EXPECTED, RIGHT

PROBES = Path(__file__).resolve().parents[3] / "docs/research/semantic-bet/probes"


def names(agent) -> set[str]:
    return {getattr(t, "name", None) or t.__name__ for t in agent.tools}


def probe(name: str):
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), PROBES / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_adk_arms_declare_exactly_the_tools_their_agents_are_built_with():
    model = ScriptedLlm(steps=[])
    assert names(baseline_agent(model)) == bet_tools.DECLARED["baseline"]
    assert names(semantic_agent(model)) == bet_tools.DECLARED["custom-metricflow"]
    assert names(hybrid.build_agent(model)) == bet_tools.DECLARED["custom-hybrid"]
    assert {t.__name__ for t in tools.TOOLS} == bet_tools.METRICFLOW


def test_the_probe_arms_declare_the_lists_their_probes_name():
    mcp = probe("328_mcp_agent.py")
    assert set(mcp.BIGQUERY_TOOLS) | set(mcp.CATALOG_TOOLS) == bet_tools.DECLARED["native-mcp"]
    toolsets = [
        d
        for d in yaml.safe_load_all((PROBES / "330_tools.yaml").read_text())
        if d.get("kind") == "toolset"
    ]
    assert set(toolsets[0]["tools"]) == bet_tools.DECLARED["custom-toolbox"]
    agents = probe("354_data_agent.py").AGENTS
    assert set(agents) == set(bet_tools.DATA_AGENT_ARMS)
    # The Claude Code variants mirror their arms tool for tool.
    assert bet_tools.DECLARED["cc-metricflow"] == bet_tools.DECLARED["custom-metricflow"]
    assert bet_tools.DECLARED["cc-native-mcp"] == bet_tools.DECLARED["native-mcp"]


def test_a_call_outside_the_list_is_named_and_a_refused_attempt_is_not():
    turns = [
        {"calls": [{"tool": "list_metrics"}, {"tool": "mcp__semantic__query_metrics"}]},
        {"calls": [{"tool": "Bash", "args": {"command": "cat x"}}]},
        {"calls": [{"tool": "get_routine", "result": "no tool with that name is available"}]},
    ]
    assert bet_tools.outside("cc-metricflow", turns) == ["Bash"]
    assert bet_tools.refused_attempts("cc-metricflow", turns) == ["get_routine"]
    assert bet_tools.outside("cc-metricflow", turns[:1]) == []


class StrayProbe:
    """Answers right, after a call outside native-mcp's tools."""

    async def __call__(self, questions):
        return [
            {"question": q, "calls": [{"tool": "Bash"}], "answer": RIGHT, "model_calls": 1}
            for q in questions
        ]


def test_the_live_runner_never_scores_a_run_outside_its_tools(tmp_path):
    log = tmp_path / "eval-native-mcp.jsonl"
    why = asyncio.run(
        bet_live.run_live(
            BET, EXPECTED, DESCRIBED, "native-mcp", StrayProbe(), "m", 1, log, say=lambda _: None
        )
    )
    assert why == "done"
    assert bet_eval.read_log(log) == []
    faults = [json.loads(line) for line in (tmp_path / bet_tools.FAULTS).read_text().splitlines()]
    assert [(f["case"], f["outside"]) for f in faults] == [
        ("revenue_one_day", ["Bash"]),
        ("revenue_then_define", ["Bash", "Bash"]),
    ]


def test_the_local_runner_logs_every_call_it_made(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "run", lambda query, catalog: {"rows": [{"revenue_eur": 868.65}]})
    model = ScriptedLlm(steps=[("list_metrics", {}), RIGHT])
    log = tmp_path / "eval.jsonl"
    bet = bet_eval.BetSet(BET.questions[:1], {"revenue_one_day": ["covered"]}, [])
    agents = {"custom-metricflow": semantic_agent(model)}
    asyncio.run(bet_eval.run_bet(bet, EXPECTED, agents, {}, "scripted", 1, log))
    (row,) = bet_eval.read_log(log)
    assert [c["tool"] for c in row["turns"][0]["calls"]] == ["list_metrics"]
    assert row["turns"][0]["calls"][0]["result"]


def test_the_check_reads_every_log_and_fails_only_runs_in_force(tmp_path):
    row = {
        "arm": "native-mcp",
        "model": "m",
        "run": 1,
        "case": "c",
        "at": "t",
        "turns": [{"text": "x", "outcome": "right", "calls": [{"tool": "Bash"}]}],
        "outcome": "right",
    }
    (tmp_path / "eval-native-mcp.jsonl").write_text(json.dumps(row) + "\n")
    census, faults = bet_tools.check(tmp_path)
    assert census[0]["outside"] == {"Bash": 1} and len(faults) == 1
    # Redacted through the overlay: no longer in force.
    redact = {"kind": "run", **{k: row[k] for k in ("arm", "model", "case", "run", "at")}}
    (tmp_path / bet_eval.OVERLAY).write_text(json.dumps(redact) + "\n")
    assert bet_tools.check(tmp_path)[1] == []


def test_the_compute_setup_differs_from_metricflow_only_in_allowing_arithmetic_over_results():
    """#400: custom-metricflow-compute is custom-metricflow's agent and tools, its instruction
    allowing a sum, difference, ratio or share of query_metrics results (as Google's agents do in
    SQL) and nothing else."""
    from semantic_agent.toolset_metricflow import INSTRUCTION, INSTRUCTION_COMPUTE, toolset_compute

    model = ScriptedLlm(steps=[])
    agent = semantic_agent(model, toolset=toolset_compute())
    assert names(agent) == bet_tools.DECLARED["custom-metricflow-compute"] == bet_tools.METRICFLOW
    assert bet_tools.DECLARED["cc-metricflow-compute"] == bet_tools.METRICFLOW
    assert agent.instruction == INSTRUCTION_COMPUTE != INSTRUCTION
    assert "never compute" in INSTRUCTION and "never compute" not in INSTRUCTION_COMPUTE
    for kept in ("never write SQL", "Never estimate or recall a figure", "sum of its numerator"):
        assert kept in INSTRUCTION_COMPUTE
    assert (
        "custom-metricflow-compute" in bet_eval.ARMS
        and bet_eval.RUNG["custom-metricflow-compute"] == 4
    )
    assert probe("387_cc_strict.py").instruction("cc-metricflow-compute") == INSTRUCTION_COMPUTE
