"""The Approaches page: every scored setup has a plain-language approach, and its figures add up."""

import html
import importlib.util
import json
import re
from pathlib import Path

BUILD = Path(__file__).resolve().parents[3] / "docs/research/semantic-bet/brief/build.py"
spec = importlib.util.spec_from_file_location("bet_brief_build", BUILD)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

RESULTS = BUILD.parents[1] / "results.json"


def test_per100_sums_to_100_and_counts_unclear_as_wrong():
    counts = build.per100({"right": 206, "unclear": 13, "confident-wrong": 9}, 228)
    assert sum(counts.values()) == 100
    assert counts == {"right": 90, "declined": 0, "wrong": 6, "sure_wrong": 4}


def test_every_scored_setup_on_the_page_belongs_to_exactly_one_approach():
    arms = {a["arm"] for a in json.loads(RESULTS.read_text())["arms"]} - build.LEFT_OUT
    pooled = [n for _, _, names, _ in build.APPROACHES for n in names]
    assert len(pooled) == len(set(pooled))
    assert arms <= set(pooled)


def test_the_approach_shown_is_the_pooled_setup_with_most_answers_right():
    arms = [
        {
            "set": "frozen",
            "arm": "a",
            "cases": 2,
            "of_cases": 2,
            "runs": 4,
            "outcomes": {"right": 2},
        },
        {
            "set": "frozen",
            "arm": "b",
            "cases": 2,
            "of_cases": 2,
            "runs": 4,
            "outcomes": {"right": 3},
        },
        {
            "set": "frozen",
            "arm": "c",
            "cases": 1,
            "of_cases": 2,
            "runs": 1,
            "outcomes": {"right": 1},
        },
    ]
    assert build.stands_for(arms, ["a", "b", "c"], "frozen")["arm"] == "b"
    assert build.stands_for(arms, ["a"], "hard") is None


def test_the_page_runs_from_most_native_to_most_custom_and_recommends_nothing():
    page = build.build(RESULTS)
    assert "@@" not in page
    names = [name for name, *_ in build.APPROACHES]
    assert names[0].startswith("Google's data agent") and names[-1].startswith("Our agent")
    positions = [page.index(html.escape(n)) for n in names]
    assert positions == sorted(positions)
    for word in ("Recommended", "Verdict", "best", "winner"):
        assert word not in page
    for setname, *_ in build.SETS:
        assert f'data-set="{setname}"' in page


def test_takeaways_quote_the_figures_their_pictures_draw():
    items = {t["key"]: t for t in build.takeaways(json.loads(RESULTS.read_text()))}
    assert {"setup", "rules", "definitions", "harness"} <= set(items)
    for r in items["setup"]["ranges"]:
        assert f"{r['lo']} to {r['hi']}" in items["setup"]["body"]
    assert all(str(p["right"]) in items["harness"]["body"] for p in items["harness"]["programs"])
    names = [name for name, *_ in build.APPROACHES]
    assert (
        items["setup"]["ranges"][0]["lo_name"] in names
        and items["setup"]["ranges"][0]["hi_name"] in names
    )


def test_a_covered_score_under_100_explains_its_unclear_answers_on_hover():
    data = json.loads(RESULTS.read_text())
    rules = next(
        t for t in build.takeaways(data, build.scored_runs(RESULTS, data)) if t["key"] == "rules"
    )
    # A note only explains a gap made of unjudged answers; with every answer judged (#428) a score
    # under 100 may carry none, but a note never sits on a full score.
    for m in rules["models"]:
        assert not m["covered_note"] or m["covered"] < 100
    page = build.build(RESULTS)
    assert all(
        f'data-tip="{html.escape(m["covered_note"])}"' in page
        for m in rules["models"]
        if m["covered_note"]
    )


def test_the_kinds_takeaway_draws_each_rows_setup_by_kind_and_names_no_winner():
    data = json.loads(RESULTS.read_text())
    kinds = next(t for t in build.takeaways(data) if t["key"] == "kinds")
    assert [s["set"] for s in kinds["sets"]] == [s for s, *_ in build.SETS]
    for s in kinds["sets"]:
        assert [r["name"] for r in s["rows"]] == [name for name, *_ in build.APPROACHES]
        for r, (_, _, names, _) in zip(s["rows"], build.APPROACHES, strict=True):
            arm = build.stands_for(data["arms"], names, s["set"])
            for k, *_ in build.KINDS:
                # An approach with no complete setup on the set (a pass under way) has no cells.
                expected = round(100 * arm["groups"][k][0]) if arm and k in arm["groups"] else None
                assert r["v"][k] == expected
        for k, *_ in build.KINDS:
            lo, hi = s["ranges"][k]
            assert f"{lo} to {hi}" in s["body"]
        words = (s["headline"] + " " + s["body"]).lower()
        for ranking in ("best", "winner", "leads", "top", "highest", "most accurate", "recommend"):
            assert ranking not in words, ranking
    page = build.build(RESULTS)
    grids = page.count('class="rk-pic ap-kinds"')
    assert grids == len(build.SETS)
    # every cell on the kit's tint (its ground follows its own number) and no emphasis on any cell
    grid = page[page.index('class="rk-pic ap-kinds"') :]
    grid = grid[: grid.index("</table>")]
    tint = r'(?:<span class="rk-tint" style="--v:(\d+)">)?'
    cell = r'<td class="rk-num" data-v="(-?\d+)">' + tint + r"<b>([^<]+)</b>"
    cells = re.findall(cell, grid)
    assert len(cells) == len(build.APPROACHES) * len(build.KINDS)
    for v, tint, shown in cells:
        assert (tint, shown) == ((v, v) if v != "-1" else ("", "–"))
    assert "data-k=" not in grid and "<strong" not in grid and "<mark" not in grid
    # each kind's head sorts the rows (the kit's two-state sort, one for both sets)
    assert '<table data-rk-sort="toggle" data-rk-sort-group="kinds">' in grid
    assert grid.count('class="rk-num" data-sort="number"><button type="button"') == len(build.KINDS)


def test_the_page_is_built_on_the_vendored_kit():
    page = build.build(RESULTS)
    assert "/* /report-kit:css */" in page and "/* /report-kit:js */" in page
    assert "window.ReportKit" in page
    assert 'data-rk-switch="set"' in page and page.count(
        '<table class="rk-table ap-table" data-rk-sort'
    ) == len(build.SETS)
