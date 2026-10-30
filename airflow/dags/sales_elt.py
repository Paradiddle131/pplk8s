"""Airflow DAG for the scheduled sales ELT: synthetic customers and orders through EL Factory,
then the dbt medallion build of the ``sales`` models, with an ``ops.readiness`` record after each
stage.

The flow, retries and readiness products are the shared ELT pattern (``pplk8s.elt``, PLAN.md D38).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pplk8s.elt import elt_dag

sales_elt = elt_dag(
    "sales",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    tags=["elt", "sales", "phase4"],
    doc_md=__doc__,
)
