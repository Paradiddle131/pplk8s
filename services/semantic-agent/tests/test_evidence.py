"""The evidence checker ties each figure to a tool result and each method claim to the trace."""

import json

from semantic_agent import evidence
from semantic_agent.evidence import Call, check_turn

REVENUE = Call(
    "query_metrics",
    {"metrics": ["revenue_eur", "orders_total"]},
    '{"rows": [{"metric_time__day": "2026-10-01", "revenue_eur": 1850.3412, "orders_total": 15},'
    ' {"metric_time__day": "2026-10-02", "orders_cancelled": 5}]}',
)
SQL = Call(
    "execute_sql", {"sql": "select sum(revenue_eur) from gold.daily_sales"}, '{"rows": [[42]]}'
)
PYTHON = Call("run_python", {"code": "import numpy"}, "ok")


def statuses(answer: str, calls=(REVENUE,), question: str = "How much revenue on 1 October 2026?"):
    return {f.text: f.status for f in check_turn(question, answer, list(calls)).figures}


def test_a_figure_a_result_holds_is_cited_at_the_answers_precision():
    assert statuses("Revenue was €1,850.34 over 15 orders.") == {"1,850.34": "cited", "15": "cited"}
    assert statuses("Revenue was about €1.85k.") == {"1.85k": "cited"}
    assert statuses("Revenue was €1,850.") == {"1,850": "cited"}


def test_a_figure_off_by_more_than_its_rounding_is_untraced():
    assert statuses("Revenue was €1,850.37.") == {"1,850.37": "untraced"}
    assert statuses("Revenue was €2,104.") == {"2,104": "untraced"}


def test_a_ratio_and_a_percentage_of_two_cited_figures_are_derived():
    verdict = check_turn("What was the AOV?", "AOV was €123.36.", [REVENUE])
    assert [(f.status, f.source) for f in verdict.figures] == [("derived", "1850.34 / 15")]
    # 5 of 15 orders cancelled: a third, as a percentage
    assert statuses("The cancellation rate was 33.3%.") == {"33.3": "derived"}


def test_a_rate_in_a_result_cites_its_percentage():
    call = Call("query_metrics", {}, '{"cancellation_rate": 0.16666666666666666}')
    assert statuses("16.67% of orders were cancelled.", [call]) == {"16.67": "cited"}


def test_dates_years_ordinals_list_markers_and_the_questions_numbers_are_not_figures():
    answer = (
        "On 1 and 2 October 2026 (2026-10-01T00:00Z, at 10:30) the 3rd campaign led.\n"
        "1. Top 5 customers spent €1,850.34."
    )
    assert statuses(answer, question="Who were the top 5 customers in 2026?") == {
        "1,850.34": "cited"
    }


def test_a_quoted_freshness_statement_is_not_a_figure():
    answer = (
        "Revenue was €1,850.34. Late: sales.silver is ready only up to 2026-10-03T00:00Z,"
        " older than its 36 h deadline. Fresh: returns.silver is ready up to 2026-10-03T00:00Z."
    )
    assert statuses(answer) == {"1,850.34": "cited"}


def test_a_figure_from_an_earlier_turn_of_the_conversation_is_cited():
    verdict = check_turn("And per order?", "That is 15 orders.", [SQL], earlier=[REVENUE])
    assert [f.status for f in verdict.figures] == ["cited"]


def test_a_python_claim_needs_a_python_step():
    answer = "I computed it in Python: 42."
    without = check_turn("Q?", answer, [SQL])
    assert [(m.method, m.status) for m in without.methods] == [("python", "unsupported")]
    with_python = check_turn("Q?", answer, [SQL, PYTHON])
    assert [(m.method, m.status, m.evidence) for m in with_python.methods] == [
        ("python", "supported", "run_python")
    ]


def test_k_means_claimed_over_plain_sql_is_unsupported():
    verdict = check_turn("Segment customers", "A k-means clustering found 42 segments.", [SQL])
    assert [(m.method, m.status) for m in verdict.methods] == [("clustering", "unsupported")]
    kmeans = Call("execute_sql", {"sql": "create model m options(model_type='kmeans')"}, "ok")
    assert (
        check_turn("Q", "A k-means clustering found it.", [kmeans]).methods[0].status == "supported"
    )


def test_a_negated_or_hedged_method_is_no_claim():
    answer = "I cannot run a regression here. A forecast would need Python."
    assert check_turn("Q?", answer, [SQL]).methods == []


def test_a_full_scan_claim_needs_sql_without_a_limit():
    answer = "I scanned all the order rows."
    assert check_turn("Q?", answer, [SQL]).methods[0].status == "supported"
    limited = Call("execute_sql", {"sql": "select * from orders limit 10"}, "[]")
    assert check_turn("Q?", answer, [limited]).methods[0].status == "unsupported"


def test_the_cli_counts_unrecorded_turns_and_shares_per_arm_and_model(tmp_path, capsys):
    row = {
        "arm": "a",
        "model": "m",
        "run": 1,
        "case": "c",
        "turns": [
            {
                "text": "Revenue was €2,104.",
                "outcome": "right",
                "calls": [{"tool": "q", "args": {}, "result": '{"v": 1850.34}'}],
            },
            {"text": "€1,850.34.", "outcome": "wrong", "calls": [{"tool": "q", "args": {}}]},
            {"text": "No data.", "calls": []},
        ],
    }
    log = tmp_path / "eval.jsonl"
    log.write_text(json.dumps(row) + "\n")
    questions = tmp_path / "set.yaml"
    questions.write_text("questions:\n- id: c\n  turns:\n  - question: Revenue?\n")
    assert evidence.main([str(log), "--questions", str(questions), "--examples", "5"]) == 0
    out = capsys.readouterr().out
    assert "1 checked, 1 made no call, 1 made calls whose results the log lacks" in out
    assert "| a | m | 1 | 100% (1/1) | 0% (0/1) | 1 | 100% (1/1) | 0% (0/1) |" in out
    assert "untraced: €2,104" not in out and "untraced: 2,104" in out


def test_the_cli_sets_apart_turns_whose_results_the_log_cut(tmp_path, capsys):
    head = '{"rows": [' + " " * 20
    row = {
        "arm": "a",
        "model": "m",
        "case": "c",
        "turns": [
            {"question": "Q?", "text": "It was 89.75.", "calls": [{"tool": "q", "result": head}]}
        ],
    }
    log = tmp_path / "eval.jsonl"
    log.write_text(json.dumps(row) + "\n")
    assert evidence.main([str(log), "--result-cap", str(len(head)), "--examples", "1"]) == 0
    out = capsys.readouterr().out
    assert "| 0 | - |" in out and "a result cut" in out
