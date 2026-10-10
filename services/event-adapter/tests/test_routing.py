import pytest

from event_adapter.routing import (
    MAX_RUN_ID,
    ConfigError,
    Ignore,
    Route,
    Trigger,
    decide,
    load_routes,
    run_id_for,
)

ROUTES = [Route("landing", "returns/", "returns_file_arrival")]
ATTRS = {
    "eventType": "OBJECT_FINALIZE",
    "bucketId": "landing",
    "objectId": "returns/2026-10-01.jsonl",
    "objectGeneration": "1791621017135916",
    "payloadFormat": "JSON_API_V1",
}


def test_a_routed_finalize_event_becomes_a_trigger_with_the_event_as_conf():
    decision = decide(ATTRS, ROUTES)

    assert isinstance(decision, Trigger)
    assert decision.dag_id == "returns_file_arrival"
    assert decision.conf == {
        "bucket": "landing",
        "object": "returns/2026-10-01.jsonl",
        "generation": "1791621017135916",
    }
    assert decision.run_id.startswith("gcs__landing__returns_2026-10-01.jsonl__1791621017135916__")


def test_the_same_generation_always_maps_to_the_same_run_id():
    assert decide(ATTRS, ROUTES) == decide(dict(ATTRS), ROUTES)


def test_a_new_generation_gets_a_new_run_id():
    newer = decide({**ATTRS, "objectGeneration": "1791621017135917"}, ROUTES)
    assert newer.run_id != decide(ATTRS, ROUTES).run_id


def test_objects_with_the_same_slug_get_different_run_ids():
    assert run_id_for("landing", "a/b", "1") != run_id_for("landing", "a_b", "1")


def test_run_ids_stay_short_and_airflow_safe_for_long_names():
    run_id = run_id_for("landing", "returns/" + "x" * 400 + ".jsonl", "1791621017135916")
    assert len(run_id) <= MAX_RUN_ID
    assert run_id.endswith("__1791621017135916__" + run_id[-8:])
    assert all(c.isalnum() or c in "_.-" for c in run_id)


@pytest.mark.parametrize(
    "attrs",
    [
        {**ATTRS, "eventType": "OBJECT_DELETE"},
        {**ATTRS, "objectId": "other/2026-10-01.jsonl"},
        {**ATTRS, "bucketId": "staging"},
        {**ATTRS, "objectGeneration": "abc"},
        {**ATTRS, "objectGeneration": ""},
        {"eventType": "OBJECT_FINALIZE"},
    ],
)
def test_unrouted_or_incomplete_events_are_ignored(attrs):
    assert isinstance(decide(attrs, ROUTES), Ignore)


def test_load_routes_parses_the_config(tmp_path):
    path = tmp_path / "routes.yaml"
    path.write_text(
        "routes:\n  - {bucket: landing, prefix: returns/, dag_id: returns_file_arrival}\n"
    )
    assert load_routes(path) == ROUTES


@pytest.mark.parametrize(
    "text", ["", "routes: []\n", "routes:\n  - {bucket: landing, prefix: returns/}\n", "- a\n"]
)
def test_bad_route_files_are_config_errors(tmp_path, text):
    path = tmp_path / "routes.yaml"
    path.write_text(text)
    with pytest.raises(ConfigError):
        load_routes(path)
