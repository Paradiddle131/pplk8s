"""Which data months a monthly pipeline keeps (PLAN.md D35, issue #87).

A pure rule, so the DAG owns the policy and the workloads only delete: EL Factory retires landing
(``POST /retire``) and dbt its own tables (``tlc_retire``), each given the months to keep.

Kept: the latest ``latest`` months on the schedule (from ``first_scheduled`` on) among the months
the warehouse holds and the run's own, plus the pinned months (the drift months backfilled on
purpose), plus the run's own month, so a run never retires what it is about to load.
The latest months count what landing holds, including a month still loading, so a catch-up run
never retires a newer month that a concurrent run is loading.
A run of an old month (a backfilled drift month) therefore keeps the newest scheduled months.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")


def kept_months(
    run_month: str,
    held: Iterable[str],
    *,
    first_scheduled: str,
    pinned: Iterable[str] = (),
    latest: int = 3,
) -> list[str]:
    """The months to keep, oldest first (every month as ``YYYY-MM``)."""
    held, pinned = list(held), list(pinned)
    for month in [run_month, first_scheduled, *held, *pinned]:
        if not MONTH.match(month):
            raise ValueError(f"month {month!r} is not YYYY-MM")
    if latest < 1:
        raise ValueError(f"latest must be at least 1, got {latest}")
    scheduled = sorted({m for m in [*held, run_month] if m >= first_scheduled}, reverse=True)
    return sorted({*scheduled[:latest], *pinned, run_month})
