# Airflow on kind (Phase 3)

The official `apache-airflow/airflow` chart, pinned to 1.22.0 in `deploy.sh`, with our 3.3.1 image from `airflow/Dockerfile`.
`make airflow-up` is the single entry point: it builds and pushes the image, creates the secrets, applies the PV/PVC and RBAC, runs `helm upgrade --install`, and ensures the `el_factory` pool (7 slots).
`make airflow-ui` port-forwards the api-server to http://localhost:8080 (login `admin` / `admin`).
`make phase3-check` is the exit check.

## Files

- `values.yaml` holds every chart override; each non-obvious value is commented.
- `manifests.yaml` holds what the chart does not own: the `airflow` and `workloads` namespaces, the hostPath PV and PVC that deliver `airflow/dags` (D10), and the Role and RoleBinding that let the worker and triggerer ServiceAccounts launch pods in `workloads` (D14).
- `deploy.sh` is idempotent and passes extra arguments to `helm upgrade`, for example `./deploy.sh --set workers.celery.replicas=3`.

## Values layout

- Image and executor: `images.airflow`, `executor: CeleryExecutor`, bundled Redis as the broker.
- Metadata DB: the `postgresql` subchart is off. `data.metadataSecretName` names the Secret `airflow-metadata`, whose URL points at PgBouncer.
  PgBouncer connects on to `metadata-db:5432` using `data.metadataConnection` (password injected by `deploy.sh`, never committed).
- Keys: the Fernet key, API secret, and JWT secret live in Secrets generated once by `deploy.sh`, so upgrades never rotate them.
- Connections: Secret `airflow-connections` is mounted as environment variables into every component through `extraEnvFrom` (`AIRFLOW_CONN_EL_FACTORY`, `AIRFLOW_CONN_WAREHOUSE`).
- DAGs: `dags.persistence.existingClaim: airflow-dags`.

## Day-2 practice

- Preview: `helm --kube-context kind-pplk8s -n airflow diff upgrade airflow apache-airflow/airflow --reuse-values --version 1.22.0 --set config.celery.worker_concurrency=8`.
- Upgrade: the same command with `upgrade ... --wait --wait-for-jobs`.
- Rollback: `helm -n airflow history airflow`, then `helm -n airflow rollback airflow <revision> --wait`.
  A rollback creates a new revision that copies the old one.
- `phase3-check.sh` rehearses diff, upgrade, rollback, and a healthy hello run afterwards.

## Database migrations

The chart's migration Job runs `airflow db migrate`, and the `wait-for-airflow-migrations` init container in every other pod blocks until the schema matches that pod's Airflow version.
With the chart's default (Helm hooks), `helm --wait` deadlocks: Helm waits for the pods to be Ready before running the post-install hook, and the pods wait for the hook.
So `values.yaml` turns hooks off for both Jobs, which then run beside the Deployments.
Jobs are immutable, so `deploy.sh` deletes the finished ones before each upgrade.
A rollback restores the old manifests but not the database schema: `airflow db migrate` is forward-only, so roll back only across revisions that do not change the Airflow version (a config or image-revision change is safe, a minor Airflow upgrade needs a metadata DB backup first).
