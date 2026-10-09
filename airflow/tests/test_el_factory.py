import pytest
import requests
import responses
from airflow.sdk.exceptions import AirflowFailException
from pplk8s.el_factory import ElFactoryHook, ElFactoryTransientError

BASE = "http://el-factory.test:80"
ARGS = (
    "synthetic",
    "orders",
    "manual__2026-10-09T10:00:00+00:00",
    "2026-10-08T00:00:00+00:00",
    "2026-10-09T00:00:00+00:00",
)


def page(rows, next_url=None, **extra):
    return {
        "status": "ok",
        "source": "synthetic",
        "entity": "orders",
        "page": 0,
        "rows": rows,
        "object": "gs://staging/x",
        "next_url": next_url,
        **extra,
    }


@responses.activate
def test_catalog():
    responses.get(
        f"{BASE}/catalog?pipeline=sales",
        json=[{"source": "synthetic", "entity": "orders"}],
    )
    assert ElFactoryHook().get_catalog("sales") == [{"source": "synthetic", "entity": "orders"}]
    assert responses.calls[0].request.params == {"pipeline": "sales"}


@responses.activate
def test_catalog_unknown_pipeline_fails_fast():
    responses.get(
        f"{BASE}/catalog",
        status=404,
        json={"status": "error", "retryable": False, "error": "unknown pipeline"},
    )
    with pytest.raises(AirflowFailException):
        ElFactoryHook().get_catalog("nope")


@responses.activate
def test_catalog_malformed_entries():
    responses.get(f"{BASE}/catalog", json=[{"source": "x"}])
    with pytest.raises(AirflowFailException):
        ElFactoryHook().get_catalog("sales")


@responses.activate
def test_pagination_follows_next_url_with_same_body():
    responses.post(f"{BASE}/extract", json=page(100, "/extract?cursor=1"))
    responses.post(f"{BASE}/extract", json=page(100, f"{BASE}/extract?cursor=2"))
    responses.post(f"{BASE}/extract", json=page(30))
    summary = ElFactoryHook().extract_entity(*ARGS)
    assert summary == {"source": "synthetic", "entity": "orders", "pages": 3, "rows": 230}
    urls = [c.request.url for c in responses.calls]
    assert urls == [f"{BASE}/extract", f"{BASE}/extract?cursor=1", f"{BASE}/extract?cursor=2"]
    bodies = {c.request.body for c in responses.calls}
    assert len(bodies) == 1
    assert b'"run_id": "manual__2026-10-09T10:00:00+00:00"' in bodies.pop()


@pytest.mark.parametrize(
    "body",
    [
        {**page(1), "status": "error"},
        page(-1),
        page("3"),
        page(True),
        page(1, 5),
        {k: v for k, v in page(1).items() if k != "next_url"},
        ["not", "an", "object"],
    ],
)
@responses.activate
def test_invalid_responses_fail_fast(body):
    responses.post(f"{BASE}/extract", json=body)
    with pytest.raises(AirflowFailException):
        ElFactoryHook().extract_entity(*ARGS)


@responses.activate
def test_next_url_on_other_host_is_refused():
    responses.post(f"{BASE}/extract", json=page(1, "http://evil.test/extract?cursor=1"))
    with pytest.raises(AirflowFailException, match="different host"):
        ElFactoryHook().extract_entity(*ARGS)


@responses.activate
def test_non_terminating_pagination_is_refused():
    responses.post(f"{BASE}/extract", json=page(1, "/extract?cursor=1"))
    with pytest.raises(AirflowFailException, match="terminate"):
        ElFactoryHook().extract_entity(*ARGS)


def test_bad_run_id_is_refused_before_any_request():
    with pytest.raises(AirflowFailException):
        ElFactoryHook().extract_entity("a", "b", "bad run id", "s", "e")


@pytest.mark.parametrize(
    ("status", "body", "transient"),
    [
        (503, {"status": "error", "retryable": True, "error": "injected"}, True),
        (500, {"status": "error", "retryable": True, "error": "odd but explicit"}, True),
        (502, {"status": "error", "retryable": False, "error": "source rejected"}, False),
        (500, {"status": "error", "retryable": False, "error": "internal"}, False),
        (400, {"status": "error", "retryable": False, "error": "bad"}, False),
        (404, {"status": "error", "retryable": False, "error": "unknown"}, False),
        (504, None, True),  # gateway during a rollout: no EL Factory body
        (404, None, False),
    ],
)
@responses.activate
def test_error_mapping(status, body, transient):
    responses.post(f"{BASE}/extract", status=status, json=body) if body else responses.post(
        f"{BASE}/extract", status=status, body="gateway"
    )
    expected = ElFactoryTransientError if transient else AirflowFailException
    with pytest.raises(expected) as info:
        ElFactoryHook().extract_entity(*ARGS)
    assert (type(info.value) is ElFactoryTransientError) == transient


@responses.activate
def test_connection_errors_are_transient_and_not_retried_by_the_hook():
    responses.post(f"{BASE}/extract", body=requests.ConnectionError("refused"))
    with pytest.raises(ElFactoryTransientError):
        ElFactoryHook().extract_entity(*ARGS)
    assert len(responses.calls) == 1


@responses.activate
def test_failure_on_later_page_is_transient_and_restart_begins_at_page_zero():
    responses.post(f"{BASE}/extract", json=page(5, "/extract?cursor=1"))
    responses.post(
        f"{BASE}/extract", status=503, json={"status": "error", "retryable": True, "error": "x"}
    )
    hook = ElFactoryHook()
    with pytest.raises(ElFactoryTransientError):
        hook.extract_entity(*ARGS)
    responses.replace(responses.POST, f"{BASE}/extract", json=page(5))
    assert hook.extract_entity(*ARGS)["pages"] == 1
    assert responses.calls[-1].request.url == f"{BASE}/extract"
