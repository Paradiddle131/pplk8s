#!/usr/bin/env bash
# Sourced by the checks that run dbt on the host: `dbt_deps <project dir>` installs dbt/packages.yml's local
# packages (the Airflow lab's TLC pipeline, semantic/PLAN.md SL-19) into that copy of the project, which
# `dbt parse` and every other command need first. A copy made with tar leaves out dbt_packages/ (its links
# point into the repo) and installs its own.
dbt_deps() {
  (cd "$1" && uvx --quiet --with-requirements requirements-postgres.txt --from dbt-core dbt deps --quiet) ||
    { echo "FAIL: dbt deps in $1" >&2; exit 1; }
}
