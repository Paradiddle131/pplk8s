from datetime import UTC, datetime, timedelta

from el_factory.model import Interval
from el_factory.sources.partner_outreach import (
    MAX_REPLY_LAG_DAYS,
    PARTNERS,
    build_contacts,
    build_messages,
    build_partners,
    build_replies,
)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def ts(row: dict[str, object], column: str) -> datetime:
    return datetime.fromisoformat(str(row[column]))


DAY_ONE = Interval(utc(2026, 10, 1), utc(2026, 10, 2))
TWO_DAYS = Interval(utc(2026, 10, 1), utc(2026, 10, 3))
AUTUMN = Interval(utc(2026, 9, 1), utc(2026, 12, 1))


def test_partners_are_fixed():
    assert [p["partner_id"] for p in build_partners()] == [p[0] for p in PARTNERS]


def test_contacts_are_a_snapshot_at_the_interval_end_with_synthetic_details():
    september = build_contacts(Interval(utc(2026, 9, 1), utc(2026, 9, 2)))
    december = build_contacts(Interval(utc(2026, 11, 30), utc(2026, 12, 1)))

    assert [c["contact_id"] for c in september] == [c["contact_id"] for c in december]
    assert len({c["contact_id"] for c in december}) == len(december) == 3 * len(PARTNERS)
    assert all(str(c["email"]).endswith(".example") for c in december)
    assert all(str(c["phone"]).startswith("+1-555-01") for c in december)
    # Some never consented, some opted out by December, and nobody had opted out on day one.
    assert any(not c["consent"] for c in december)
    assert any(c["opted_out_ts"] for c in december)
    assert not any(c["opted_out_ts"] for c in september)


def test_an_opt_out_shows_from_the_interval_it_happens_in_and_moves_updated_ts():
    december = build_contacts(Interval(utc(2026, 11, 30), utc(2026, 12, 1)))
    opted = next(c for c in december if c["opted_out_ts"])
    at = ts(opted, "opted_out_ts")
    before = Interval(at - timedelta(days=1), at)
    after = Interval(at, at + timedelta(days=1))

    row_before = next(c for c in build_contacts(before) if c["contact_id"] == opted["contact_id"])
    row_after = next(c for c in build_contacts(after) if c["contact_id"] == opted["contact_id"])
    assert row_before["opted_out_ts"] is None
    assert ts(row_before, "updated_ts") < at
    assert ts(row_after, "opted_out_ts") == at == ts(row_after, "updated_ts")


def test_messages_go_only_to_contacts_who_consented_and_had_not_opted_out():
    contacts = {c["contact_id"]: c for c in build_contacts(AUTUMN)}
    messages = build_messages(AUTUMN)

    assert messages
    for message in messages:
        contact = contacts[message["contact_id"]]
        assert contact["consent"]
        assert not contact["opted_out_ts"] or ts(contact, "opted_out_ts") > ts(message, "sent_ts")
        assert message["channel"] == contact["preferred_channel"]


def test_messages_are_extracted_by_sent_time_and_split_intervals_agree():
    rows = build_messages(DAY_ONE)

    assert rows == build_messages(DAY_ONE)
    assert all(DAY_ONE.start <= ts(r, "sent_ts") < DAY_ONE.end for r in rows)
    halves = build_messages(Interval(utc(2026, 10, 1), utc(2026, 10, 2))) + build_messages(
        Interval(utc(2026, 10, 2), utc(2026, 10, 3))
    )
    assert halves == build_messages(TWO_DAYS)


def test_replies_follow_their_message_within_the_lag_and_land_once():
    messages = {m["message_id"]: m for m in build_messages(AUTUMN)}
    replies = build_replies(Interval(utc(2026, 9, 5), utc(2026, 11, 25)))

    assert replies
    assert len({r["reply_id"] for r in replies}) == len(replies)
    for reply in replies:
        lag = ts(reply, "replied_ts") - ts(messages[reply["message_id"]], "sent_ts")
        assert timedelta(0) < lag <= timedelta(days=MAX_REPLY_LAG_DAYS + 1)
    rate = len(replies) / sum(
        utc(2026, 9, 5) <= ts(m, "sent_ts") < utc(2026, 11, 21) for m in messages.values()
    )
    assert 0.15 < rate < 0.45


def test_replies_are_extracted_by_reply_time_and_split_intervals_agree():
    halves = build_replies(Interval(utc(2026, 10, 1), utc(2026, 10, 2))) + build_replies(
        Interval(utc(2026, 10, 2), utc(2026, 10, 3))
    )

    assert halves == build_replies(TWO_DAYS)
    assert all(TWO_DAYS.start <= ts(r, "replied_ts") < TWO_DAYS.end for r in halves)
