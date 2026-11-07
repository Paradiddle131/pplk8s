"""The report's set families (#378), reader rule (#393, #394) and glossary coverage (#395)."""

import importlib.util
import json
import re
from pathlib import Path

BUILD = Path(__file__).resolve().parents[3] / "docs/research/semantic-bet/report/build.py"
spec = importlib.util.spec_from_file_location("bet_report_build", BUILD)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


RESULTS = BUILD.parents[1] / "results.json"
EVALS = RESULTS.parents[3] / "services/semantic-agent/evals"
# Process words a reader of the page never sees (#393): versions, adoption, retirement, hashes.
PROCESS = re.compile(
    r"superseded|not yet adopted|retired|retirement|sha256|RULE\.md|#\d{3}|owner's go|\bv[12]\b"
)


def test_the_figures_show_v1_until_the_owners_go_and_v2_is_drawn_in_the_map_only():
    present, appendix = build.shown_sets(["frozen", "hard", "hard-v2"], {})
    assert present == ["frozen", "hard"]
    assert appendix == [("hard-v2", "Extended hard set")]


def test_showing_v2_puts_v1_in_the_map_only_under_its_plain_name():
    present, appendix = build.shown_sets(["frozen", "hard", "hard-v2"], {"hard": "hard-v2"})
    assert present == ["frozen", "hard-v2"]
    assert appendix == [("hard", "Hard set")]
    assert not any(PROCESS.search(label) for _, label in appendix)


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


def test_the_built_page_carries_no_process_metadata_and_no_retired_question(tmp_path):
    out = tmp_path / "index.html"
    build.build(str(RESULTS), str(RESULTS.parent), str(EVALS), str(out))
    page = out.read_text(encoding="utf-8")
    payload = re.search(r"const D = (\{.*?\});\nwindow\.REPORT", page, re.S).group(1)
    data = json.loads(payload.replace("<\\/", "</"))
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    scored = {c for spec in results["sets"].values() for c in spec.get("cases") or []}
    retired = {c for spec in results["sets"].values() for c in spec.get("retired") or []} - scored
    assert retired, "the results hold retired questions, so this test checks something"
    shown = json.dumps(data)
    assert not [c for c in retired if f'"{c}"' in shown]
    for spec in data["questionSets"].values():
        assert set(spec) == {"label", "shown", "groups", "questions"}
        assert all(not ({"retired", "new"} & set(q)) for q in spec["questions"])
    visible = re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", visible)
    assert not PROCESS.search(text), PROCESS.search(text)


def test_every_group_bucket_kind_rubric_family_and_role_the_page_can_show_has_a_glossary_entry():
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    terms = {k for k, _, _ in build.TERMS}
    shown = {k for k, _ in build.GROUPS_ALL} | {k for k, _, _ in build.BUCKETS}
    shown |= {"decides", "check", "cc"}
    for spec in results["sets"].values():
        shown |= {g for gs in (spec.get("groups") or {}).values() for g in gs}
        for q in spec.get("questions") or []:
            for field in ("groups", "kinds", "rubric"):
                shown |= set(q.get(field) or [])
    missing = sorted(k for k in shown if build.term_key(k) not in terms)
    families = [f for f in build.FAMILY_LABEL if f != "other"]
    missing += sorted("family-" + f for f in families if "family-" + f not in terms)
    assert not missing, f"shown with no glossary entry: {missing}"


def test_every_glossary_term_has_a_type():
    untyped = [k for k, _, _ in build.TERMS if k not in build.TERM_TYPE]
    assert not untyped, f"glossary terms with no type: {untyped}"


def _built(tmp_path):
    out = tmp_path / "index.html"
    build.build(str(RESULTS), str(RESULTS.parent), str(EVALS), str(out))
    page = out.read_text(encoding="utf-8")
    payload = re.search(r"const D = (\{.*?\});\nwindow\.REPORT", page, re.S).group(1)
    return page, json.loads(payload.replace("<\\/", "</"))


def test_the_question_section_sits_in_its_part(tmp_path):
    page, _ = _built(tmp_path)
    at = page.index('id="question-guide"')
    assert page.index('id="view-question-sets"') < at < page.index('id="view-method"')
    assert at > page.index('id="view-setups"')


def test_each_question_set_has_its_anchor_in_the_section(tmp_path):
    page, data = _built(tmp_path)
    section = page[page.index('id="question-guide"') : page.index('id="view-method"')]
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    for st in results["sets"]:
        assert f'id="qs-{st}"' in section, st
    assert set(data["questionGuide"]["setLabel"]) == set(results["sets"])


def test_no_retired_question_reaches_the_section_or_its_data(tmp_path):
    page, data = _built(tmp_path)
    section = page[page.index('id="question-guide"') : page.index('id="view-method"')]
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    scored = {c for spec in results["sets"].values() for c in spec.get("cases") or []}
    retired = {c for spec in results["sets"].values() for c in spec.get("retired") or []} - scored
    assert retired
    guide = data["questionGuide"]
    assert set(guide["q"]) == scored
    shown = json.dumps(guide)
    assert not [c for c in retired if c in section or f'"{c}"' in shown]
    assert all(set(c["ids"]) <= scored for c in guide["cats"])


def test_the_see_all_buttons_exist_one_per_category_visible_and_wired_to_the_browser(tmp_path):
    page, data = _built(tmp_path)
    buttons = re.findall(r'<button[^>]*class="qs-seeall"[^>]*>', page)
    cats = data["questionGuide"]["cats"]
    assert len(buttons) == len(cats) > 0
    assert not [b for b in buttons if re.search(r"\shidden(\s|=|>|$)", b)]
    assert {re.search(r'data-category="([^"]+)"', b).group(1) for b in buttons} == {
        c["key"] for c in cats
    }
    # a click dispatches qs:see-all; the question browser listens for it and opens a modal
    assert 'new CustomEvent("qs:see-all"' in page
    assert 'document.addEventListener("qs:see-all"' in page
    assert "dlg.showModal()" in page


def test_every_list_title_and_category_of_the_section_is_a_typed_glossary_term(tmp_path):
    _, data = _built(tmp_path)
    terms = {k for k, _, _ in build.TERMS}
    guide = data["questionGuide"]
    keys = [x["key"] for x in guide["lists"]] + [c["key"] for c in guide["cats"]]
    keys += ["obvious-sql", "groups", "declined", "unclear", "confident-wrong"] + [
        build.term_key(s) for s in guide["setLabel"]
    ]
    assert not [k for k in keys if k not in terms or k not in build.TERM_TYPE]


def test_the_decision_maps_set_switch_covers_every_set_with_rows(tmp_path):
    _, data = _built(tmp_path)
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    with_rows = {a["set"] for a in build.strict_view(results["arms"])}
    assert set(data["mapOrder"]) == with_rows and set(data["setOrder"]) < with_rows
    for st in data["mapOrder"]:
        rows = data["sets"][st]["rows"]
        assert rows and all({"cov", "sel", "pass3"} <= set(r) for r in rows)
        assert data["sets"][st]["counts"] == (st in data["setOrder"])
    # the figures other than the map draw the counted sets only
    assert data["setOrder"] == ["frozen", "hard"]


def test_no_appendix_remains(tmp_path):
    page, _ = _built(tmp_path)
    assert 'other-set-versions"' not in page and 'href="#other-set-versions"' not in page
    assert not re.search(r"class=\"apx|Appendix|the appendix", page)
    assert "<!--APPENDIX-->" not in (BUILD.parent / "template.html").read_text(encoding="utf-8")


def test_the_setup_explorer_comes_before_the_setup_map(tmp_path):
    page, _ = _built(tmp_path)
    one = page.index("What each setup is, one at a time</h2>")
    assert page.index('id="view-setups"') < one < page.index(">What each setup is</h2>")


def test_coverage_selective_accuracy_and_pass3_arithmetic():
    pc = {
        "a": ["right", "right", "right"],
        "b": ["right", "declined", "wrong"],
        "c": ["declined", "declined", "confident-wrong"],
    }
    got = build.run_scores(pc)
    assert got["nRuns"] == 9 and got["answered"] == 6
    assert got["cov"] == 6 / 9  # (runs - declined) / runs
    assert got["sel"] == 4 / 6  # right answered / answered
    assert got["pass3"] == 1 / 3  # questions right on all three runs / questions
    # a run scored right that only asked which meaning was meant is a decline for coverage
    asked = build.run_scores(pc, {"b": 1})
    assert asked["cov"] == 5 / 9 and asked["sel"] == 3 / 5
    # pass^3 only when every question has three runs; selective accuracy empty with nothing answered
    assert build.run_scores({"a": ["right", "right"], "b": ["right"] * 3})["pass3"] is None
    none = build.run_scores({"a": ["declined"] * 3})
    assert none["cov"] == 0 and none["sel"] is None and none["pass3"] == 0
    assert build.run_scores({})["cov"] is None


def test_an_asked_back_turn_reads_as_a_decline_and_a_define_answer_does_not():
    assert build.asks_back([{"outcome": "right", "text": "Do you mean gross sales or net sales?"}])
    assert not build.asks_back(
        [{"outcome": "right", "text": "Sales were 868.65 EUR. Did you mean net sales?"}]
    )
    assert not build.asks_back(
        [{"outcome": "right", "text": "Revenue is the sum of non-cancelled order amounts."}]
    )
    assert not build.asks_back([{"outcome": "declined", "text": "Which sales do you mean?"}])


def test_the_maps_scores_match_the_runs_they_come_from(tmp_path):
    _, data = _built(tmp_path)
    for st in data["mapOrder"]:
        for r in data["sets"][st]["rows"]:
            o = r["outcomes"]
            if r["cov"] is None:
                continue
            assert 0 <= r["cov"] <= 1 and (r["sel"] is None or 0 <= r["sel"] <= 1)
            if r["pass3"] is not None:
                assert r["pass3"] <= r["acc"][0] + 1e-9  # never above accuracy
            if sum(o.values()) == r["nRuns"]:
                assert abs(r["cov"] - (r["nRuns"] - o.get("declined", 0)) / r["nRuns"]) < 0.1


def test_the_new_measures_are_typed_terms_with_a_calculation_and_the_map_shows_them(tmp_path):
    page, data = _built(tmp_path)
    terms = {t["key"]: t for t in data["terms"]}
    for key in ("accuracy", "coverage", "selective-accuracy", "pass-3", "confident-wrong"):
        assert (
            key in terms
            and terms[key]["type"] == "Measures and statistics"
            and terms[key].get("calc")
        )
        assert key in build.TERM_TYPE
    assert "declin" in terms["coverage"]["calc"]
    for key in ("accuracy", "coverage", "selective-accuracy", "pass-3"):
        assert f'["{key}"' in page or f'"{key}",' in page  # the map's column reads its term


def test_every_terms_longer_explanation_is_structured_and_not_its_short_text(tmp_path):
    _, data = _built(tmp_path)
    floor = next(t for t in data["terms"] if t["key"] == "over-the-floor")
    assert "paired by question, in points" not in floor["text"]
    labels = [k for k, _ in floor["more"]]
    assert {"The floor", "Per question", "Combined", "Example"} <= set(labels)
    for t in data["terms"]:
        assert t.get("more"), t["key"]
        assert all(
            len(pair) == 2 and pair[1] != t["text"] and len(pair[1]) < 200 for pair in t["more"]
        ), t["key"]


def test_the_build_refuses_a_longer_text_that_repeats_its_one_liner():
    one = {
        "key": "x",
        "text": "How often a setup is right, on every run.",
        "more": [["Example", "1 of 2"]],
    }
    assert build.check_longer_lines([one]) == []
    same = dict(one, more=[["Again", "How often a setup is right on every run"]])
    holds = dict(one, key="y", calc="how often a setup is right, on every run. Then more.")
    assert build.check_longer_lines([same, holds]) == ["x", "y"]
    terms = build.glossary({"cats": [], "q": {}}, {}, [])
    assert build.check_longer_lines(terms) == []
    one_liners = {k: t for k, _, t in build.TERMS}
    assert one_liners["accuracy"].startswith("How often a setup is right")


def test_a_hidden_setup_is_nowhere_on_the_page(tmp_path):
    page, data = _built(tmp_path)
    assert "native-context-python" in build.HIDDEN_ARMS
    assert "native-context-python" not in page
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert any(
        a["arm"] == "native-context-python" for a in results["arms"]
    )  # its runs stay in the results


def test_every_model_name_the_page_shows_has_a_glossary_term_and_the_tools_are_defined():
    """#395's newcomer read: the models, tools and products a setup names are explained."""
    keys = {k for k, _, _ in build.TERMS}
    for k in (
        *("metricflow", "semantic-layer", "dbt", "adk", "mcp", "knowledge-catalog", "lightdash"),
        *("nemotron", "gemini", "claude-models", "harness", "points", "tolerance", "hedge"),
        *("judge", "rung"),
    ):
        assert k in keys and k in build.TERM_TYPE, k
    template = (BUILD.parent / "template.html").read_text()
    for k in re.findall(r'\[/\^[^/]+/, "([a-z-]+)"\]', template):
        assert k in keys, k


def test_the_no_arithmetic_metricflow_setups_say_why_obeying_scores_lower():
    """#400: the old setups stay on the page; their description explains the model order."""
    for arm in ("custom-metricflow", "cc-metricflow"):
        assert re.search(r"never (to )?compute", build.DESC[arm]), arm
