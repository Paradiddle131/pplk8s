# syntax=docker/dockerfile:1
# One recipe per warehouse (semantic/PLAN.md SL-19): WAREHOUSE names the extra of pyproject.toml the
# image installs, so it carries only that warehouse's driver, and the image runs with ELF_WAREHOUSE set
# to it. postgres (the default) is the lab's Compose warehouse.
ARG WAREHOUSE=postgres

FROM ghcr.io/astral-sh/uv:0.11.7 AS uv

FROM python:3.13-slim AS builder
ARG WAREHOUSE
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first so source edits do not invalidate the dependency layer.
# `build_ca`: the TLS-intercepting proxy's CA where one sits between the build and PyPI (Makefile BUILD_CA).
COPY pyproject.toml uv.lock ./
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && uv sync --frozen --no-dev --extra "${WAREHOUSE}" --no-install-project
COPY src ./src
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && uv sync --frozen --no-dev --extra "${WAREHOUSE}" --no-editable

FROM python:3.13-slim AS runtime
ARG WAREHOUSE
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY catalog.yaml /app/catalog.yaml
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    CATALOG_PATH=/app/catalog.yaml \
    ELF_WAREHOUSE=${WAREHOUSE}
# Memory under the D35 ceiling (1 GiB), measured with real yellow months (one chunk in flight per
# process, two processes): Arrow's jemalloc pool kept ~500 MB of freed chunk buffers (1.04 GiB
# for one month), so Arrow uses the system allocator; glibc then kept freed buffers in per-thread
# arenas (1.07 GiB for three concurrent months), so two arenas and a fixed mmap threshold return
# large buffers at once (817 MiB).
ENV ARROW_DEFAULT_MEMORY_POOL=system \
    MALLOC_ARENA_MAX=2 \
    MALLOC_MMAP_THRESHOLD_=1048576
USER 10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8080'), timeout=2)"]
# Threaded workers (D34): a time-boxed /extract holds its thread for up to MAX_RUN_TIME plus a page.
# Sync workers were killed at gunicorn's 30 s worker timeout, and two busy ones starved /healthz;
# a gthread worker heartbeats from its main thread, so long requests neither time out nor block probes.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --worker-class gthread --threads 8 --no-control-socket --access-logfile - 'el_factory.app:create_app_from_env()'"]
