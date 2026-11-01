from collections import Counter
from datetime import UTC, datetime, timedelta

from el_factory.model import Interval
from el_factory.sources.customer_actions import (
    ACTION_TYPES,
    MAX_LATENESS,
    build_customer_actions,
)
from el_factory.sources.synthetic import CUSTOMER_COUNT


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def ts(row: dict[str, object], column: str) -> datetime:
    return datetime.fromisoformat(str(row[column]))


DAY_ONE = Interval(utc(2026, 10, 1), utc(2026, 10, 2))
TWO_DAYS = Interval(utc(2026, 10, 1), utc(2026, 10, 3))
OCTOBER = Interval(utc(2026, 10, 1), utc(2026, 11, 1))


def test_actions_are_extracted_by_the_time_they_were_received():
    rows = build_customer_actions(DAY_ONE)

    assert rows
    assert rows == build_customer_actions(DAY_ONE)
    assert all(DAY_ONE.start <= ts(row, "received_ts") < DAY_ONE.end for row in rows)
    assert [(r["received_ts"], r["event_id"]) for r in rows] == sorted(
        (r["received_ts"], r["event_id"]) for r in rows
    )


def test_splitting_an_interval_yields_the_same_rows_as_the_whole():
    split = [
        Interval(utc(2026, 10, 1), utc(2026, 10, 2)),
        Interval(utc(2026, 10, 2), utc(2026, 10, 3)),
    ]

    assert sorted(sum((build_customer_actions(i) for i in split), []), key=str) == sorted(
        build_customer_actions(TWO_DAYS), key=str
    )


def test_some_actions_arrive_a_day_late_and_none_later_than_the_maximum():
    rows = build_customer_actions(OCTOBER)
    lateness = [ts(r, "received_ts") - ts(r, "event_ts") for r in rows]

    assert all(timedelta(0) <= late <= MAX_LATENESS for late in lateness)
    late = [r for r in rows if ts(r, "received_ts").date() > ts(r, "event_ts").date()]
    assert 0.03 < len(late) / len(rows) < 0.2
    # A late action lands in the next day's extract, behind the day it happened.
    assert any(ts(r, "event_ts") < DAY_ONE.start for r in build_customer_actions(DAY_ONE))


def test_each_event_is_extracted_once():
    rows = build_customer_actions(OCTOBER)

    assert len({r["event_id"] for r in rows}) == len(rows)


def test_sessions_walk_the_funnel_in_order_and_take_each_step_once():
    # A session's steps can be received in different extracts, so look at sessions well inside.
    rows = [
        r
        for r in build_customer_actions(OCTOBER)
        if r["session_id"] is None or "20261003" <= str(r["session_id"])[2:10] <= "20261028"
    ]
    order = {"page_view": 0, "add_to_cart": 1, "checkout": 2}
    sessions: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        if row["session_id"] is not None:
            assert row["channel"] == "site"
            sessions.setdefault(str(row["session_id"]), []).append(row)
        else:
            assert row["channel"] == "crm"
    steps = Counter()
    for actions in sessions.values():
        actions.sort(key=lambda r: ts(r, "event_ts"))
        types = [str(r["action_type"]) for r in actions]
        assert len(types) == len(set(types))
        assert [order[t] for t in types] == list(range(len(types)))
        assert len({r["customer_id"] for r in actions}) == 1
        steps.update(types)
    assert steps["page_view"] > steps["add_to_cart"] > steps["checkout"] > 0


def test_every_action_names_a_known_customer_and_type():
    rows = build_customer_actions(OCTOBER)

    assert {r["action_type"] for r in rows} == set(ACTION_TYPES)
    assert all(1 <= int(str(r["customer_id"])) <= CUSTOMER_COUNT for r in rows)
