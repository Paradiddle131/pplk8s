# Review

What the `review` skill's `tier.sh` reads for a change to this repo, from the default branch.

## Sensitive
- `services/semantic-agent/evals/**` — the agent eval's frozen question set and the scoring criteria each case must meet; lenses: control-prober
- `services/semantic-agent/src/semantic_agent/evaluation.py` `services/semantic-agent/tests/test_evaluation.py` — the agent eval's scorers and the tests that prove them; lenses: control-prober
- `tests/e2e/agent-eval.sh` — the agent eval's runner, which sets its model, its retries and its free-tier spend; lenses: control-prober, guardrail-reviewer
- `dbt/dev/fixture.sql` `dbt/dev/fixture_weeks.sql` `tests/e2e/agent-fixture.sh` `services/semantic-agent/src/sql_baseline/**` — the agent eval's fixture data, the script that loads it, and the text-to-SQL baseline it compares against; lenses: control-prober
- `docs/research/semantic-agent-eval.md` — the agent eval's published scores; lenses: claims-auditor
- `dbt/seeds/silver/call_label_*.csv` `dbt/models/silver/slv_call_golden_labels.sql` `dbt/tests/silver/call_label*.sql` `dbt/macros/call_labels.sql` `dbt/dbt_project.yml` `dbt/scripts/record_call_labels.py` — the call labels' golden set and recorded answers, the prompt and thresholds that score them, and the tests and macros that apply those thresholds; lenses: control-prober
- `platform/gcp/**` — the lab project billed at $0.00, with its infrastructure, access grants, free-path allowlist and runbook; lenses: guardrail-reviewer
- `platform/gcp/cost-check.sh` `platform/gcp/check_free_path.py` `platform/gcp/free-path.yaml` `platform/gcp/guardrails-check.sh` `platform/gcp/tests/**` `platform/gcp/infra/tests/**` — the cost check and the checks of the lab project's spend stops; lenses: control-prober
- `Makefile` — the live GCP targets and the cost check run before and after them; lenses: guardrail-reviewer
- `services/semantic-agent/src/semantic_agent/warehouse_bigquery.py` `services/semantic-agent/src/semantic_agent/model.py` `tests/e2e/lib/bigquery_target.py` `tests/e2e/lib/fixture_to_bigquery.py` `tests/e2e/bigquery-run-check.sh` `dbt/profiles.yml` — the spend controls outside the platform folder, namely the BigQuery byte caps and free load jobs of the agent, the checks and dbt, and the model selector that lets only a free OpenRouter model reach the agent; lenses: guardrail-reviewer, control-prober
- `services/semantic-agent/src/semantic_agent/guard.py` `services/semantic-agent/src/semantic_agent/audit.py` `services/semantic-agent/src/semantic_agent/mcp_server.py` — the agent's security seam, where every data call is audited and an MCP client is let in by its token; lenses: control-prober, guardrail-reviewer
- `dbt/macros/agent_*.sql` `tests/e2e/agent-columns-check.sh` — the macros that create the agents' logins, roles and grants and withhold every column marked personal data from them, and the check that no agent role reads one; lenses: guardrail-reviewer, leak-hunter, control-prober
- `dbt/models/bronze/schema.yml` `dbt/models/silver/schema.yml` `dbt/models/exposed/schema.yml` `dbt/dbt_project.yml` — the columns marked personal data and the post-hook that applies those markings to every model; lenses: leak-hunter, guardrail-reviewer
- `airflow/include/**` — the seam every business DAG reaches its workloads through, which keeps the DAGs portable to Cloud Composer; lenses: guardrail-reviewer
- `dbt/models/semantic/**` `dbt/models/silver/**` — the published metrics, their glossary and the semantic models under them, whose descriptions the agents quote; lenses: claims-auditor
- `dbt/models/gold/**` `dbt/models/exposed/**` — the hand-written aggregates that are the metrics' parity oracle, and the exposed layer consumers read
- `dbt/tests/gold/**` `dbt/tests/exposed/**` `dbt/macros/test_matches_metric.sql` `dbt/macros/test_failed_call_share.sql` `dbt/macros/test_latest_load_reconciles.sql` `dbt/macros/hops.sql` `dbt/scripts/check_standard.py` `dbt/scripts/validate_semantic.py` `dbt/scripts/check_catalog.py` `dbt/scripts/build_catalog.py` `tests/e2e/semantic-check.sh` — the checks that hold the metrics to their standard and their parity oracle, the generic tests behind them, and the catalog the agents read; lenses: control-prober
- `CLAUDE.md` `REVIEW.md` `docs/agents/**` — the repo's rules, this file, and the unattended wakes' profile; lenses: guardrail-reviewer
- `.process-ids` — the process-id check's exemptions; lenses: guardrail-reviewer, control-prober
- `PLAN.md` `LESSONS.md` `LEDGER.md` `ledger.d/**` — the frozen history, which no change adds to; lenses: guardrail-reviewer
