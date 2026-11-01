# syntax=docker/dockerfile:1.19
# dbt image for the lab's medallion build (PLAN.md Phase 1); the same image runs as a Kubernetes Job in Phase 2.
# One recipe, two builds (semantic/PLAN.md SL-19): WAREHOUSE=postgres (the default) for the lab, with the
# Airflow lab's TLC pipeline installed from the local package in packages/; WAREHOUSE=bigquery for GCP
# (`make gcp-images`), with the BigQuery adapter only and neither the TLC package nor the dev fixtures.
ARG WAREHOUSE=postgres

FROM python:3.13-slim AS runtime
ARG WAREHOUSE
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DBT_PROFILES_DIR=/dbt \
    DBT_SEND_ANONYMOUS_USAGE_STATS=False

# Postgres: the top-level pins. BigQuery: a full lock (requirements-bigquery.in, compiled with
# requirements-bigquery.exclude left out), installed as it is, with no dependency resolution of its own.
COPY requirements-${WAREHOUSE}.txt /tmp/requirements.txt
# `build_ca`: the TLS-intercepting proxy's CA where one sits between the build and PyPI (Makefile BUILD_CA).
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && if [ "$WAREHOUSE" = bigquery ]; then deps=--no-deps; else deps=; fi \
    && pip install $deps -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN useradd --uid 10001 --create-home --home-dir /home/dbt --shell /usr/sbin/nologin dbt
WORKDIR /dbt

FROM runtime AS postgres
COPY --exclude=requirements-* . /dbt
RUN dbt deps

# The GCP build: nothing local-only, so no Postgres package and no TLC model, macro, seed or test (the dev
# fixtures stay out of both builds, .dockerignore).
# The project parses on the `gcp` output, which needs a project id but no credential to parse.
FROM runtime AS bigquery
COPY --exclude=requirements-* --exclude=packages.yml --exclude=package-lock.yml --exclude=packages . /dbt
ENV DBT_TARGET=gcp
RUN ! pip list --format=freeze | grep -iE '^(dbt-postgres|psycopg|psycopg2|psycopg-binary|asyncpg)==' \
    && ! find /dbt -ipath '*tlc*' | grep . \
    && GCP_PROJECT=parse-only dbt parse \
    && ! grep -q '"package_name": "pplk8s_tlc"' target/manifest.json

FROM ${WAREHOUSE}
# Smoke check, all without a database connection: the project parses, no view reads another
# pipeline's model (scripts/check_pipeline_views.py, PLAN.md D20), the project keeps the agent-ready
# standard (scripts/check_standard.py, docs/agent-ready-warehouse.md), and the semantic manifest validates
# (`mf validate-configs --skip-dw`; the warehouse half runs in `make dbt-validate`).
# Parse output is discarded so the runtime target/ and logs/ start empty and owned by the dbt user.
RUN GCP_PROJECT=parse-only dbt parse \
    && python scripts/check_pipeline_views.py target/manifest.json \
    && python scripts/check_standard.py target \
    && GCP_PROJECT=parse-only mf validate-configs --skip-dw \
    && rm -rf /dbt/target /dbt/logs \
    && mkdir -p /dbt/target /dbt/logs \
    && chown -R 10001:10001 /dbt/target /dbt/logs

USER 10001

ENTRYPOINT ["dbt"]
CMD ["build"]
