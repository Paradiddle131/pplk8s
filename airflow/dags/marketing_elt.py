"""Airflow DAG for the scheduled marketing ELT: synthetic campaigns, daily ad spend, CRM leads and
their bookings through EL Factory, then the dbt medallion build of the ``marketing`` models, with
an ``ops.readiness`` record after each stage.

The flow, retries and readiness products are the shared ELT pattern (``pplk8s.elt``, PLAN.md D38);
the semantic layer's marketing metrics read these layers (semantic/PLAN.md SL-8).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pplk8s.elt import elt_dag

marketing_elt = elt_dag(
    "marketing",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    tags=["elt", "marketing", "use-case"],
    doc_md=__doc__,
)
