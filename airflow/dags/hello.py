"""Phase 3 smoke DAG: one task that reports which pod it ran on."""

import logging
import socket

from airflow.sdk import dag, task

log = logging.getLogger(__name__)


@dag(schedule=None, catchup=False, tags=["phase3"])
def hello():
    @task
    def say_hello() -> str:
        # On the Celery executor the hostname is the worker pod's name (airflow-worker-N).
        hostname = socket.gethostname()
        log.info("hello from %s", hostname)
        return hostname

    say_hello()


hello()
