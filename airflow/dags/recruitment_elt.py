"""Airflow DAG for the scheduled recruitment ELT: every candidate in their current hiring stage,
through EL Factory, then the dbt medallion build of the ``recruitment`` models, with an
``ops.readiness`` record after each stage.

The source keeps only each candidate's current stage, so the silver stage's dbt snapshot is the
only record of the stage history: it sees the changes between two runs of this DAG, and the
schedule bounds the history's resolution (semantic/PLAN.md SL-17). The flow, retries and readiness
products are the shared ELT pattern (``pplk8s.elt``, PLAN.md D38).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pplk8s.elt import elt_dag

recruitment_elt = elt_dag(
    "recruitment",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    tags=["elt", "recruitment", "use-case"],
    doc_md=__doc__,
)
