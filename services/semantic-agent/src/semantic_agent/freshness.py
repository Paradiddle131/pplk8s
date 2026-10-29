"""How fresh a metric's data is: the readiness ledger and its deadlines (semantic/PLAN.md SL-4).

The catalog names the readiness products each metric reads (`sales.silver`; build_catalog.py).
A product is ready up to the end of its newest `ready` interval in `ops.readiness`, whichever
producer wrote it (the Airflow lab's D19). It is late, by D37's rule, when that end is older than
its deadline in `ops.product_deadlines`, or when it has a deadline and no ready interval at all.
A layer without a deadline of its own takes its pipeline's (`sales` for `sales.silver`), since the
pipeline is not ready before its layers are.

`freshness()` returns the facts and one `statement` the agent quotes in its answer; the statement is
built here, never by the model or its prompt.

Env: dbt's own `DBT_*` connection variables, with profiles.yml's defaults, so the ledger is read
from the warehouse the metrics come from, as the read-only `agent_metrics` role in the lab.
"""

from __future__ import annotations

import datetime
import os
from typing import Any

import psycopg

SQL = """
select p.product,
       (select max(r.interval_end) from ops.readiness r
         where r.product = p.product and r.status = 'ready') as ready_until,
       coalesce(own.max_age, pipeline.max_age) as max_age
from unnest(%(products)s::text[]) as p(product)
left join ops.product_deadlines own on own.product = p.product
left join ops.product_deadlines pipeline on pipeline.product = split_part(p.product, '.', 1)
order by p.product
"""


def _url() -> str:
    env = os.environ.get
    user, password = env("DBT_USER", "warehouse"), env("DBT_PASSWORD", "warehouse")
    host, port = env("DBT_HOST", "warehouse"), env("DBT_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{env('DBT_DBNAME', 'warehouse')}"


def _stamp(value: datetime.datetime) -> str:
    return value.astimezone(datetime.UTC).strftime("%Y-%m-%dT%H:%MZ")


def _hours(age: datetime.timedelta) -> str:
    return f"{age.total_seconds() / 3600:g} h"


def assess(
    rows: list[tuple[str, datetime.datetime | None, datetime.timedelta | None]],
    now: datetime.datetime,
) -> dict[str, Any]:
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


def freshness(products: list[str], now: datetime.datetime | None = None) -> dict[str, Any]:
    """The freshness of the given readiness products; an unreadable ledger is said, not raised."""
    now = now or datetime.datetime.now(datetime.UTC)
    if not products:
        return {
            "products": [],
            "late": None,
            "statement": "Freshness unknown: the catalog names no readiness product for these "
            "metrics (run make dbt-catalog).",
        }
    try:
        with psycopg.connect(_url(), connect_timeout=10) as conn:
            rows = conn.execute(SQL, {"products": products}).fetchall()
    except psycopg.Error as e:
        reason = str(e).strip().splitlines()[0]
        return {
            "products": [],
            "late": None,
            "statement": f"Freshness unknown: the readiness ledger could not be read ({reason}).",
        }
    return assess(rows, now)
