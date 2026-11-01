"""Query one metric grouped by a date part of metric_time, as the semantic agent's query_metrics builds it.

The `mf` CLI parses no date part from a group-by name (`metric_time__extract_dow` is refused), so this asks
MetricFlow's engine with the typed parameter the agent sends, set up as the CLI sets it up, against the dbt
target the environment names (Postgres or the BigQuery emulator).

Usage, from the dbt project: python mf_date_part.py METRIC PART START END OUT.csv
  (PART: year, quarter, month, day, dow or doy; dow is ISO, 1 Monday to 7 Sunday)
Writes the CSV `metric_time__extract_<part>,<metric>`, one row per value of the part.
"""

from __future__ import annotations

import csv
import datetime
import os
import sys
from pathlib import Path


def main() -> int:
    from dbt_metricflow.cli.cli_configuration import CLIConfiguration
    from metricflow.engine.metricflow_engine import MetricFlowEngine, MetricFlowQueryRequest
    from metricflow_semantic_interfaces.type_enums.date_part import DatePart
    from metricflow_semantics.specs.query_param_implementations import TimeDimensionParameter

    metric, part, start, end, out = sys.argv[1:6]
    project = Path.cwd()
    config = CLIConfiguration()
    config.setup(dbt_project_path=project, dbt_profiles_path=Path(os.environ.get("DBT_PROFILES_DIR", project)))
    engine = MetricFlowEngine(semantic_manifest_lookup=config.semantic_manifest_lookup, sql_client=config.sql_client)
    request = MetricFlowQueryRequest.create(
        metric_names=[metric],
        group_by=[TimeDimensionParameter(name="metric_time", date_part=DatePart(part))],
        time_constraint_start=datetime.datetime.fromisoformat(start),
        time_constraint_end=datetime.datetime.fromisoformat(end),
    )
    table = engine.query(request).result_df
    with open(out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(table.column_names)
        writer.writerows(table.rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
