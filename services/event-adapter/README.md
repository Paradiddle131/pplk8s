# Event adapter

The event adapter is the stand-in for Eventarc: it turns GCS object notifications on Pub/Sub into Airflow DAG runs (PLAN.md D17).
It runs as a Deployment in namespace `workloads` and talks to the Pub/Sub emulator and the Airflow REST API only.

## Behaviour

- It streaming-pulls subscription `file-arrivals` (topic `gcs-object-events`).
- For an `OBJECT_FINALIZE` event whose bucket and object prefix match a route, it calls `POST /api/v2/dags/<dag_id>/dagRuns` with `conf = {bucket, object, generation}` and `logical_date: null`.
- The run id is deterministic: `gcs__<bucket>__<object-slug>__<generation>__<hash8>`, where the hash covers the exact `bucket/object`, so one object generation always maps to one run (D18).
- It acks after Airflow answered 2xx (`triggered`), 409 (`duplicate`, a redelivery), or another 4xx (`rejected`, logged at ERROR); it nacks on 5xx, 404 (DAG not parsed yet), 408/429, and network errors, so Pub/Sub redelivers.
- Events that match no route, or that are not finalize events, are acked and logged as `ignored`.
- Every handled message is one JSON log line with `outcome`, `message_id`, `object`, `generation`, and the DAG and run id.
- `GET /healthz` on `HEALTH_PORT` answers 503 once the streaming pull has stopped; the process also exits then, and the kubelet restarts it.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `AIRFLOW_API_URL` | required | Airflow API base URL, for example `http://airflow-api-server.airflow.svc.cluster.local:8080` |
| `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` | required | Login exchanged for a JWT at `/auth/token`; the token is refreshed once on a 401 |
| `PUBSUB_EMULATOR_HOST` | unset | When set, the Pub/Sub client uses the emulator, for example `pubsub:8085` |
| `GCP_PROJECT` | `pplk8s` | Project of the subscription |
| `SUBSCRIPTION` | `file-arrivals` | Pull subscription to read |
| `ROUTES_PATH` | `/etc/event-adapter/routes.yaml` | `routes: [{bucket, prefix, dag_id}]`; validated at startup |
| `MAX_MESSAGES` | `10` | Flow control: unacked messages in flight |
| `HEALTH_PORT` | `8080` | Port of the health endpoint |

## Tests

```bash
cd services/event-adapter
uv sync
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

The tests cover routing, run-id derivation, the ack/nack table, and the Airflow client's status mapping, with no network.
