"""How fresh a metric's data is: the readiness ledger and its deadlines (semantic/PLAN.md SL-4).

The catalog names the readiness products each metric reads (`sales.silver`; build_catalog.py).
A product is ready up to the end of its newest `ready` interval in `ops.readiness`, whichever
producer wrote it (the Airflow lab's D19). It is late, by D37's rule, when that end is older than
its deadline in `ops.product_deadlines`, or when it has a deadline and no ready interval at all.
A layer without a deadline of its own takes its pipeline's (`sales` for `sales.silver`), since the
pipeline is not ready before its layers are.

`freshness()` returns the facts and one `statement` the agent quotes in its answer; the statement is
built here, never by the model or its prompt.

The ledger is read through the warehouse seam (warehouse.py): on Postgres with dbt's own `DBT_*`
connection variables and profiles.yml's defaults, so it is read from the warehouse the metrics come
from, as the read-only `agent_metrics` role in the lab; on BigQuery from the lab project's `ops`
dataset, as the agent's own service account.
"""

from __future__ import annotations

import datetime
from typing import Any

from semantic_agent.warehouse import Readiness, WarehouseError, reason, warehouse


def _stamp(value: datetime.datetime) -> str:
    return value.astimezone(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")


def _hours(age: datetime.timedelta) -> str:
    return f"{age.total_seconds() / 3600:g} h"


def assess(rows: list[Readiness], now: datetime.datetime) -> dict[str, Any]:
    """The freshness of each product from its ledger row, and the sentence an answer quotes."""
    products, sentences = [], []
    for product, ready_until, max_age in rows:
        late = max_age is not None and (ready_until is None or now - ready_until > max_age)
        products.append(
            {
                "product": product,
                "ready_until": _stamp(ready_until) if ready_until else None,
                "deadline": _hours(max_age) if max_age is not None else None,
                "late": late,
            }
        )
        if ready_until is None:
            sentences.append(
                f"Late: {product} has never been ready (deadline {_hours(max_age)})."
                if late
                else f"Freshness unknown: {product} has no ready interval recorded."
            )
        elif late:
            sentences.append(
                f"Late: {product} is ready only up to {_stamp(ready_until)}, "
                f"older than its {_hours(max_age)} deadline."
            )
        else:
            sentences.append(f"Fresh: {product} is ready up to {_stamp(ready_until)}.")
    return {
        "products": products,
        "late": any(p["late"] for p in products),
        "statement": " ".join(sentences),
    }


def freshness(
    products: list[str],
    now: datetime.datetime | None = None,
    *,
    agent: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """The freshness of the given readiness products, read for `agent`'s `session_id` where the
    warehouse records who asked; an unreadable ledger is said, not raised."""
    now = now or datetime.datetime.now(datetime.UTC)
    if not products:
        return {
            "products": [],
            "late": None,
            "statement": "Freshness unknown: the catalog names no readiness product for these "
            "metrics (run make dbt-catalog).",
        }
    try:
        rows = warehouse().readiness(products, agent=agent, session_id=session_id)
    except WarehouseError as e:
        return {
            "products": [],
            "late": None,
            "statement": "Freshness unknown: the readiness ledger could not be read "
            f"({reason(e)}).",
        }
    return assess(rows, now)
