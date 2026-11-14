"""The report's set families (#378), reader rule (#393, #394) and glossary coverage (#395)."""

import html
import importlib.util
import json
import re
from html.parser import HTMLParser
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
    assert page.index('id="question-sets"') < at < page.index('id="method"')
    assert at > page.index('id="setups"')


def test_each_question_set_has_its_anchor_in_the_section(tmp_path):
    page, data = _built(tmp_path)
    section = page[page.index('id="question-guide"') : page.index('id="method"')]
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    for st in results["sets"]:
        assert f'id="qs-{st}"' in section, st
    assert set(data["questionGuide"]["setLabel"]) == set(results["sets"])


def test_no_retired_question_reaches_the_section_or_its_data(tmp_path):
    page, data = _built(tmp_path)
    section = page[page.index('id="question-guide"') : page.index('id="method"')]
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


def test_the_setups_tab_is_on_the_kit_in_the_one_type_standard(tmp_path):
    """Both setup sections are kit sections (a kit head each), their words at 1rem in the kit's
    family and full ink, every control wears the kit's focus ring, and no text says how to use
    them."""
    page, _ = _built(tmp_path)
    panel = page[page.index('id="setups" data-view') : page.index('id="question-sets" data-view')]
    for sec, h in (("sm", "sm-h"), ("sxb", "sxb-h")):
        assert f'<section class="{sec} rk-section"' in panel, sec
        assert f'<div class="rk-head"><h2 id="{h}">' in panel, sec
    # the tab maps the report's paler inks and rules onto the kit's, as the other kit tabs do
    inks = (
        ".mfa, .er, .st, .qs, .mg { --ink-2: var(--ink); --ink-3: var(--ink); --rule: var(--hair);"
    )
    assert inks in page
    styles = "".join(re.findall(r"<style>(.*?)</style>", panel, re.S))
    rules = [r for r in styles.split("\n") if r.startswith((".sm .sm-", ".sxb .sxb-"))]
    html_rules = [r for r in rules if not r.startswith(".sm .sm-sheet")]
    small = [r for r in html_rules if re.search(r"font-size: 1[0-5](\.\d)?px", r)]
    assert not small, small  # words at 1rem
    # the sheets: every label at the chart size (14px, ids in mono at 13px), drawn one unit a pixel
    assert ".sm .sm-sheet text { fill: var(--ink); font-size: 14px; letter-spacing: 0; }" in styles
    assert ".sxb svg text { font-family: var(--sans); font-size: 14px; letter-spacing: 0;" in styles
    sizes = {float(x) for x in re.findall(r"font-size: (\d+(?:\.\d+)?)px", styles)}
    assert sizes and min(sizes) >= 13, sorted(sizes)
    script = "".join(re.findall(r"<script>(.*?)</script>", panel, re.S))
    assert "svg.style.width = K.W" in script and "MINW = 944" in script  # the map at full size
    assert 'style="width:${W}px"' in script  # the sequence too
    assert "(h - 16 - 8 - rh)" not in script  # no shrinking the map to the screen's height
    assert not [r for r in html_rules if "outline: 2px solid var(--mf)" in r]
    assert "g[tabindex]:focus-visible { outline: 2.5px solid var(--line)" in styles
    for gone in (
        "Hover or tap",
        "Escape lets go",
        "scrolls sideways.</p>",
        "Arrow keys move",
        "Pick a setup",
    ):
        assert gone not in panel, gone


def test_the_setups_tab_sets_its_parts_apart_with_the_kits_levels(tmp_path):
    """Owner, 2026-11-08: the parts of each setup section read apart at a glance. The ladders sit
    on the kit's raised side column, each sheet is a figure holding its key, the explorer's two
    parts and the map's readout are kit parts (a head over a 1px ink rule), and each fact is said
    once: no change summary over the list of changes, no tag line repeating the rung's name, no
    caption restating its sequence, no map lede repeating the readout."""
    page, _ = _built(tmp_path)
    panel = page[page.index('id="setups" data-view') : page.index('id="question-sets" data-view')]
    assert '<div class="sxb-wrap rk-split">' in panel
    assert '<div class="sxb-pick rk-aside">' in panel and '<h3 class="sxb-pick-h"' in panel
    assert '<div class="sxb-stage rk-stage">' in panel
    assert (
        '<figure class="sxb-fig rk-fig"><svg' in panel and '<ul class="sxb-legend rk-key"' in panel
    )
    assert (
        '<div class="sxb-panel rk-parts"><div class="sxb-change rk-part"></div>'
        '<div class="sxb-seq rk-part"></div></div>' in panel
    )
    assert '<div class="sm-aside rk-aside">' in panel
    fig = panel.index('<figure class="sm-fig rk-fig">')
    assert (
        fig
        < panel.index('<ul class="sm-legend rk-key"')
        < panel.index('<div class="sm-read rk-part"')
    )
    script = "".join(re.findall(r"<script>(.*?)</script>", panel, re.S))
    assert "<h4>What changes from" in script and "<h4>On one question</h4>" in script
    assert 'why: "' not in script and "S.why" not in script
    assert '"rung " + m[1] + ": "' not in script  # the tag line names the rung by number only
    assert "MetricFlow turns the definition into SQL" not in script
    lede = re.search(r'<p class="sm-lede">(.*?)</p>', panel, re.S).group(1)
    assert (
        "write their own SQL" not in lede and "never writes SQL" not in lede
    )  # the readout says it
    # the kit carries the levels the tab uses (vendored from upstream, never copied into the page)
    kit = (BUILD.parent.parent / "report-kit/kit/section.css").read_text(encoding="utf-8")
    assert ".rk-aside {" in kit and ".rk-part {" in kit and ".rk-fig {" in kit


def test_the_question_sets_tab_is_on_the_kit(tmp_path):
    """The Question sets tab on report-kit: two kit sections (the sets as parts, the guide as the
    kit's split with a folding side column and the kit's step row); outcomes as the kit's status
    marks, as the rest of the page draws them; one runs table, never split side by side; headings
    step down one level at a time, in the guide and in the question browser."""
    page, _ = _built(tmp_path)
    panel = page[page.index('id="question-sets" data-view') : page.index('id="method" data-view')]
    assert 'class="view rk-kit rk-js qs-v" id="question-sets"' in page
    assert panel.count('<section class="rk-section') == 2
    assert panel.count('<article class="qs-set rk-part"') >= 2
    assert '<div class="qs-guide rk-split">' in panel and "rk-aside" in panel
    assert '<button type="button" class="rk-fold" aria-controls="qs-kinds" hidden>' in panel
    assert '<div class="rk-step qs-step" id="qs-step">' in panel
    assert '<h3 id="qs-cat-h"' in panel and 'data-hl="4"' in panel and "<h5" not in panel
    script = "".join(re.findall(r"<script>(.*?)</script>", panel, re.S))
    # the kit's marks: right ok, declined no, wrong warn, confident-wrong bad, not run a dot
    assert 'const KIND = { "0": "ok", "1": "no", "2": "warn", "4": "bad", ".": "" };' in script
    assert "function swatch(" not in script and "<rect" not in script
    assert 'class="rk-table qs-rt"' in script and "cells.slice(0, half)" not in script
    # the item takes its own height: no field reserves the tallest content
    assert "minHeight" not in script and "function measure(" not in script
    # the browser is the kit's dialog, its question an h3 under its h2, no eyebrow over the h2
    assert 'dlg.className = "qs qb rk-dialog"' in script and 'bc.dataset.hl = "3"' in script
    assert "qb-kick" not in script


def test_the_setups_ladders_fold_on_a_phone_and_never_grey_out(tmp_path):
    """Owner, 2026-11-08 (the trial's misses): stacked above their stage, both ladders fold behind
    the kit's button naming the current choice; pointing at a setup lights its row on a band instead
    of fading the rest to grey; the explorer's chips are rows of the panel, not boxes inside it."""
    page, _ = _built(tmp_path)
    panel = page[page.index('id="setups" data-view') : page.index('id="question-sets" data-view')]
    # the kit's fold (.rk-fold), the page's own (window.reportFold, .fold-btn) gone
    assert "window.reportFold" not in page and "fold-btn" not in page
    assert panel.count('class="rk-fold" aria-controls=') == 2
    assert 'aria-controls="sxb-ladder"' in panel and 'aria-controls="sm-rungs"' in panel
    script = "".join(re.findall(r"<script>(.*?)</script>", panel, re.S))
    assert script.count("ReportKit.fold.init(") == 2
    assert script.count("ReportKit.fold.current(") == 2
    assert "data-rk-fold-pick" in script
    styles = "".join(re.findall(r"<style>(.*?)</style>", panel, re.S))
    assert ".sm-s:not(.on) { opacity" not in styles and ".sm-rhd { opacity" not in styles
    assert not re.search(r"\.sm-rungs[^{]*\{[^}]*opacity", styles)
    chip = re.search(r"\.sxb \.sxb-chip \{[^}]*\}", styles).group(0)
    assert "border: 0;" in chip


def test_the_page_folds_unclear_runs_into_wrong(tmp_path):
    _, data = _built(tmp_path)
    rows = [r for st in data["sets"].values() for r in st["rows"]]
    assert rows and not [r for r in rows if "3" in r["units"] or "unclear" in r["outcomes"]]
    assert not [r for r in rows if r.get("example") and r["example"]["outcome"] == "unclear"]
    assert build.shown_outcomes({"wrong": 2, "unclear": 3, "right": 1}) == {"wrong": 5, "right": 1}


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
    assert page.index('id="setups"') < one < page.index(">What each setup is</h2>")


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


def test_each_setup_leads_with_its_default_model_never_its_best_one(tmp_path):
    """A setup's main row is the model it would ship on, fixed before any score: Gemini's default
    for Google's agent even where another mode holds the managed best (the owner saw 67 in a chart
    and 80 in the map for one setup, 2026-11-07)."""
    _, data = _built(tmp_path)
    for st in data["mapOrder"]:
        rows = data["sets"][st]["rows"]
        for arm in {r["arm"] for r in rows if r["family"] == "da"}:
            mine = [r for r in rows if r["arm"] == arm and r["plotted"]]
            default = [r for r in mine if r["model"].endswith("(MODEL_UNSPECIFIED)")]
            if default:
                main = [r["model"] for r in mine if r["primary"]]
                assert main == [default[0]["model"]], (st, arm)
        assert any(r["managedBest"] for r in rows) or not any(r["family"] == "da" for r in rows)
    assert "main-model" in {k for k, _, _ in build.TERMS}


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


def test_figure_one_and_figure_four_compare_with_the_same_managed_best(tmp_path):
    """#409 (owner, 2026-11-07): one bar for "the managed best", never the best per group."""
    _, data = _built(tmp_path)
    tw = data["twin"]
    strip = {r["set"]: r for r in tw["strip"]}
    for row in tw["map"]:
        s = strip.get(row["set"])
        if not s or s["mbUnc"] is None:
            continue
        gap = s["mbUnc"] - s["unc"]
        cell = row["cells"][2]
        if abs(gap) <= 5:
            assert cell == "level with", (row["set"], cell, gap)
        else:
            assert cell.startswith(f"{abs(gap)} points"), (row["set"], cell, gap)


def test_every_per_set_caption_names_its_set(tmp_path):
    """#409: a caption that follows a figure's set switch says which set its numbers are from."""
    _, data = _built(tmp_path)
    labels = {s: v["label"].lower() for s, v in data["sets"].items()}
    for fig in ("scatter", "slope", "ladder"):
        for s, text in (data["sentences"].get(fig) or {}).items():
            assert text.startswith(f"On the {labels[s]},"), (fig, s, text)


VOID = {
    "area",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


def _summary(page):
    """The Summary tab's markup, without its style block."""
    tab = page[page.index('id="summary"') : page.index('id="decision-map"')]
    return re.sub(r"<style>.*?</style>", "", tab, flags=re.S)


def test_the_summary_shows_the_approaches_and_takeaways_from_the_brief(tmp_path):
    """The Summary tab is the Approaches page's two sections, generated by the brief's own code."""
    page, _ = _built(tmp_path)
    tab = _summary(page)
    assert tab.index('id="approaches-h"') < tab.index('id="takeaways-h"')
    assert build.brief.summary(RESULTS) in page
    for gone in ('id="abstract"', 'id="winners"', "In short.", "Who wins each kind of question"):
        assert gone not in page, gone


def test_the_summary_runs_from_most_native_to_most_custom(tmp_path):
    page, _ = _built(tmp_path)
    tab = _summary(page)
    table = tab[: tab.index("</table>")]
    names = [name for name, *_ in build.brief.APPROACHES]
    positions = [table.index(html.escape(n)) for n in names]
    assert positions == sorted(positions)
    assert names[0].startswith("Google's data agent") and names[-1].startswith("Our agent")


def test_the_summary_recommends_nothing(tmp_path):
    page, _ = _built(tmp_path)
    text = re.sub(r"<[^>]+>|data-tip=\"[^\"]*\"", " ", _summary(page)).lower()
    text = " ".join([text] + re.findall(r'data-tip="([^"]*)"', _summary(page).lower()))
    for word in ("recommend", "verdict", "best", "winner", "wins", "leader", "should"):
        assert not re.search(rf"\b{word}", text), word


def test_every_term_the_summary_defines_has_a_glossary_entry(tmp_path):
    """The reader rule: a word with a definition in the Summary's bubble is also in the glossary."""
    page, _ = _built(tmp_path)

    def norm(label):
        label = html.unescape(re.sub(r"<[^>]+>", "", label)).replace("\u00ad", "")
        return re.sub(r"[\s-]+", " ", re.sub(r"\d+|\bquestions\b", "", label)).strip().lower()

    glossary = {norm(label) for _, label, _ in build.TERMS}
    tipped = []

    class Tips(HTMLParser):
        """The text of every element with a definition (data-tip), nested markup included."""

        def __init__(self):
            super().__init__()
            self.open = []  # [depth, text parts] per data-tip element being read
            self.depth = 0

        def handle_starttag(self, tag, attrs):
            if tag in VOID:
                return
            self.depth += 1
            if "data-tip" in dict(attrs):
                self.open.append([self.depth, []])

        def handle_startendtag(self, tag, attrs):
            pass  # <path/>, <line/>: no text, no depth

        def handle_endtag(self, tag):
            if self.open and self.open[-1][0] == self.depth:
                tipped.append("".join(self.open.pop()[1]))
            self.depth -= 1

        def handle_data(self, data):
            for _, parts in self.open:
                parts.append(data)

    Tips().feed(_summary(page))
    words = {norm(t) for t in tipped} - {""}
    assert len(words) > 15, words
    assert not sorted(words - glossary), (
        f"defined on the Summary with no glossary entry: {sorted(words - glossary)}"
    )


def test_the_kit_reaches_only_the_parts_moved_onto_it(tmp_path):
    page, _ = _built(tmp_path)
    css = page[page.index("/* report-kit:css ") : page.index("/* /report-kit:css */")]
    assert '<section class="view on rk-kit rk-js" id="summary"' in page
    assert '<section class="view rk-kit" id="decision-map"' in page
    assert '<section class="view rk-kit mfa" id="metricflow"' in page
    assert '<section class="view rk-kit er" id="every-run"' in page
    # the shared chrome moved with the second tab; the tabs still to move keep the report's own look
    moved = ('class="memo rk-kit"', 'class="tabs rk-kit"', 'class="tip rk-kit" id="tip"')
    for part in moved:
        assert part in page, part
    assert '<section class="view rk-kit st" id="setups"' in page
    assert '<section class="view rk-kit rk-js qs-v" id="question-sets"' in page
    # Method & glossary keeps its own layout, its text on the kit's standard (owner, 2026-11-08)
    assert '<section class="view rk-kit mg" id="method"' in page
    assert "a type's heading folds it" not in page and 'class="gl-label">Find a term' in page
    assert not re.search(r"(?m)^\s*(:root[^{&]*|body|html)\s*\{", css), "a kit rule left unscoped"
    assert page.count('<div class="rk-tip" id="rk-tip" hidden></div>') == 1
    # the kit's own scopes: its look on .rk-kit, its scripts on .rk-js (Summary, map filter,
    # Question sets' fold)
    assert "/* report-kit:css " in page and "scope=.rk-kit */" in page
    assert "scope=.rk-js */" in page and '.root = ".rk-js";' in page
    assert len(re.findall(r'class="[^"]*\brk-js\b', page)) == 3


def test_each_tab_names_its_panel_by_the_hash_it_opens(tmp_path):
    page, _ = _built(tmp_path)
    tab = r'class="tab" role="tab" id="tab-([a-z-]+)" href="#([a-z-]+)" aria-controls="([a-z-]+)"'
    tabs = re.findall(tab, page)
    assert len(tabs) == 7
    for name, href, panel in tabs:
        assert name == href == panel
        assert f'id="{panel}" data-view="{panel}" role="tabpanel"' in page


def test_the_decision_map_is_on_the_kit_and_marks_no_best(tmp_path):
    page, _ = _built(tmp_path)
    start = page.index('id="decision-map" data-view')
    panel = page[start : page.index('id="metricflow" data-view')]
    assert 'class="rk-head"' in panel and 'class="rk-switch"' in panel and 'id="map-seg"' in panel
    # no table comparing the sets; the filters fold behind the kit's filter beside the switch
    assert 'id="twin1"' not in panel and "MetricFlow against the" not in panel
    filt = panel[panel.index("<details") : panel.index("</details>")]
    assert "data-rk-filter" in filt and 'id="map-fam"' in filt and 'id="map-role"' in filt
    start = page.index("the Decision map, every set")
    script = page[start : page.index("Observable Plot: shared pieces")]
    # cells on the kit's tint, its sort and wrong-and-sure marks; no best box, no key for the tint
    assert '<span class="ch rk-tint" style="--v:${P(v[0])}"' in script
    assert "dm-ramp" not in page
    assert 'class="rk-sort-mark"' in script and 'data-k="bad"' in script
    plain = re.sub(r"managed[ -]?[bB]est", "", script)
    assert "best" not in plain


def test_the_metricflow_tab_is_on_the_kit_its_charts_on_the_kits_type_and_tokens(tmp_path):
    """The MetricFlow agent tab on the kit (2026-11-07): the kit's heads and set switches, no table
    comparing the question sets, no figure numbers, a focus ring on its marks, and charts on the
    kit's chart theme and tokens with no colour of their own."""
    page, _ = _built(tmp_path)
    start = page.index('id="metricflow" data-view')
    panel = page[page.rindex("<section", 0, start) : page.index('id="every-run" data-view')]
    assert 'class="view rk-kit mfa"' in panel
    assert panel.count('class="rk-head"') == 2 and panel.count('class="rk-section"') == 2
    for view in ("scatter", "slopes"):
        assert 'class="rk-switch" role="group"' in panel and f'data-view="{view}"' in panel
    # no twin table comparing the sets, no "Figure N." (owner: as on the Decision map)
    assert 'id="twin4"' not in panel and "table.tw" not in page and "fignum" not in panel
    assert not re.search(r"Figure \d", panel)
    # the kit's chart theme in both markers; Plot and d3 from the kit's vendor marker
    assert re.search(r"report-kit:css [^*]*plot-theme[^*]*scope=\.rk-kit", page)
    assert re.search(r"report-kit:js [^*]*plot-theme[^*]*scope=\.rk-js", page)
    assert "<!-- report-kit:vendor plot -->" in page and "<!--VENDOR-->" not in page
    assert not (BUILD.parent / "vendor").exists()
    script = page[page.index("Observable Plot: shared pieces") : page.index("Figure 6: unit plate")]
    assert "window.ReportKit.plotTheme(el)" in script
    for fig in ("renderForest", "renderScatter", "renderStrip", "renderSlopes"):
        body = script[script.index(f"function {fig}()") :]
        assert "chartType(el)" in body[: body.index("\n  }\n")], fig
    raw = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(")
    assert not raw.search(script), "a raw colour in the figures' code"
    # the tab's own rules: kit tokens only; a focus ring on every focusable mark, label and glider
    css = page[page.index("/* the MetricFlow agent tab:") :]
    css = css[: css.index("/* the report's own tooltip")]
    assert not raw.search(css), "a raw colour in the tab's rules"
    ring = "#metricflow .glider:focus-visible { outline: 2.5px solid var(--line)"
    assert "#metricflow .plot [tabindex]:focus-visible, " + ring in css
    # no winner marks: the only "best" is the managed best, the bar every setup is paired against
    plain = re.sub(r"managed[ -]?[bB]est", "", script + panel)
    assert "best" not in plain


def test_the_every_run_tab_is_on_the_kit_its_marks_the_kits_status_shapes(tmp_path):
    """The Every run tab on the kit (2026-11-07): the kit's head with the set switch beside it,
    no figure number, a key of defined outcomes, every outcome a kit status shape and token, the
    plate's text columns scaled with the reader's text size, a head that scrolls (not clips)
    sideways, and the kit's focus ring."""
    page, _ = _built(tmp_path)
    start = page.index('id="every-run" data-view')
    panel = page[page.rindex("<section", 0, start) : page.index('id="setups" data-view')]
    assert panel.count('class="rk-head"') == 1 and 'class="rk-switch" role="group"' in panel
    assert 'data-view="plate"' in panel and 'class="seg"' not in panel
    assert 'class="rk-key er-key" id="leg6"' in panel
    assert "fignum" not in panel and not re.search(r"Figure \d", panel)
    # the plate and a hidden live line; no strip, button, caption or how-to line around the chart
    # (owner, 2026-11-07): the question's card and its guide link are in the mark's tooltip
    for name in ("plate-live", "plate-head", "plate-body"):
        assert f'id="{name}"' in panel, name
    assert '<p class="vh" id="plate-live"' in panel
    for gone in (
        'id="pstrip"',
        'id="plate-clear"',
        "Show every question",
        "<figcaption",
        "Click a ",
    ):
        assert gone not in panel, gone
    # outcomes on the kit's status tokens, wherever the kit reaches (the tab and the tooltip)
    tokens = "--o-right: var(--ok); --o-decl: var(--ink); "
    tokens += "--o-wrong: var(--warn); --o-cw: var(--bad)"
    assert ".rk-kit { " + tokens in page
    script = page[page.index("Figure 6: unit plate") : page.index("column heads stay on screen")]
    marks = script[script.index("function outMark(") :]
    marks = marks[: marks.index("\n  }\n")]
    shapes = {"0": ("o-right", "fill"), "1": ("o-decl", "ring"), "2": ("o-wrong", "fill")}
    shapes |= {"4": ("o-cw", "fill")}
    for ch, (paint, kind) in shapes.items():
        assert f'if (ch === "{ch}") return ["{paint}", "{kind}"' in marks, ch
    # unclear is folded into wrong (owner): no mark, no key entry, no count of its own on the page
    assert 'ch === "3"' not in marks and '"unclear"' not in script
    assert "circ(cx, cy, s / 2)" in marks  # right and declined are round, as the kit's ok and no
    assert "function swatch(ch) { const [c, k, d] = outMark(ch" in script
    assert "outMark(r.units[" in script
    assert "function qCard(ci)" in script and "Open in the question guide" in script
    assert "PLATE_IDLE" not in script and "reserveStrip" not in script
    # the head: one word per column, what a column holds in its tooltip, no subtitles
    assert "<small>" not in script and "data-note=" in script
    # legible marks: never under 7 px a question; text columns grow with the root size
    assert "let pitch = 9, L = lay(pitch);" in script
    assert "while (pitch > 7 && LW + L.UW + 16 + IW + CWW > avail)" in script
    assert "getComputedStyle(document.documentElement).fontSize" in script
    assert "function layoutHead()" in script
    raw = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\(")
    assert not raw.search(script), "a raw colour in the plate's code"
    css = page[page.index("/* run outcomes on the kit's status tokens") :]
    css = css[: css.index("/* the report's own tooltip")]
    assert not raw.search(css), "a raw colour in the tab's rules"
    assert "#every-run .plate-head { overflow-x: auto;" in css
    assert "#every-run .plate [tabindex]:focus-visible" in css
    assert "outline: 2.5px solid var(--line)" in css
    plain = re.sub(r"managed[ -]?[bB]est", "", script + panel)
    assert "best" not in plain


def test_one_type_standard_and_no_how_to_text_on_the_page(tmp_path):
    """Owner, 2026-11-07: one standard for every tab (the kit's family, every word in full ink,
    words at 1rem), only the last-updated time under the title, column heads without subtitles,
    and no text that explains how to use a chart."""
    page, _ = _built(tmp_path)
    css = page[: page.index("</style>")]
    assert "STIX" not in page and "Barlow" not in page
    assert "--ink-2: var(--ink); --ink-3: var(--ink);" in css
    assert '--serif: "Atkinson Hyperlegible Next"' in css and "--label: var(--serif);" in css
    assert "font-size: 16px; line-height: 1.45;" in css
    # the header: one line, when the numbers were written
    assert '<p class="updated" id="updated"></p>' in page and "byline" not in page
    assert "living memo" not in page and "Evidence as of" not in page
    assert 'Updated <time datetime="${esc(D.written)}">' in page
    # the Decision map: one-word heads (notes in their tooltips), words at 1rem, no how-to line
    assert "min-width: 64rem; font: 400 var(--t-word)/1.4 var(--sans);" in page
    assert 'class="dm-note"' not in page and "A column's head sorts" not in page
    assert "What this setup is" not in page and '<p class="vh" id="map-live"' in page
    assert "Hover a line or a label" not in page
    assert 'tSec("In this column"' in page
