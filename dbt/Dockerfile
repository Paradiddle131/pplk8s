# dbt image for the lab's medallion build (PLAN.md Phase 1); the same image runs as a Kubernetes Job in Phase 2.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DBT_PROFILES_DIR=/dbt \
    DBT_SEND_ANONYMOUS_USAGE_STATS=False

COPY requirements.txt /tmp/requirements.txt
# `build_ca`: the TLS-intercepting proxy's CA where one sits between the build and PyPI (Makefile BUILD_CA).
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca SSL_CERT_FILE=/run/secrets/build_ca; fi \
    && pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN useradd --uid 10001 --create-home --home-dir /home/dbt --shell /usr/sbin/nologin dbt

WORKDIR /dbt
COPY . /dbt

# Smoke check, all without a database connection: the project parses, no view reads another
# pipeline's model (scripts/check_pipeline_views.py, PLAN.md D20), the project keeps the agent-ready
# standard (scripts/check_standard.py, docs/agent-ready-warehouse.md), and the semantic manifest validates
# (`mf validate-configs --skip-dw`; the warehouse half runs in `make dbt-validate`).
# Parse output is discarded so the runtime target/ and logs/ start empty and owned by the dbt user.
RUN dbt parse \
    && python scripts/check_pipeline_views.py target/manifest.json \
    && python scripts/check_standard.py target \
    && mf validate-configs --skip-dw \
    && rm -rf /dbt/target /dbt/logs \
    && mkdir -p /dbt/target /dbt/logs \
    && chown -R 10001:10001 /dbt/target /dbt/logs

USER 10001

ENTRYPOINT ["dbt"]
CMD ["build"]
