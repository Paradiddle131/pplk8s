"""Airflow DAG for the scheduled customer-actions ELT: the synthetic stream of site and CRM actions
through EL Factory, then the dbt medallion build of the ``customer_actions`` models, with an
``ops.readiness`` record after each stage.

The stream is extracted by the time an action was received, so a run's extract holds actions that
happened the day before; silver merges them incrementally into their own event date
(semantic/PLAN.md SL-15). The flow, retries and readiness products are the shared ELT pattern
(``pplk8s.elt``, PLAN.md D38); the semantic layer's engagement and funnel metrics read these
layers (semantic/PLAN.md SL-8).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pplk8s.elt import elt_dag

customer_actions_elt = elt_dag(
    "customer_actions",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    tags=["elt", "customer_actions", "use-case"],
    doc_md=__doc__,
)
