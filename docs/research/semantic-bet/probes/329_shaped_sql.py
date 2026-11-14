"""MetricFlow's compiled BigQuery SQL for every saved query, with a date range, as the source of bet_shaped.

Measures: for each saved query in dbt/models/semantic/saved_queries.yml, the SQL MetricFlow's engine compiles
in BigQuery's dialect with a time constraint of 2026-02-03 to 2026-04-05 (sentinel dates inside the time spine,
so the hand-written table functions can show where the date range lands), and how many WHERE clauses carry them.
MetricFlow moves a start before its time spine forward (a 1999-01-01 start compiled as 2000-01-01).
Run (from the repo root), on a copy of dbt/ parsed on the compile-only `bigquery` target (as
tests/e2e/governed-models.sh makes one), from inside that copy:
  cd <copy> && DBT_TARGET=bigquery DBT_PROFILES_DIR=. uv run --no-project \
    --with-requirements requirements-postgres.txt --with dbt-bigquery==1.12.1 --with dbt-metricflow==0.15.0 \
    python -I <repo>/docs/research/semantic-bet/probes/329_shaped_sql.py [out-dir]
Writes <out-dir>/<saved query>.sql (default target/bet_shaped) and prints one line per saved query.
Not quite offline: CLIConfiguration.setup (as the mf CLI and dbt/scripts/build_catalog.py use it) runs dbt's
connection test, `select 1` on the target, before the engine's explain; on a cloud VM whose egress proxy injects a
Google credential that reaches BigQuery despite the placeholder token (refused: the `bigquery` target's project
`pplk8s-lab` does not exist, so nothing runs or bills).
"""

import datetime
import sys
from pathlib import Path

import yaml
from dbt_metricflow.cli.cli_configuration import CLIConfiguration
from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest

START = datetime.datetime(2026, 2, 3)
END = datetime.datetime(2026, 4, 5)


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "target/bet_shaped")
    out.mkdir(parents=True, exist_ok=True)
    config = CLIConfiguration()
    config.setup(dbt_project_path=Path.cwd())
    engine = MetricFlowEngine(
        semantic_manifest_lookup=config.semantic_manifest_lookup,
        sql_client=config.sql_client,
    )
    saved = yaml.safe_load(Path("models/semantic/saved_queries.yml").read_text())[
        "saved_queries"
    ]
    for query in saved:
        name = query["name"]
        request = MetricFlowQueryRequest.create(
            saved_query_name=name, time_constraint_start=START, time_constraint_end=END
        )
        sql = engine.explain(request).sql_statement.sql
        (out / f"{name}.sql").write_text(sql + "\n")
        filters = sql.count("BETWEEN '2026-02-03' AND '2026-04-05'")
        print(
            f"{name}: {len(sql.splitlines())} lines, the date range filtered in {filters} places"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
