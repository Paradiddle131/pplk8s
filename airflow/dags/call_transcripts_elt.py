"""Airflow DAG for the scheduled call-transcripts ELT: synthetic sales and support call transcripts
through EL Factory, then the dbt medallion build of the ``call_transcripts`` models, with an
``ops.readiness`` record after each stage.

EL Factory lands the text only; dbt's silver stage labels it (topic, objection, sentiment, next
step) through the warehouse's AI function on BigQuery, or recorded labels in the lab, and tests the
labels against a golden set before gold reads them (semantic/PLAN.md SL-18, docs/text-signals.md).
The flow, retries and readiness products are the shared ELT pattern (``pplk8s.elt``, PLAN.md D38).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pplk8s.elt import elt_dag

call_transcripts_elt = elt_dag(
    "call_transcripts",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    tags=["elt", "call_transcripts", "use-case"],
    doc_md=__doc__,
)
