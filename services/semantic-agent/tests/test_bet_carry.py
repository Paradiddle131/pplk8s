"""The carry of a superseded set's runs into its new version (RULE.md § Set versions, #378)."""

import json

import yaml

from semantic_agent import bet_carry, bet_eval
from semantic_agent.bet_eval import SetFiles

HEDGES = ["roughly"]


def _set(path, cases, supersedes=None):
    spec = {"hedges": HEDGES, "groups": {c["id"]: ["covered"] for c in cases}, "questions": cases}
    if supersedes:
        spec["supersedes"] = supersedes
    path.write_text(yaml.safe_dump(spec, sort_keys=False))
    return path


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _run(case, run, model="m", outcome="right"):
    return {"model": model, "run": run, "case": case, "outcome": outcome, "turns": []}


def _sets(tmp_path, monkeypatch):
    same = {"id": "same", "question": "Revenue on 1 October?", "expected_sql": "select 1"}
    changed = {"id": "changed", "question": "Orders on 1 October?", "expected_sql": "select 2"}
    v1 = _set(tmp_path / "v1.yaml", [same, changed])
    edited = {**changed, "expected_sql": "select 3"}
    new = {"id": "new", "question": "Median order?", "expected_sql": "select 4"}
    v2 = _set(tmp_path / "v2.yaml", [same, edited, new], supersedes="v1")
    sets = {
        "v1": SetFiles("v1", v1, "eval-v1-", "v1"),
        "v2": SetFiles("v2", v2, "eval-v1-v2-", "v2"),
    }
    monkeypatch.setattr(bet_carry, "SETS", sets)


def test_a_carry_copies_unchanged_cases_with_provenance_and_refuses_changed_ones(
    tmp_path, monkeypatch
):
    _sets(tmp_path, monkeypatch)
    _write(tmp_path / "eval-v1-native-kc.jsonl", [_run("same", 1), _run("changed", 1)])
    _write(tmp_path / "eval-v1-local.jsonl", [{**_run("same", 1), "arm": "baseline"}])
    # A log of the new set already there, under a prefix that extends the old one's: never a source.
    _write(tmp_path / "eval-v1-v2-native-kc.jsonl", [_run("new", 1)])
    verdict = {"judge": "j", "arm": "native-kc", "model": "m", "run": 1, "turn": 0}
    verdict |= {"answer": "abc", "n": 1, "verdict": "right", "set": "v1"}
    _write(
        tmp_path / "judge.jsonl",
        [{**verdict, "case": "same"}, {**verdict, "case": "changed"}],
    )

    result = bet_carry.carry("v2", tmp_path)

    assert result.source == "v1" and result.carried == ["same"] and result.refused == ["changed"]
    assert result.copied == {"eval-v1-v2-local.jsonl": 1, "eval-v1-v2-native-kc.jsonl": 1}
    rows = bet_eval.read_log(tmp_path / "eval-v1-v2-native-kc.jsonl")
    assert [(r["case"], r.get("carried_from")) for r in rows] == [("new", None), ("same", "v1")]
    hashes = bet_carry.case_hashes(tmp_path / "v2.yaml")
    assert (
        rows[1]["case_hash"]
        == hashes["same"]
        == bet_carry.case_hashes(tmp_path / "v1.yaml")["same"]
    )
    assert hashes["changed"] != bet_carry.case_hashes(tmp_path / "v1.yaml")["changed"]
    # The old set's logs are untouched; its verdict on the carried case becomes the new set's too.
    assert len(bet_eval.read_log(tmp_path / "eval-v1-native-kc.jsonl")) == 2
    judged = bet_eval.read_log(tmp_path / "judge.jsonl")
    assert [(r["case"], r["set"]) for r in judged] == [
        ("same", "v1"),
        ("changed", "v1"),
        ("same", "v2"),
    ]
    assert bet_eval.read_verdicts(tmp_path / "judge.jsonl", "j", "v2") == {
        ("native-kc", "m", "same", 1, 0, "abc"): ["right", None]
    }
    assert bet_carry.verify("v2", tmp_path) == []


def test_a_second_carry_copies_only_what_the_old_set_gained(tmp_path, monkeypatch):
    _sets(tmp_path, monkeypatch)
    _write(tmp_path / "eval-v1-native-kc.jsonl", [_run("same", 1)])
    bet_carry.carry("v2", tmp_path)
    assert bet_carry.carry("v2", tmp_path).copied == {}
    with (tmp_path / "eval-v1-native-kc.jsonl").open("a") as log:
        log.write(json.dumps(_run("same", 2)) + "\n")
    assert bet_carry.carry("v2", tmp_path).copied == {"eval-v1-v2-native-kc.jsonl": 1}
    runs = [r["run"] for r in bet_eval.read_log(tmp_path / "eval-v1-v2-native-kc.jsonl")]
    assert runs == [1, 2]


def test_a_carried_row_whose_case_changed_since_is_flagged(tmp_path, monkeypatch):
    _sets(tmp_path, monkeypatch)
    _write(tmp_path / "eval-v1-native-kc.jsonl", [_run("same", 1)])
    bet_carry.carry("v2", tmp_path)
    log = tmp_path / "eval-v1-v2-native-kc.jsonl"
    row = {**bet_eval.read_log(log)[0], "case_hash": "0" * 64}
    _write(log, [row])
    assert bet_carry.verify("v2", tmp_path) == ["eval-v1-v2-native-kc.jsonl: same run 1"]


def test_the_cli_exits_1_on_a_refused_case_and_writes_nothing_on_a_dry_run(
    tmp_path, monkeypatch, capsys
):
    _sets(tmp_path, monkeypatch)
    _write(tmp_path / "eval-v1-native-kc.jsonl", [_run("same", 1)])
    monkeypatch.setattr(bet_carry, "RESEARCH", tmp_path)
    monkeypatch.setattr(
        bet_carry, "carry", lambda t, dry_run=False, f=bet_carry.carry: f(t, tmp_path, dry_run)
    )
    assert bet_carry.main(["--to", "v2", "--dry-run"]) == 1
    assert not (tmp_path / "eval-v1-v2-native-kc.jsonl").exists()
    assert "refused (scoring inputs differ): changed" in capsys.readouterr().out


def test_hard_v2_carries_every_v1_case_unchanged():
    # The frozen files themselves: v2 holds v1's 43 cases with equal hashes, so none is refused.
    v1 = bet_carry.case_hashes(bet_eval.SETS["hard"].questions)
    v2 = bet_carry.case_hashes(bet_eval.SETS["hard-v2"].questions)
    assert len(v1) == 43 and all(v2[case] == digest for case, digest in v1.items())
