# Review

What the `review` skill's `tier.sh` reads for a change to this repo, from the default branch.
`tier.sh` reads each item under § Sensitive as backticked globs and their lenses only, so the reason for each item is under § Why, in the same order.

## Sensitive
- `services/semantic-agent/evals/**`; lenses: control-prober
- `services/semantic-agent/src/semantic_agent/evaluation.py` `services/semantic-agent/tests/test_evaluation.py`; lenses: control-prober
- `tests/e2e/agent-eval.sh`; lenses: control-prober, guardrail-reviewer
- `docs/research/semantic-agent-eval.md`; lenses: claims-auditor
- `dbt/seeds/silver/call_label_*.csv` `dbt/models/silver/slv_call_golden_labels.sql` `dbt/tests/silver/call_label*.sql` `dbt/scripts/record_call_labels.py`; lenses: control-prober
- `platform/gcp/**`; lenses: guardrail-reviewer
- `platform/gcp/cost-check.sh` `platform/gcp/check_free_path.py` `platform/gcp/free-path.yaml` `platform/gcp/guardrails-check.sh` `platform/gcp/tests/**` `platform/gcp/infra/tests/**`; lenses: control-prober
- `Makefile`; lenses: guardrail-reviewer
- `airflow/include/**`; lenses: guardrail-reviewer
- `dbt/models/semantic/**` `dbt/models/silver/**`; lenses: claims-auditor
- `dbt/models/gold/**` `dbt/models/exposed/**`
- `dbt/tests/gold/**` `dbt/tests/exposed/**` `dbt/scripts/check_standard.py` `dbt/scripts/validate_semantic.py` `dbt/scripts/check_catalog.py` `dbt/scripts/build_catalog.py` `tests/e2e/semantic-check.sh`; lenses: control-prober
- `tests/e2e/agent-columns-check.sh`; lenses: control-prober
- `docs/agents/**` `.process-ids`; lenses: guardrail-reviewer, control-prober
- `PLAN.md` `LESSONS.md` `LEDGER.md` `ledger.d/**`; lenses: guardrail-reviewer

## Why
- The agent eval's frozen question set and the scoring criteria each case must meet.
- The agent eval's scorers and the tests that prove them.
- The agent eval's runner: its fixture, its model and its free-tier spend.
- The agent eval's published scores.
- The call labels' golden set, its recorded answers and the thresholds that score them.
- The lab project billed at $0.00: its infrastructure, access grants, free-path allowlist and runbook.
- The cost check and the checks of the lab project's spend stops.
- The live GCP targets and the cost check run before and after them.
- The seam every business DAG reaches its workloads through, which keeps the DAGs portable to Cloud Composer.
- The published metrics, their glossary and the semantic models under them, whose descriptions the agents quote.
- The hand-written aggregates that are the metrics' parity oracle, and the exposed layer consumers read.
- The checks that hold the metrics to their standard and their parity oracle, and the catalog the agents read.
- The check that no agent role reads a column marked personal data.
- The unattended wakes' profile and the process-id check's exemptions.
- The frozen history, which no change adds to.
