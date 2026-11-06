"""The report's set families (report/build.py, RULE.md § Set versions, #378)."""

import importlib.util
from pathlib import Path

BUILD = Path(__file__).resolve().parents[3] / "docs/research/semantic-bet/report/build.py"
spec = importlib.util.spec_from_file_location("bet_report_build", BUILD)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_the_page_shows_v1_until_the_owners_go_and_keeps_v2_in_the_appendix():
    present, appendix = build.shown_sets(["frozen", "hard", "hard-v2"], {})
    assert present == ["frozen", "hard"]
    assert [st for st, _ in appendix] == ["hard-v2"]
    assert "not yet adopted" in appendix[0][1] and "#380" in appendix[0][1]


def test_showing_v2_puts_v1_in_the_appendix_labelled_superseded():
    present, appendix = build.shown_sets(["frozen", "hard", "hard-v2"], {"hard": "hard-v2"})
    assert present == ["frozen", "hard-v2"]
    assert appendix == [("hard", "Hard set, superseded by hard set v2")]


def test_each_log_goes_to_the_set_its_longest_prefix_names():
    by_name = {
        name: next(s for p, s in build.LOG_PREFIX if name.startswith(p))
        for name in (
            "eval-native-kc.jsonl",
            "eval-hard-native-kc.jsonl",
            "eval-hard-v2-local.jsonl",
        )
    }
    assert list(by_name.values()) == ["frozen", "hard", "hard-v2"]


def test_the_appendix_lists_each_hidden_sets_setups_from_the_results():
    arm = {"set": "hard-v2", "arm": "native-bare", "model": "google-data-agent", "cases": 43}
    arm |= {"of_cases": 58, "accuracy": [0.65, 0.5, 0.8], "confident_wrong": [0.28, 0.2, 0.4]}
    arm |= {"groups": {"composable": [0.67, 20]}}
    html = build.appendix_html({"arms": [arm]}, [("hard-v2", "Hard set v2, not yet adopted")])
    assert 'id="other-set-versions"' in html and "43 of 58" in html and "65%" in html
    assert build.appendix_html({"arms": [arm]}, []) == ""
