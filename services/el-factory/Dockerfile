# syntax=docker/dockerfile:1.19
# One recipe per warehouse (semantic/PLAN.md SL-19): WAREHOUSE names the stage the image is built
# from, so it carries only that warehouse's driver, and the image runs with ELF_WAREHOUSE set to it.
# postgres (the default) is the lab's Compose warehouse, with the file sources (el_factory/tlc and
# pyarrow, the `files` extra), which only Postgres keeps a ledger for.
ARG WAREHOUSE=postgres

FROM ghcr.io/astral-sh/uv:0.11.7 AS uv

FROM python:3.13-slim AS builder-base
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# The dependencies only: the package itself is copied into the image's stage below, so each stage
# chooses which of its modules it carries.
# `build_ca`: the TLS-intercepting proxy's CA where one sits between the build and PyPI (Makefile BUILD_CA).
FROM builder-base AS builder-postgres
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && uv sync --frozen --no-dev --extra postgres --extra files --no-install-project

# The bigquery extra exported from uv.lock (requirements-bigquery.txt; `make gcp-validate` fails when it is
# stale), installed as it is with no resolution of its own; the build fails on a Postgres package or pyarrow.
FROM builder-base AS builder-bigquery
COPY requirements-bigquery.txt ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && uv venv --quiet .venv \
    && VIRTUAL_ENV=/app/.venv uv pip install --no-deps -r requirements-bigquery.txt \
    && ! VIRTUAL_ENV=/app/.venv uv pip list --format=freeze \
      | grep -iE '^(psycopg|psycopg2|psycopg2-binary|psycopg-binary|psycopg-c|psycopg-pool|asyncpg|pyarrow)=='

FROM builder-${WAREHOUSE} AS builder

FROM python:3.13-slim AS runtime
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY catalog.yaml /app/catalog.yaml
# The package sits at /app/el_factory, on the path, as each stage copies it.
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    CATALOG_PATH=/app/catalog.yaml
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8080'), timeout=2)"]
# Threaded workers (D34): a time-boxed /extract holds its thread for up to MAX_RUN_TIME plus a page.
# Sync workers were killed at gunicorn's 30 s worker timeout, and two busy ones starved /healthz;
# a gthread worker heartbeats from its main thread, so long requests neither time out nor block probes.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --worker-class gthread --threads 8 --no-control-socket --access-logfile - 'el_factory.app:create_app_from_env()'"]

# The lab's build: the whole package, the file sources included.
FROM runtime AS postgres
COPY src/el_factory /app/el_factory
RUN python -m compileall -q /app/el_factory
# Memory under the D35 ceiling (1 GiB), measured with real yellow months (one chunk in flight per
# process, two processes): Arrow's jemalloc pool kept ~500 MB of freed chunk buffers (1.04 GiB
# for one month), so Arrow uses the system allocator; glibc then kept freed buffers in per-thread
# arenas (1.07 GiB for three concurrent months), so two arenas and a fixed mmap threshold return
# large buffers at once (817 MiB).
ENV ELF_WAREHOUSE=postgres \
    ARROW_DEFAULT_MEMORY_POOL=system \
    MALLOC_ARENA_MAX=2 \
    MALLOC_MMAP_THRESHOLD_=1048576
USER 10001

# The GCP build (semantic/PLAN.md SL-19, #227): the package without its Postgres implementation and without
# the file sources (el_factory/tlc), which only a warehouse with a file ledger serves. Smoke check: no
# Postgres driver, no pyarrow and no TLC path, and the app imports and builds on BigQuery without touching it.
FROM runtime AS bigquery
COPY --exclude=tlc --exclude=warehouse_postgres.py src/el_factory /app/el_factory
RUN python -m compileall -q /app/el_factory \
    && ! find /app -ipath '*tlc*' | grep . \
    && ! python -c 'import psycopg' 2>/dev/null && ! python -c 'import pyarrow' 2>/dev/null \
    && ELF_WAREHOUSE=bigquery GCP_PROJECT=build-only python -c 'import sys; from el_factory.config import Config; from el_factory.warehouse import warehouse; import el_factory.app; warehouse(Config.from_env()); sys.exit(any(m in sys.modules for m in ("psycopg", "pyarrow", "el_factory.tlc")))'
ENV ELF_WAREHOUSE=bigquery
USER 10001

FROM ${WAREHOUSE}
