from datetime import UTC, datetime

from el_factory.model import Interval
from el_factory.sources.recruitment import CLOSED_STAGES, STAGES, build_applications


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def ts(row: dict[str, object], column: str) -> datetime:
    return datetime.fromisoformat(str(row[column]))


def day(*args: int) -> Interval:
    start = utc(*args)
    return Interval(start, start.replace(day=start.day + 1))


def by_id(rows: list[dict[str, object]]) -> dict[object, dict[str, object]]:
    return {row["candidate_id"]: row for row in rows}


def test_every_candidate_who_applied_by_the_interval_end_is_extracted_once():
    rows = build_applications(day(2026, 10, 1))

    assert rows == build_applications(day(2026, 10, 1))
    assert len(by_id(rows)) == len(rows) > 30
    assert all(ts(r, "applied_ts") < utc(2026, 10, 2) for r in rows)
    assert all(ts(r, "applied_ts") <= ts(r, "stage_ts") < utc(2026, 10, 2) for r in rows)
    assert {r["stage"] for r in rows} <= {*STAGES, "rejected"}


def test_the_source_keeps_only_the_current_stage_so_a_later_extract_overwrites_it():
    early = by_id(build_applications(day(2026, 9, 10)))
    late = by_id(build_applications(day(2026, 11, 1)))

    assert set(early) <= set(late)
    moved = [cid for cid in early if early[cid]["stage"] != late[cid]["stage"]]
    assert moved
    for cid in moved:
        assert ts(late[cid], "stage_ts") > ts(early[cid], "stage_ts")
        assert early[cid]["stage"] not in CLOSED_STAGES
        # Only the stage moves: role, channel and the application's time stay.
        assert {k: v for k, v in early[cid].items() if not k.startswith("stage")} == {
            k: v for k, v in late[cid].items() if not k.startswith("stage")
        }


def test_stages_only_move_forward_and_a_closed_stage_is_final():
    order = {stage: rank for rank, stage in enumerate(STAGES)}
    snapshots = [by_id(build_applications(day(2026, 9, d))) for d in range(1, 30)]

    for before, after in zip(snapshots, snapshots[1:], strict=False):
        for cid, row in before.items():
            now = after[cid]
            if row["stage"] in CLOSED_STAGES:
                assert now == row
            elif now["stage"] != "rejected":
                assert order[str(now["stage"])] >= order[str(row["stage"])]


def test_by_november_candidates_were_hired_and_rejected():
    stages = [r["stage"] for r in build_applications(day(2026, 11, 1))]

    assert stages.count("hired") >= 5
    assert stages.count("rejected") >= 5
