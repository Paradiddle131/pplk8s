"""Logging config for remote task logs on the fake-gcs emulator (PLAN.md D22).

Airflow's GCS log writer reads the existing object before appending, and treats a failed read as
"object missing" only when the error text says ``No such object`` (real GCS's wording). fake-gcs
answers the same 404 with ``Not Found``, so every first upload is refused and logs stay local.
This module is Airflow's default logging config with the remote log IO swapped for one that also
recognises the typed ``NotFound`` error. Point ``[logging] logging_config_class`` at
``pplk8s.emulator_logging.LOGGING_CONFIG`` against the emulator only; real GCS needs none of this.
"""

from __future__ import annotations

import attrs
from airflow.config_templates.airflow_local_settings import DEFAULT_LOGGING_CONFIG
from airflow.providers.google.cloud.log.gcs_task_handler import GCSRemoteLogIO
from google.api_core.exceptions import NotFound


@attrs.define
class EmulatorGCSRemoteLogIO(GCSRemoteLogIO):
    """GCS remote log IO that also accepts the emulator's wording of a missing object."""

    @staticmethod
    def no_log_found(exc):
        return isinstance(exc, NotFound) or GCSRemoteLogIO.no_log_found(exc)


LOGGING_CONFIG = DEFAULT_LOGGING_CONFIG
REMOTE_TASK_LOG = EmulatorGCSRemoteLogIO.from_config()
