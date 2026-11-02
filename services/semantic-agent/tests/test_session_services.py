"""src/services.py: the firestore:// session scheme, loaded the way `adk api_server` loads it.

ADK logs a services.py that fails to import and goes on, then hands the unknown scheme to
DatabaseSessionService, so a broken file would only show at the first session on Cloud Run: these
tests load it through ADK's own loader and fail on its warning or a missing scheme.
"""

import logging
from pathlib import Path

import pytest
from google.adk.cli import service_registry
from google.adk.cli.utils.agent_loader import AgentLoader
from google.adk.cli.utils.service_factory import create_session_service_from_options
from google.adk.integrations.firestore import FirestoreSessionService

AGENTS_DIR = Path(__file__).resolve().parents[1] / "src"


@pytest.fixture
def registry(monkeypatch, caplog):
    """A fresh registry with the agents directory's services.py loaded by ADK's loader."""
    monkeypatch.setattr(service_registry, "_service_registry_instance", None)
    monkeypatch.delitem(__import__("sys").modules, "services", raising=False)
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:9")  # never dialled: nothing is read
    monkeypatch.setenv("GCP_PROJECT", "pplk8s-lab")
    with caplog.at_level(logging.DEBUG, logger="google_adk"):
        service_registry.load_services_module(str(AGENTS_DIR))
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], caplog.text
    return service_registry.get_service_registry()


def test_the_firestore_scheme_builds_adks_firestore_session_service(registry):
    service = create_session_service_from_options(
        base_dir=AGENTS_DIR, session_service_uri="firestore://"
    )
    assert isinstance(service, FirestoreSessionService)
    assert service.client.project == "pplk8s-lab"
    assert service.client._database == "(default)"


def test_the_uri_names_another_database(registry):
    service = registry.create_session_service("firestore://sessions", agents_dir=str(AGENTS_DIR))
    assert service.client._database == "sessions"


def test_adks_own_schemes_stay(registry):
    assert type(registry.create_session_service("memory://")).__name__ == "InMemorySessionService"


def test_services_py_is_not_an_app():
    assert sorted(AgentLoader(str(AGENTS_DIR)).list_agents()) == ["semantic_agent", "sql_baseline"]
