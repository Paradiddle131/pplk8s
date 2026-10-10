"""Pub/Sub streaming pull -> Airflow REST trigger (PLAN.md D17, D18).

Ack rule: ack once the event is durably handled (run created, run already existed, or the event can
never succeed); nack on anything transient so Pub/Sub redelivers it.  The deterministic run id makes
redelivery safe, so the adapter never needs its own dedupe state.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Protocol

from event_adapter.airflow import AirflowClient, Outcome
from event_adapter.routing import Ignore, Route, decide, load_routes

log = logging.getLogger("event_adapter")


class Message(Protocol):
    message_id: str
    attributes: dict[str, str]

    def ack(self) -> None: ...

    def nack(self) -> None: ...


class Trigger(Protocol):
    def trigger(self, dag_id: str, run_id: str, conf: dict[str, str]) -> tuple[Outcome, str]: ...


@dataclass(frozen=True)
class Config:
    project: str
    subscription: str
    airflow_url: str
    airflow_username: str
    airflow_password: str
    routes_path: Path
    max_messages: int
    health_port: int

    @classmethod
    def from_env(cls) -> Config:
        def required(key: str) -> str:
            value = os.environ.get(key)
            if not value:
                raise SystemExit(f"{key} is required")
            return value

        return cls(
            project=os.environ.get("GCP_PROJECT", "pplk8s"),
            subscription=os.environ.get("SUBSCRIPTION", "file-arrivals"),
            airflow_url=required("AIRFLOW_API_URL"),
            airflow_username=required("AIRFLOW_USERNAME"),
            airflow_password=required("AIRFLOW_PASSWORD"),
            routes_path=Path(os.environ.get("ROUTES_PATH", "/etc/event-adapter/routes.yaml")),
            max_messages=int(os.environ.get("MAX_MESSAGES", "10")),
            health_port=int(os.environ.get("HEALTH_PORT", "8080")),
        )


def handle(message: Message, routes: list[Route], airflow: Trigger) -> str:
    """Decide, trigger, and ack or nack one message; return the outcome name for logging/tests."""
    decision = decide(dict(message.attributes), routes)
    if isinstance(decision, Ignore):
        message.ack()
        _log(logging.INFO, message, "ignored", reason=decision.reason)
        return "ignored"
    outcome, detail = airflow.trigger(decision.dag_id, decision.run_id, decision.conf)
    if outcome is Outcome.RETRY:
        message.nack()
        _log(logging.WARNING, message, outcome.value, dag_id=decision.dag_id, detail=detail)
    else:
        message.ack()
        level = logging.ERROR if outcome is Outcome.REJECTED else logging.INFO
        _log(
            level,
            message,
            outcome.value,
            dag_id=decision.dag_id,
            run_id=decision.run_id,
            detail=detail if outcome is Outcome.REJECTED else None,
        )
    return outcome.value


def _log(level: int, message: Message, outcome: str, **fields: object) -> None:
    record = {
        "outcome": outcome,
        "message_id": message.message_id,
        "object": message.attributes.get("objectId"),
        "generation": message.attributes.get("objectGeneration"),
        **fields,
    }
    log.log(level, json.dumps({k: v for k, v in record.items() if v is not None}))


def serve_health(port: int, healthy: Callable[[], bool]) -> ThreadingHTTPServer:
    class Health(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # http.server calls do_<METHOD>
            ok = self.path == "/healthz" and healthy()
            self.send_response(200 if ok else 503)
            self.end_headers()
            self.wfile.write(b"ok\n" if ok else b"unhealthy\n")

        def log_message(self, *args: object) -> None:  # probes every few seconds; keep logs clean
            pass

    server = ThreadingHTTPServer(("0.0.0.0", port), Health)  # the kubelet probes the pod IP
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    # Imported here so unit tests of handle() never load the gRPC stack.
    from google.cloud import pubsub_v1

    config = Config.from_env()
    routes = load_routes(config.routes_path)
    airflow = AirflowClient(config.airflow_url, config.airflow_username, config.airflow_password)
    subscriber = pubsub_v1.SubscriberClient()  # honours PUBSUB_EMULATOR_HOST
    path = subscriber.subscription_path(config.project, config.subscription)
    future = subscriber.subscribe(
        path,
        callback=lambda message: handle(message, routes, airflow),
        flow_control=pubsub_v1.types.FlowControl(max_messages=config.max_messages),
    )
    serve_health(config.health_port, lambda: not future.done())
    log.info("listening on %s with %d route(s)", path, len(routes))
    with subscriber:
        # Blocks until the stream fails for good; the exception ends the process and the
        # kubelet restarts the pod, which is the whole recovery story.
        future.result()


if __name__ == "__main__":
    main()
