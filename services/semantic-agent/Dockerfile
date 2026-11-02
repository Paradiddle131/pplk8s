# syntax=docker/dockerfile:1.19
# The semantic agent served by `adk api_server`: the Cloud Run stand-in of semantic/PLAN.md SL-2,
# deployed in the workloads namespace (platform/k8s/workloads). The text-to-SQL baseline is the eval's
# control (SL-5) and is never deployed, so the image carries the semantic agent's package only.
# One recipe, two builds (SL-19): WAREHOUSE=postgres (the default) for the lab, with the Airflow lab's TLC
# package and ADK's Postgres session store; WAREHOUSE=bigquery for GCP (`make gcp-images`, #209), with
# BigQuery's client and dbt adapter, Firestore sessions and neither Postgres nor TLC.
# Build with the dbt project as a named context: `docker build --build-context dbt=dbt services/semantic-agent`.
ARG WAREHOUSE=postgres

FROM ghcr.io/astral-sh/uv:0.11.7 AS uv

FROM python:3.13-slim AS builder-base
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# `build_ca`: the TLS-intercepting proxy's CA where one sits between the build and PyPI (Makefile BUILD_CA).
# `--extra postgres`: the Compose warehouse's driver for the audit and freshness (AGENT_WAREHOUSE's default),
# dbt-postgres and ADK's DatabaseSessionService.
FROM builder-base AS builder-postgres
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && uv sync --frozen --no-default-groups --extra postgres --no-install-project

# The bigquery extra exported from uv.lock (requirements-bigquery.txt; `make gcp-validate` fails when it is
# stale), installed as it is with no resolution of its own; the build fails on any Postgres package.
FROM builder-base AS builder-bigquery
COPY requirements-bigquery.txt ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && uv venv --quiet .venv \
    && VIRTUAL_ENV=/app/.venv uv pip install --no-deps -r requirements-bigquery.txt \
    && ! VIRTUAL_ENV=/app/.venv uv pip list --format=freeze \
      | grep -iE '^(dbt-postgres|psycopg|psycopg2|psycopg2-binary|psycopg-binary|psycopg-c|psycopg-pool|asyncpg)=='

FROM builder-${WAREHOUSE} AS builder

FROM python:3.13-slim AS runtime
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# The dbt project MetricFlow compiles requests against: what `dbt parse` and the catalog read, so not the
# singular tests in dbt/tests (the catalog reads only generic tests, declared in YAML and macros/). Its target
# (manifest and agent catalog) is written at start, for the database the agent reads (SL-3): by the catalog
# initContainer on kind, by the entrypoint on Cloud Run.
COPY --from=dbt dbt_project.yml profiles.yml selectors.yml /app/dbt/
COPY --from=dbt models /app/dbt/models
COPY --from=dbt macros /app/dbt/macros
COPY --from=dbt seeds /app/dbt/seeds
COPY --from=dbt snapshots /app/dbt/snapshots
COPY --from=dbt scripts/build_catalog.py /app/dbt/scripts/build_catalog.py
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    PORT=8080 \
    DBT_PROJECT_DIR=/app/dbt \
    DBT_PROFILES_DIR=/app/dbt \
    DBT_SEND_ANONYMOUS_USAGE_STATS=False \
    DBT_TARGET_PATH=/app/dbt/target \
    DBT_LOG_PATH=/app/dbt/logs

FROM runtime AS postgres
# The agents directory `adk api_server` serves: one package per agent, each with its root_agent;
# only semantic_agent, so the Service lists one app (SL-5: the baseline runs only inside the eval).
COPY src/semantic_agent /app/agents/semantic_agent
# The local dbt package (the Airflow lab's TLC pipeline, semantic/PLAN.md SL-19), as the lab's catalog lists its
# public tables; the same paths, no singular tests. The bigquery build leaves it out.
COPY --from=dbt packages.yml package-lock.yml /app/dbt/
COPY --from=dbt packages/tlc/dbt_project.yml /app/dbt/packages/tlc/
COPY --from=dbt packages/tlc/models /app/dbt/packages/tlc/models
COPY --from=dbt packages/tlc/macros /app/dbt/packages/tlc/macros
COPY --from=dbt packages/tlc/seeds /app/dbt/packages/tlc/seeds
# Smoke check without a database: the package installs, the project parses and the catalog builds; the output is
# discarded so the runtime target starts empty.
RUN cd /app/dbt && dbt deps --quiet && dbt parse --quiet && python scripts/build_catalog.py target \
    && rm -rf target logs && mkdir target logs && chown 10001:10001 target logs
USER 10001
EXPOSE 8080
# SESSION_SERVICE_URI: ADK's DatabaseSessionService (the metadata DB's agent_sessions database).
CMD ["sh", "-c", "exec adk api_server --host 0.0.0.0 --port \"${PORT}\" --session_service_uri \"${SESSION_SERVICE_URI}\" /app/agents"]

# The GCP build: the agent without its Postgres implementation, ADK's services.py (the firestore:// session
# scheme) beside it, and the dbt project on the `gcp` output (the lab project from GCP_PROJECT).
FROM runtime AS bigquery
COPY --exclude=warehouse_postgres.py src/semantic_agent /app/agents/semantic_agent
COPY src/services.py /app/agents/services.py
COPY --chmod=0755 gcp-entrypoint.sh /usr/local/bin/gcp-entrypoint.sh
ENV AGENT_WAREHOUSE=bigquery \
    DBT_TARGET=gcp \
    SESSION_SERVICE_URI=firestore://
# Smoke check without a project or a credential: no Postgres package and no TLC path, the project parses on the
# `gcp` output (a project id, no credential), the catalog builds and services.py registers firestore://; the
# output is discarded so the runtime target starts empty.
RUN export GCP_PROJECT=parse-only && ! find /app/dbt /app/agents -ipath '*tlc*' | grep . \
    && ! python -c 'import psycopg' 2>/dev/null && ! python -c 'import psycopg2' 2>/dev/null \
    && cd /app/dbt && dbt parse --quiet \
    && ! grep -q '"package_name": "pplk8s_tlc"' target/manifest.json \
    && python scripts/build_catalog.py target \
    && cd /app/agents && python -c 'import services, google.cloud.firestore' \
    && rm -rf /app/dbt/target /app/dbt/logs && mkdir /app/dbt/target /app/dbt/logs \
    && chown 10001:10001 /app/dbt/target /app/dbt/logs
USER 10001
EXPOSE 8080
# The catalog for the project the agent reads, then `adk api_server`; sessions in Firestore's (default) database
# (ADK's FirestoreSessionService, services.py), memory:// in `make gcp-image-check`.
ENTRYPOINT ["gcp-entrypoint.sh"]
CMD ["sh", "-c", "exec adk api_server --host 0.0.0.0 --port \"${PORT}\" --session_service_uri \"${SESSION_SERVICE_URI}\" /app/agents"]

FROM ${WAREHOUSE}
