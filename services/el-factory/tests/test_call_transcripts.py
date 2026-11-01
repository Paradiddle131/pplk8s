from collections import Counter
from datetime import UTC, datetime

from el_factory.model import Interval
from el_factory.sources.call_transcripts import (
    NEXT_STEPS,
    OBJECTIONS,
    SENTIMENTS,
    TOPICS,
    build_call_transcripts,
    call_labels,
)
from el_factory.sources.synthetic import CUSTOMER_COUNT


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


DAY_ONE = Interval(utc(2026, 10, 1), utc(2026, 10, 2))
TWO_DAYS = Interval(utc(2026, 10, 1), utc(2026, 10, 3))
OCTOBER = Interval(utc(2026, 10, 1), utc(2026, 11, 1))


def test_calls_are_extracted_by_call_time_in_a_stable_order():
    rows = build_call_transcripts(DAY_ONE)

    assert rows
    assert rows == build_call_transcripts(DAY_ONE)
    times = [datetime.fromisoformat(str(r["call_ts"])) for r in rows]
    assert all(DAY_ONE.start <= at < DAY_ONE.end for at in times)
    assert [(r["call_ts"], r["transcript_id"]) for r in rows] == sorted(
        (r["call_ts"], r["transcript_id"]) for r in rows
    )


def test_splitting_an_interval_yields_the_same_rows_as_the_whole():
    split = [
        Interval(utc(2026, 10, 1), utc(2026, 10, 2)),
        Interval(utc(2026, 10, 2), utc(2026, 10, 3)),
    ]

    assert sum((build_call_transcripts(i) for i in split), []) == build_call_transcripts(TWO_DAYS)


def test_landed_rows_carry_text_and_never_the_labels():
    rows = build_call_transcripts(OCTOBER)

    assert len({r["transcript_id"] for r in rows}) == len(rows)
    assert {key for row in rows for key in row} == {
        "transcript_id",
        "customer_id",
        "call_ts",
        "duration_seconds",
        "transcript",
    }
    assert all(1 <= int(str(r["customer_id"])) <= CUSTOMER_COUNT for r in rows)
    assert all(str(r["transcript"]).startswith("Agent: ") for r in rows)


def test_every_call_has_true_labels_and_october_uses_every_value():
    rows = build_call_transcripts(OCTOBER)
    labels = call_labels(OCTOBER)

    assert set(labels) == {str(r["transcript_id"]) for r in rows}
    assert {lab.topic for lab in labels.values()} == set(TOPICS)
    assert {lab.objection for lab in labels.values()} == set(OBJECTIONS)
    assert {lab.sentiment for lab in labels.values()} == set(SENTIMENTS)
    assert {lab.next_step for lab in labels.values()} == set(NEXT_STEPS)


def test_the_text_says_what_its_labels_say():
    rows = {str(r["transcript_id"]): str(r["transcript"]) for r in build_call_transcripts(OCTOBER)}
    labels = call_labels(OCTOBER)

    objections = Counter(lab.objection for lab in labels.values())
    assert objections["none"] > objections["competitor"]
    for transcript_id, lab in labels.items():
        text = rows[transcript_id]
        # A call without an objection has no line the agent answers with "I understand".
        assert ("I understand, let me see" in text) == (lab.objection != "none")
        if lab.next_step == "send_quote":
            assert "written quote" in text
        if lab.next_step == "escalate":
            assert "team lead" in text
