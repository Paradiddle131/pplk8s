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


def test_the_page_shows_v1_until_the_owners_go_and_keeps_v2_in_the_appendix():
    present, appendix = build.shown_sets(["frozen", "hard", "hard-v2"], {})
    assert present == ["frozen", "hard"]
    assert appendix == [("hard-v2", "Extended hard set")]


def test_showing_v2_puts_v1_in_the_appendix_under_its_plain_name():
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


def test_the_appendix_lists_each_hidden_sets_setups_from_the_results():
    arm = {"set": "hard-v2", "arm": "native-bare", "model": "google-data-agent", "cases": 43}
    arm |= {"of_cases": 58, "accuracy": [0.65, 0.5, 0.8], "confident_wrong": [0.28, 0.2, 0.4]}
    arm |= {"groups": {"composable": [0.67, 20]}}
    html = build.appendix_html({"arms": [arm]}, [("hard-v2", "Extended hard set")])
    assert 'id="other-set-versions"' in html and "43 of 58" in html and "65%" in html
    assert build.appendix_html({"arms": [arm]}, []) == ""


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
        assert set(spec) == {"label", "shown", "appendix", "groups", "questions"}
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


def test_the_appendix_goes_to_its_own_part_or_after_the_sections(tmp_path):
    out = tmp_path / "index.html"
    build.build(str(RESULTS), str(RESULTS.parent), str(EVALS), str(out))
    page = out.read_text(encoding="utf-8")
    at = page.index('id="other-set-versions"')
    assert page.index('id="view-question-sets"') < at < page.index('id="view-method"')
    setups, setup_map = page.index('id="view-setups"'), page.index('id="setup-map"')
    assert setups < setup_map < page.index('id="view-question-sets"')
    bare = tmp_path / "bare.html"
    bare.write_text(
        "<script>const D = /*__DATA__*/null;</script><main><!--SECTIONS--></main><!--VENDOR-->",
        encoding="utf-8",
    )
    build.build(str(RESULTS), str(RESULTS.parent), str(EVALS), str(out), template=str(bare))
    page = out.read_text(encoding="utf-8")
    assert (
        page.index('id="setup-map"') < page.index('id="other-set-versions"') < page.index("</main>")
    )


def _built(tmp_path):
    out = tmp_path / "index.html"
    build.build(str(RESULTS), str(RESULTS.parent), str(EVALS), str(out))
    page = out.read_text(encoding="utf-8")
    payload = re.search(r"const D = (\{.*?\});\nwindow\.REPORT", page, re.S).group(1)
    return page, json.loads(payload.replace("<\\/", "</"))


def test_the_question_section_sits_in_its_part_before_the_appendix(tmp_path):
    page, _ = _built(tmp_path)
    at = page.index('id="question-guide"')
    assert page.index('id="view-question-sets"') < at < page.index('id="other-set-versions"')
    assert at > page.index('id="view-setups"') and page.index(
        'id="other-set-versions"'
    ) < page.index('id="view-method"')


def test_each_question_set_has_its_anchor_in_the_section(tmp_path):
    page, data = _built(tmp_path)
    section = page[page.index('id="question-guide"') : page.index('id="other-set-versions"')]
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    for st in results["sets"]:
        assert f'id="qs-{st}"' in section, st
    assert set(data["questionGuide"]["setLabel"]) == set(results["sets"])


def test_no_retired_question_reaches_the_section_or_its_data(tmp_path):
    page, data = _built(tmp_path)
    section = page[page.index('id="question-guide"') : page.index('id="other-set-versions"')]
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    scored = {c for spec in results["sets"].values() for c in spec.get("cases") or []}
    retired = {c for spec in results["sets"].values() for c in spec.get("retired") or []} - scored
    assert retired
    guide = data["questionGuide"]
    assert set(guide["q"]) == scored
    shown = json.dumps(guide)
    assert not [c for c in retired if c in section or f'"{c}"' in shown]
    assert all(set(c["ids"]) <= scored for c in guide["cats"])


def test_the_see_all_buttons_exist_one_per_category_and_stay_hidden(tmp_path):
    page, data = _built(tmp_path)
    buttons = re.findall(r'<button[^>]*class="qs-seeall"[^>]*>', page)
    cats = data["questionGuide"]["cats"]
    assert len(buttons) == len(cats) > 0
    assert all(re.search(r"\shidden(\s|>|$)", b) for b in buttons)
    assert {re.search(r'data-category="([^"]+)"', b).group(1) for b in buttons} == {
        c["key"] for c in cats
    }


def test_every_list_title_and_category_of_the_section_is_a_typed_glossary_term(tmp_path):
    _, data = _built(tmp_path)
    terms = {k for k, _, _ in build.TERMS}
    guide = data["questionGuide"]
    keys = [x["key"] for x in guide["lists"]] + [c["key"] for c in guide["cats"]]
    keys += ["obvious-sql", "groups", "declined", "unclear", "confident-wrong"] + [
        build.term_key(s) for s in guide["setLabel"]
    ]
    assert not [k for k in keys if k not in terms or k not in build.TERM_TYPE]
