"""ADK's custom services for the agents directory: `adk api_server` and `adk web` import this file
from the directory they serve (google/adk/cli/service_registry.py, `load_services_module`).

It registers the session scheme `firestore://`, so `SESSION_SERVICE_URI` stays the one seam for
where sessions live (semantic/PLAN.md SL-2, SL-13): the lab's Postgres (`postgresql+asyncpg://...`,
ADK's own scheme) or, on GCP, Firestore through ADK's `FirestoreSessionService` (#209).
- `firestore://` is the project's `(default)` database, the free one; `firestore://<database>`
  names another.
- The project is `GCP_PROJECT` when set, else the credentials' own; `FIRESTORE_EMULATOR_HOST`
  points the client at an emulator, as for any Firestore client.
- ADK's `ADK_FIRESTORE_ROOT_COLLECTION` names the root collection (default `adk-session`).

ADK only logs a services.py that fails to import and then hands an unknown scheme to SQLAlchemy,
so nothing here imports Firestore until the scheme is used: an image without google-cloud-firestore
(the local one) still loads this file. tests/test_session_services.py holds it.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from google.adk.cli.service_registry import get_service_registry
from google.adk.sessions.base_session_service import BaseSessionService

SCHEME = "firestore"


def firestore_session_service(uri: str, **_: Any) -> BaseSessionService:
    """ADK's FirestoreSessionService on the database the URI names (empty: `(default)`)."""
    from google.adk.integrations.firestore import FirestoreSessionService
    from google.cloud import firestore

    database = urlparse(uri).netloc or None
    client = firestore.AsyncClient(project=os.environ.get("GCP_PROJECT") or None, database=database)
    return FirestoreSessionService(client=client)


get_service_registry().register_session_service(SCHEME, firestore_session_service)
