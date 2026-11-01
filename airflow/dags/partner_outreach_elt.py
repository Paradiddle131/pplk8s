"""Airflow DAG for the scheduled partner-outreach ELT: partners, their contacts with consent and
opt-out flags, the messages the outreach automation sent and the replies, through EL Factory, then
the dbt medallion build of the ``partner_outreach`` models, with an ``ops.readiness`` record after
each stage.

The exposed stage builds the activation list the automation reads (who to contact next, never an
opted-out or recently contacted contact); the semantic layer's outreach metrics read the silver
models (semantic/PLAN.md SL-8, SL-16). The flow, retries and readiness products are the shared ELT
pattern (``pplk8s.elt``, PLAN.md D38).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pplk8s.elt import elt_dag

partner_outreach_elt = elt_dag(
    "partner_outreach",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    tags=["elt", "partner_outreach", "use-case"],
    doc_md=__doc__,
)
