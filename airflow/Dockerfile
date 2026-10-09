# Airflow image for the lab (PLAN.md D1, D3): the official 3.3.1 image plus the
# provider pins from requirements.txt and the shared `pplk8s` package in include/.
# Build context is this directory: `docker build -t <tag> airflow`.
FROM apache/airflow:3.3.1-python3.12

ARG AIRFLOW_VERSION=3.3.1
ARG PYTHON_VERSION=3.12

COPY --chown=airflow:0 requirements.txt /tmp/requirements.txt

# Install under the upstream constraints so transitive deps match what Airflow
# was tested with. D3 pins Composer's google provider (22.4.0) over the
# constraints' 22.3.0, and 22.4.0 needs google-cloud-aiplatform>=1.164 while the
# constraints freeze 1.163.0, so those two constraint lines are dropped; pip
# still resolves everything else against the remaining constraints.
RUN curl -fsSL -o /tmp/constraints.txt \
      "https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
 && sed -i -E '/^(apache-airflow-providers-google|google-cloud-aiplatform)==/d' /tmp/constraints.txt \
 && pip install --no-cache-dir -r /tmp/requirements.txt -c /tmp/constraints.txt \
 && pip check \
 && rm /tmp/constraints.txt /tmp/requirements.txt

# Shared hooks/helpers (the workload seam, D7) ship in the image, not in the DAG folder.
COPY --chown=airflow:0 include/ /opt/airflow/include/
ENV PYTHONPATH=/opt/airflow/include
