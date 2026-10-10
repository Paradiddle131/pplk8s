"""Run context shared by the business DAGs: safe run ids, processing intervals, file events.

Pure functions only, so DAG files stay thin and these rules are unit-tested once.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from airflow.sdk.exceptions import AirflowFailException

from pplk8s.el_factory import RUN_ID_PATTERN

_GENERATION = re.compile(r"^[1-9][0-9]{0,18}$")


def safe_run_id(run_id: str) -> str:
    """Airflow run ids (``scheduled__2026-10-09T00:00:00+00:00``) already satisfy EL Factory's
    run_id pattern; anything else is mapped deterministically to a safe form."""
    if RUN_ID_PATTERN.match(run_id):
        return run_id
    return re.sub(r"[^A-Za-z0-9_.:+-]", "_", run_id)


def resolve_interval(
    start: datetime | None, end: datetime | None, logical_date: datetime
) -> tuple[datetime, datetime]:
    """Return the half-open UTC interval a run processes.

    Scheduled runs use their data interval.  Manual runs may carry an empty or missing interval;
    they process the last complete UTC day before ``logical_date``, i.e. what the daily
    schedule would have processed at that moment.
    """
    if start is not None and end is not None and start < end:
        return start.astimezone(UTC), end.astimezone(UTC)
    day = logical_date.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=1), day


def file_event(conf: dict[str, Any] | None, object_pattern: re.Pattern[str]) -> dict[str, str]:
    """Validate the ``{bucket, object, generation}`` conf an event-triggered run carries.

    ``object_pattern`` must match the whole object name and capture the file's UTC day as the
    group ``day`` (``YYYY-MM-DD``); the run processes the interval ``[day, day + 1)``.
    A malformed event can never become valid on retry, so every problem fails fast.
    """
    conf = conf or {}
    bucket, name, generation = (conf.get(k) for k in ("bucket", "object", "generation"))
    if isinstance(generation, int) and not isinstance(generation, bool):
        generation = str(generation)
    if not all(isinstance(v, str) and v for v in (bucket, name, generation)):
        raise AirflowFailException(f"conf needs string bucket, object, generation: {conf!r}")
    if not _GENERATION.match(generation):
        raise AirflowFailException(f"generation {generation!r} is not a positive integer")
    match = object_pattern.fullmatch(name)
    if match is None:
        raise AirflowFailException(f"object {name!r} does not match {object_pattern.pattern}")
    try:
        day = datetime.strptime(match["day"], "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise AirflowFailException(f"object {name!r} names no valid day") from exc
    return {
        "bucket": bucket,
        "object": name,
        "generation": generation,
        "interval_start": day.isoformat(),
        "interval_end": (day + timedelta(days=1)).isoformat(),
    }
