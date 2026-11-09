"""The strict headless runner's transcript audit (#387): offline, on hand-made turns."""

import importlib.util
import json
from pathlib import Path

PROBE = Path(__file__).resolve().parents[3] / "docs/research/semantic-bet/probes/387_cc_strict.py"
spec = importlib.util.spec_from_file_location("cc_strict", PROBE)
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)

TOOLS = cc.tool_names("cc-metricflow")
QUERY = "mcp__semantic__query_metrics"


def turn(answer, calls=(), text="", question="Revenue on 1 and 2 October 2026?"):
    return {"question": question, "answer": answer, "calls": list(calls), "text_all": text}


def test_a_figure_from_a_tool_result_is_cited_and_a_computed_one_is_not():
    rows = {"tool": QUERY, "full": '{"rows": [{"revenue_eur": 1850.34}, {"orders": 25}]}'}
    ok = cc.audit(
        "cc-metricflow", [turn("Revenue was €1,850.34 on 25 orders.", [rows])], TOOLS, TOOLS
    )
    assert ok["tools_ok"] and ok["uncited"] == []
    # 74.01 is 1850.34 / 25, computed by the model: reported, never a fault.
    made = cc.audit("cc-metricflow", [turn("Average order value €74.01.", [rows])], TOOLS, TOOLS)
    assert made["tools_ok"] and made["uncited"] == [[0, 74.01]]


def test_dates_years_and_the_question_numbers_are_not_figures():
    got = cc.audit(
        "cc-metricflow",
        [turn("On 2 October 2026 (Oct 1, 2026-10-01) at 09:00: none.")],
        TOOLS,
        TOOLS,
    )
    assert got["uncited"] == []


def test_a_rate_matches_its_percentage():
    rows = {"tool": QUERY, "full": '{"rows": [{"share": 0.3513}]}'}
    assert (
        cc.audit("cc-metricflow", [turn("35.1% of revenue.", [rows])], TOOLS, TOOLS)["uncited"]
        == []
    )


def test_a_built_in_or_foreign_tool_fails_the_tool_check():
    bad = cc.audit("cc-metricflow", [turn("x", [{"tool": "Bash", "full": ""}])], TOOLS, TOOLS)
    assert not bad["tools_ok"] and bad["outside"] == ["Bash"]
    # An init list unlike the server's fails it too.
    assert not cc.audit("cc-metricflow", [turn("x")], [*TOOLS, "Bash"], TOOLS)["tools_ok"]


def test_a_call_written_as_text_without_a_real_one_is_flagged():
    got = cc.audit(
        "cc-metricflow", [turn("€10.", text='query_metrics(metrics=["x"])')], TOOLS, TOOLS
    )
    assert got["fabricated_turns"] == [0] and got["uncited"] == [[0, 10.0]]


def test_an_answers_file_name_reads_its_longest_setup_first():
    assert cc._parts("cc-metricflow-compute-haiku-hard-v2") == (
        "cc-metricflow-compute",
        "haiku",
        "hard-v2",
    )
    assert cc._parts("cc-metricflow-sonnet-frozen") == ("cc-metricflow", "sonnet", "frozen")


def test_a_filtered_query_the_server_failed_is_a_filter_fault():
    """#432: until the fix, every filtered query_metrics call answered "Error executing tool"."""
    failed = {
        "tool": "mcp__semantic__query_metrics",
        "args": {"metrics": ["revenue_eur"], "filters": [{"dimension": "customer__country"}]},
        "result": "Error executing tool query_metrics",
    }
    plain = {**failed, "args": {"metrics": ["revenue_eur"]}}
    assert cc.filter_fault({"turns": [{"calls": [failed]}]})
    assert not cc.filter_fault({"turns": [{"calls": [plain]}]})
    assert not cc.filter_fault({"turns": [{"calls": [{**failed, "result": '{"rows": []}'}]}]})


def test_a_stale_answer_is_never_read(tmp_path, monkeypatch):
    line = '{"case": "c", "run": 1, "turns": []}'
    answers = tmp_path / "a.jsonl"
    answers.write_text(line + "\n" + '{"case": "c", "run": 2, "turns": []}\n')
    stale = tmp_path / "stale.jsonl"
    stale.write_text(json.dumps({"answer_sha": cc.answer_sha(line)}) + "\n")
    monkeypatch.setattr(cc, "STALE", stale)
    assert cc.recorded_runs(answers) == {("c", 2)}
