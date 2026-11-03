"""GET /publication: is a TLC month published yet? (PLAN.md D34, issue #54)."""

from datetime import datetime

import pytest

from tests.conftest import FakeFileLedger
from tests.tlc_fixtures import TlcServer, yellow_2025

OCT = datetime(2025, 10, 1)


@pytest.fixture
def warehouse() -> FakeFileLedger:
    # The file sources are served only on a warehouse that keeps their ledger.
    return FakeFileLedger()


@pytest.fixture
def server():
    tlc = TlcServer()
    yield tlc
    tlc.close()


@pytest.fixture
def client(make_client, server):
    return make_client(tlc_base_url=server.base_url)


def probe(client, **params):
    query = {"source": "tlc", "entity": "yellow", "month": "2025-10", **params}
    return client.get("/publication", query_string=query)


def test_a_published_month_answers_its_etag_and_size(client, server):
    data = yellow_2025(12, 4, OCT)
    url = server.publish("yellow_tripdata_2025-10.parquet", data)

    response = probe(client)

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "published"
    assert body["source_uri"] == url
    assert body["size"] == len(data)
    assert body["etag"].startswith('"') and body["etag"].endswith('"')
    assert (body["source"], body["entity"], body["month"]) == ("tlc", "yellow", "2025-10")
    assert server.gets == 0  # a HEAD is enough


def test_an_unpublished_month_answers_not_published(client, server):
    response = probe(client, month="2099-01")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "not_published"
    assert body["source_uri"] == f"{server.base_url}/yellow_tripdata_2099-01.parquet"
    assert "etag" not in body


def test_a_cdn_block_is_a_retryable_503_not_unpublished(client, server):
    server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(4, 4, OCT))
    server.blocked = True

    response = probe(client)

    assert response.status_code == 503
    assert response.get_json()["retryable"] is True


@pytest.mark.parametrize("month", ["2025-13", "2025-1", "25-10", "", "2025-10-01"])
def test_a_malformed_month_is_a_400(client, month):
    assert probe(client, month=month).status_code == 400


def test_an_unknown_entity_is_a_404(client):
    assert probe(client, entity="purple").status_code == 404


def test_a_paged_source_has_no_publication(client):
    response = probe(client, source="synthetic", entity="orders")
    assert response.status_code == 400
