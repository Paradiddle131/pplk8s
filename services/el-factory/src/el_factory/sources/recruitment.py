"""A deterministic synthetic applicant-tracking source (semantic/PLAN.md SL-8, SL-17): candidates
who apply for a role and move through the hiring stages applied -> screen -> interview -> offer ->
hired, or are rejected at any stage before hired.

The source keeps only each candidate's current stage and when they entered it (``stage_ts``), as an
applicant-tracking system's table does: every interval extracts every candidate who had applied by
the interval's end, in the stage they were in at that moment. The stage history is not in the
source; the warehouse keeps it with a dbt snapshot, so its resolution is the extraction schedule's.
Each candidate's journey comes from their own seed, so a row never depends on the interval that
requested it. Candidates carry no personal data: an id, the role and how they applied.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from el_factory.model import Interval, Page, Table
from el_factory.sources.base import Entity
from el_factory.sources.paging import paginate

SOURCE = "synthetic"
STAGES = ("applied", "screen", "interview", "offer", "hired")
CLOSED_STAGES = ("hired", "rejected")
ROLES = ("engineering", "sales", "support")
CHANNELS = ("referral", "job_board", "agency")
APPLICATIONS_START = date(2026, 9, 1)
# The share of candidates who move on from each stage; the rest are rejected there.
PASS_RATE = {"applied": 0.7, "screen": 0.6, "interview": 0.5, "offer": 0.8}
# A candidate stays in a stage between these many days before moving on or being rejected.
MIN_STAGE_DAYS, MAX_STAGE_DAYS = 0, 6

APPLICATIONS_TABLE = Table(
    "synthetic_applications",
    (
        ("candidate_id", "text"),
        ("role", "text"),
        ("channel", "text"),
        ("applied_ts", "timestamptz"),
        ("stage", "text"),
        ("stage_ts", "timestamptz"),
    ),
)


def entities(page_size: int) -> list[Entity]:
    def fetch(interval: Interval, cursor: int) -> Page:
        return paginate(build_applications(interval), cursor, page_size)

    return [Entity(SOURCE, "applications", APPLICATIONS_TABLE, fetch)]


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _journey(candidate_id: str, applied: datetime) -> list[tuple[str, datetime]]:
    """Every stage the candidate enters, with when, from the candidate's own seed."""
    rng = random.Random(f"candidate:{candidate_id}")
    journey = [("applied", applied)]
    for stage, next_stage in zip(STAGES, STAGES[1:], strict=False):
        at = journey[-1][1] + timedelta(
            days=rng.randint(MIN_STAGE_DAYS, MAX_STAGE_DAYS), seconds=rng.randint(3_600, 8 * 3_600)
        )
        if rng.random() >= PASS_RATE[stage]:
            journey.append(("rejected", at))
            break
        journey.append((next_stage, at))
    return journey


def _day_candidates(day: date) -> list[dict[str, object]]:
    """The candidates who applied on ``day``, each with their whole journey."""
    rng = random.Random(f"applications:{day.isoformat()}")
    candidates = []
    for seq in range(1, 2 + rng.randint(0, 3) + 1):
        candidate_id = f"K-{day:%Y%m%d}-{seq:02d}"
        applied = _midnight(day) + timedelta(seconds=rng.randint(7 * 3_600, 20 * 3_600))
        candidates.append(
            {
                "candidate_id": candidate_id,
                "role": rng.choice(ROLES),
                "channel": rng.choice(CHANNELS),
                "applied_ts": applied,
                "journey": _journey(candidate_id, applied),
            }
        )
    return candidates


def build_applications(interval: Interval) -> list[dict[str, object]]:
    """Every candidate who had applied by the interval's end, in their stage at that moment."""
    rows = []
    day = APPLICATIONS_START
    while _midnight(day) < interval.end:
        for candidate in _day_candidates(day):
            applied = candidate["applied_ts"]
            if not isinstance(applied, datetime) or applied >= interval.end:
                continue
            stage, stage_ts = [step for step in candidate["journey"] if step[1] < interval.end][-1]
            rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "role": candidate["role"],
                    "channel": candidate["channel"],
                    "applied_ts": applied.isoformat(),
                    "stage": stage,
                    "stage_ts": stage_ts.isoformat(),
                }
            )
        day += timedelta(days=1)
    return sorted(rows, key=lambda r: r["candidate_id"])
