"""A deterministic synthetic source of sales and support call transcripts (semantic/PLAN.md SL-8,
SL-18): the text a contact centre's recorder lands, and nothing a model derives from it.

Each call's signals (topic, objection, sentiment, next step) are picked first and its text is
written from them, so the generator knows every call's true labels: ``call_labels`` gives them for
the golden set, while the landed rows carry only the text. Labelling happens in dbt
(docs/text-signals.md). Each day is generated from its own seed, so a call never depends on the
interval that requested it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from el_factory.model import Interval, Page, Table
from el_factory.sources.base import Entity
from el_factory.sources.paging import paginate
from el_factory.sources.synthetic import CUSTOMER_COUNT

SOURCE = "synthetic"
TOPICS = ("delivery", "pricing", "returns", "product")
OBJECTIONS = ("none", "price", "timing", "competitor")
SENTIMENTS = ("positive", "neutral", "negative")
NEXT_STEPS = ("none", "follow_up_call", "send_quote", "escalate")

CALL_TRANSCRIPTS_TABLE = Table(
    "synthetic_call_transcripts",
    (
        ("transcript_id", "text"),
        ("customer_id", "integer"),
        ("call_ts", "timestamptz"),
        ("duration_seconds", "integer"),
        ("transcript", "text"),
    ),
)

# The customer's opening line per topic; the agent's reply keeps to the same topic.
_OPENINGS = {
    "delivery": (
        "My order still has not arrived and the tracking page has not moved since Monday.",
        "I wanted to check when my parcel will be delivered, the courier missed me yesterday.",
        "Can you tell me where my delivery is? It was due last week.",
    ),
    "pricing": (
        "I am looking at the annual plan and want to know what it costs for a team of twelve.",
        "Can you walk me through the price list? I need a figure for our budget meeting.",
        "I saw the new pricing on your site and want to know what we would pay next year.",
    ),
    "returns": (
        "I would like to send back the chair I bought, it does not fit the room.",
        "How do I return an item? The jacket I ordered is the wrong size.",
        "I want to return the blender, it stopped working after two days.",
    ),
    "product": (
        "Does the standing desk come with a cable tray, or is that sold separately?",
        "I have a question about the coffee machine: can it make two cups at once?",
        "Which of your laptops has the longest battery life?",
    ),
}
_AGENT_REPLIES = {
    "delivery": "Let me look up the shipment. I can see it left the depot this morning.",
    "pricing": "Of course. The annual plan is billed per seat, and larger teams get a volume rate.",
    "returns": "I can help with that. Returns are free within thirty days of delivery.",
    "product": "Good question. Let me pull up the product sheet for you.",
}
_OBJECTION_LINES = {
    "none": (),
    "price": (
        "Honestly that is more than we wanted to spend, it feels too expensive.",
        "That price is too high for us at the moment.",
    ),
    "timing": (
        "We are not ready to decide this quarter, maybe after the new year.",
        "The timing is bad, we are in the middle of a reorganisation.",
    ),
    "competitor": (
        "Another supplier offered us something similar, so I am comparing the two.",
        "We already use a competitor for this and they are cheaper.",
    ),
}
_SENTIMENT_LINES = {
    "positive": (
        "Thank you, that is really helpful, I appreciate it.",
        "Great, you have been very kind, thanks a lot.",
    ),
    "neutral": (
        "Okay, noted.",
        "Alright, I understand.",
    ),
    "negative": (
        "This is frustrating, I have called three times already and nothing changes.",
        "I am not happy with how this has been handled at all.",
    ),
}
# (agent, customer): how the call ends.
_NEXT_STEP_LINES = {
    "none": ("Is there anything else I can help with?", "No, that is all. Goodbye."),
    "follow_up_call": ("I will call you back on Thursday with an answer.", "Fine, talk then."),
    "send_quote": ("I will email you a written quote today.", "Please do, I will look at it."),
    "escalate": ("I am passing this to my team lead, who will contact you today.", "Thank you."),
}
# Objections a call on the topic can raise, with weights: a delivery or return call rarely argues
# about price or a competitor, so the text stays coherent for whoever labels it.
_TOPIC_OBJECTIONS = {
    "delivery": (4, 0, 1, 0),
    "returns": (4, 0, 1, 0),
    "pricing": (3, 3, 2, 2),
    "product": (4, 2, 1, 2),
}


@dataclass(frozen=True)
class CallLabels:
    """The true signals a call was written from: the golden labels a model's are scored against."""

    topic: str
    objection: str
    sentiment: str
    next_step: str


def entities(page_size: int) -> list[Entity]:
    def fetch(interval: Interval, cursor: int) -> Page:
        return paginate(build_call_transcripts(interval), cursor, page_size)

    return [Entity(SOURCE, "call_transcripts", CALL_TRANSCRIPTS_TABLE, fetch)]


def _write(rng: random.Random, labels: CallLabels) -> str:
    lines = [
        "Agent: Thanks for calling, how can I help?",
        f"Customer: {rng.choice(_OPENINGS[labels.topic])}",
        f"Agent: {_AGENT_REPLIES[labels.topic]}",
    ]
    if labels.objection != "none":
        lines.append(f"Customer: {rng.choice(_OBJECTION_LINES[labels.objection])}")
        lines.append("Agent: I understand, let me see what I can do.")
    lines.append(f"Customer: {rng.choice(_SENTIMENT_LINES[labels.sentiment])}")
    agent, customer = _NEXT_STEP_LINES[labels.next_step]
    lines += [f"Agent: {agent}", f"Customer: {customer}"]
    return " ".join(lines)


def _day_calls(day: date) -> list[tuple[dict[str, object], CallLabels]]:
    """Every call on ``day``, with the labels its text was written from."""
    rng = random.Random(f"call_transcripts:{day.isoformat()}")
    midnight = datetime(day.year, day.month, day.day, tzinfo=UTC)
    calls = []
    for seq in range(1, 5 + rng.randint(0, 4) + 1):
        topic = rng.choice(TOPICS)
        labels = CallLabels(
            topic=topic,
            objection=rng.choices(OBJECTIONS, _TOPIC_OBJECTIONS[topic])[0],
            sentiment=rng.choices(SENTIMENTS, (3, 4, 2))[0],
            next_step=rng.choice(NEXT_STEPS),
        )
        at = midnight + timedelta(seconds=rng.randint(8 * 3_600, 18 * 3_600))
        row = {
            "transcript_id": f"T-{day:%Y%m%d}-{seq:03d}",
            "customer_id": rng.randint(1, CUSTOMER_COUNT),
            "call_ts": at.isoformat(),
            "duration_seconds": rng.randint(90, 1_200),
            "transcript": _write(rng, labels),
        }
        calls.append((row, labels))
    return calls


def _calls(interval: Interval) -> list[tuple[dict[str, object], CallLabels]]:
    first = interval.start.astimezone(UTC).date()
    last = interval.end.astimezone(UTC).date()
    found = [
        call
        for offset in range((last - first).days + 1)
        for call in _day_calls(first + timedelta(days=offset))
        if interval.start <= datetime.fromisoformat(str(call[0]["call_ts"])) < interval.end
    ]
    return sorted(found, key=lambda call: (call[0]["call_ts"], call[0]["transcript_id"]))


def build_call_transcripts(interval: Interval) -> list[dict[str, object]]:
    """Calls made in [start, end), ordered by call_ts then id; text only, no labels."""
    return [row for row, _ in _calls(interval)]


def call_labels(interval: Interval) -> dict[str, CallLabels]:
    """The true labels of the calls in [start, end), by transcript_id (the golden set's source)."""
    return {str(row["transcript_id"]): labels for row, labels in _calls(interval)}
