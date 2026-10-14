import re
from pathlib import Path

import pytest
import requests
import responses
from airflow.sdk.exceptions import AirflowFailException
from pplk8s.el_factory import READ_TIMEOUT_SECONDS, ElFactoryHook, ElFactoryTransientError

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
    assert summary == {
        "source": "synthetic",
        "entity": "orders",
        "requests": 3,
        "pages": 3,
        "rows": 230,
    }
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


@responses.activate
def test_time_boxed_responses_count_their_pages():
    responses.post(f"{BASE}/extract", json=page(400, "/extract?cursor=4", pages=4))
    responses.post(f"{BASE}/extract", json=page(150, None, pages=2))
    summary = ElFactoryHook().extract_entity(*ARGS)
    assert (summary["requests"], summary["pages"], summary["rows"]) == (2, 6, 550)


@pytest.mark.parametrize("pages", [-1, "3", True])
@responses.activate
def test_invalid_pages_fail_without_retry(pages):
    responses.post(f"{BASE}/extract", json=page(1, pages=pages))
    with pytest.raises(AirflowFailException):
        ElFactoryHook().extract_entity(*ARGS)


@responses.activate
def test_a_file_already_loaded_answers_zero_pages_and_succeeds():
    """A file source whose version is complete loads nothing and says so (issue #92)."""
    responses.post(f"{BASE}/extract", json=page(0, None, pages=0))
    summary = ElFactoryHook().extract_entity(*ARGS)
    assert (summary["requests"], summary["pages"], summary["rows"]) == (1, 0, 0)


@pytest.mark.parametrize(
    "body",
    [page(0, "/extract?cursor=3", pages=0), page(5, None, pages=0)],
    ids=["no-progress-continuation", "rows-without-pages"],
)
@responses.activate
def test_zero_pages_is_only_valid_as_an_empty_final_answer(body):
    responses.post(f"{BASE}/extract", json=body)
    with pytest.raises(AirflowFailException):
        ElFactoryHook().extract_entity(*ARGS)


def test_el_factory_budget_leaves_room_for_one_overrunning_page():
    """MAX_RUN_TIME (deployed and default) stays at most half the hook's read timeout (D34)."""
    repo = Path(__file__).resolve().parents[2]
    configmap = (repo / "platform/k8s/workloads/el-factory-configmap.yaml").read_text()
    default = (repo / "services/el-factory/src/el_factory/config.py").read_text()
    deployed = float(re.search(r'MAX_RUN_TIME: "([0-9.]+)"', configmap).group(1))
    built_in = float(re.search(r"DEFAULT_MAX_RUN_TIME = ([0-9.]+)", default).group(1))
    for budget in (deployed, built_in):
        assert 0 < budget <= READ_TIMEOUT_SECONDS / 2


PUBLISHED = {
    "status": "published",
    "source": "tlc",
    "entity": "yellow",
    "month": "2026-08",
    "source_uri": "https://cdn.test/trip-data/yellow_tripdata_2026-08.parquet",
    "etag": '"abc-4"',
    "size": 59043961,
}


@responses.activate
def test_publication_of_a_published_month():
    responses.get(f"{BASE}/publication", json=PUBLISHED)
    assert ElFactoryHook().publication("tlc", "yellow", "2026-08") == {
        "published": True,
        "source_uri": PUBLISHED["source_uri"],
        "etag": '"abc-4"',
        "size": 59043961,
    }
    assert responses.calls[0].request.params == {
        "source": "tlc",
        "entity": "yellow",
        "month": "2026-08",
    }


@responses.activate
def test_publication_of_an_unpublished_month():
    responses.get(
        f"{BASE}/publication",
        json={"status": "not_published", "source_uri": PUBLISHED["source_uri"]},
    )
    assert ElFactoryHook().publication("tlc", "yellow", "2026-10") == {
        "published": False,
        "source_uri": PUBLISHED["source_uri"],
    }


@responses.activate
def test_publication_cdn_block_is_transient():
    responses.get(
        f"{BASE}/publication",
        status=503,
        json={"status": "error", "retryable": True, "error": "blocked by the CDN"},
    )
    with pytest.raises(ElFactoryTransientError):
        ElFactoryHook().publication("tlc", "yellow", "2026-08")


@pytest.mark.parametrize(
    "body",
    [
        {"status": "maybe"},
        {**PUBLISHED, "etag": ""},
        {**PUBLISHED, "size": "big"},
        ["published"],
    ],
)
@responses.activate
def test_publication_malformed_answers_fail_fast(body):
    responses.get(f"{BASE}/publication", json=body)
    with pytest.raises(AirflowFailException):
        ElFactoryHook().publication("tlc", "yellow", "2026-08")


def test_publication_rejects_a_malformed_month():
    with pytest.raises(AirflowFailException):
        ElFactoryHook().publication("tlc", "yellow", "2026-8")


@responses.activate
def test_a_spent_budget_stops_before_the_next_continuation_and_retries(mocker):
    # The loop checks the entity's budget between requests: a task retry then resumes (a file
    # source from its chunk ledger), instead of execution_timeout killing a request mid-chunk.
    from pplk8s import el_factory

    clock = iter([0.0, 10.0, 70.0])
    mocker.patch.object(el_factory.time, "monotonic", side_effect=lambda: next(clock))
    responses.post(f"{BASE}/extract", json=page(100, "/extract?cursor=1"))
    responses.post(f"{BASE}/extract", json=page(100, "/extract?cursor=2"))

    with pytest.raises(ElFactoryTransientError, match="budget"):
        ElFactoryHook().extract_entity(*ARGS, budget_seconds=60)
    assert len(responses.calls) == 2


@responses.activate
def test_no_budget_follows_every_continuation():
    responses.post(f"{BASE}/extract", json=page(100, "/extract?cursor=1"))
    responses.post(f"{BASE}/extract", json=page(1))
    assert ElFactoryHook().extract_entity(*ARGS, budget_seconds=None)["requests"] == 2
