# Airflow image for the lab (PLAN.md D1, D3): the official 3.3.1 image plus the
# provider pins from requirements.txt and the shared `pplk8s` package in include/.
# Build context is this directory: `docker build -t <tag> airflow`.
FROM apache/airflow:3.3.1-python3.11

ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.11

COPY --chown=airflow:0 requirements.txt /tmp/requirements.txt

# Install under the upstream constraints so transitive deps match what Airflow
# was tested with. D3/D27 pin Composer 3.3.1-build.3's providers where they are
# newer than the constraints (google 22.4.0, cncf-kubernetes 10.21.1, postgres
# 7.0.2, common-sql 2.1.1, standard 1.18.0, fab 3.8.1), and google 22.4.0 needs
# google-cloud-aiplatform>=1.164 while the constraints freeze 1.163.0, so those
# constraint lines are dropped; pip still resolves everything else against the
# remaining constraints, and `pip check` proves the result is consistent.
RUN curl -fsSL -o /tmp/constraints.txt \
      "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
 && sed -i -E '/^(apache-airflow-providers-(google|cncf-kubernetes|postgres|common-sql|standard|fab)|google-cloud-aiplatform)==/d' /tmp/constraints.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt -c /tmp/constraints.txt \
 && pip check \
 && rm /tmp/constraints.txt /tmp/requirements.txt

# Shared hooks/helpers (the workload seam, D7) arrive with the DAGs through git-sync (D23) at
# /opt/airflow/dags/repo/airflow/include, which comes first on PYTHONPATH; the baked copy is the
# fallback for the host-path dev overlay, where only airflow/dags is mounted.
COPY --chown=airflow:0 include/ /opt/airflow/include/
ENV PYTHONPATH=/opt/airflow/dags/repo/airflow/include:/opt/airflow/include
