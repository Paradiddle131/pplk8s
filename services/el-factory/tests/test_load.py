import json

import pytest

from el_factory.sources.files import PARTNER_RETURNS_TABLE

URI = "gs://landing/returns/2026-10-01.jsonl"


def returns_file(*amounts: str) -> bytes:
    lines = [
        {
            "return_id": f"R{i}",
            "order_id": f"O{i}",
            "returned_at": "2026-10-01T12:00:00+00:00",
            "amount": amount,
            "reason": "damaged",
        }
        for i, amount in enumerate(amounts)
    ]
    return "".join(json.dumps(line) + "\n" for line in lines).encode()


def body(gen, **changes):
    values = {
        "entity": "partner_returns",
        "bucket": "landing",
        "object": "returns/2026-10-01.jsonl",
        "generation": str(gen),
        "run_id": "gcs__landing__returns_2026-10-01.jsonl__1",
    }
    values.update(changes)
    return values


def test_load_reads_the_named_generation_and_loads_its_rows(client, storage, warehouse):
    generation = storage.upload(URI, returns_file("10.00", "5.50"))

    response = client.post("/load", json=body(generation))

    assert response.status_code == 200
    assert response.get_json() == {
        "status": "ok",
        "entity": "partner_returns",
        "object": URI,
        "generation": str(generation),
        "rows": 2,
    }
    assert warehouse.row_count("partner_returns") == 2


def test_reloading_the_same_generation_leaves_row_counts_unchanged(client, storage, warehouse):
    generation = storage.upload(URI, returns_file("10.00", "5.50"))

    client.post("/load", json=body(generation))
    client.post("/load", json=body(generation))

    assert warehouse.row_count("partner_returns") == 2


def test_a_new_generation_replaces_the_rows_of_the_object(client, storage, warehouse):
    client.post("/load", json=body(storage.upload(URI, returns_file("10.00", "5.50"))))
    newer = storage.upload(URI, returns_file("1.00"))

    client.post("/load", json=body(newer))

    rows = next(iter(warehouse.tables["partner_returns"].values()))
    assert [(r["amount"], r["_generation"]) for r in rows] == [("1.00", newer)]


def test_an_overwritten_generation_is_superseded_and_not_retryable(client, storage, warehouse):
    old = storage.upload(URI, returns_file("10.00"))
    storage.upload(URI, returns_file("1.00"))

    response = client.post("/load", json=body(old))

    assert response.status_code == 409
    assert response.get_json()["superseded"] is True
    assert response.get_json()["retryable"] is False
    assert warehouse.row_count("partner_returns") == 0


def test_an_older_generation_never_overwrites_a_newer_load(client, storage, warehouse):
    old = storage.upload(URI, returns_file("10.00"))
    newer = storage.upload(URI, returns_file("1.00", "2.00"))
    client.post("/load", json=body(newer))
    # The old bytes were read before the overwrite, so storage would still hand them out.
    storage.generations[URI] = old

    response = client.post("/load", json=body(old))

    assert response.status_code == 409
    assert warehouse.row_count("partner_returns") == 2


@pytest.mark.parametrize(
    "content",
    [b"not json\n", b'{"return_id": "R1"}\n', b"[1, 2]\n", b"\xff\xfe\n"],
)
def test_a_malformed_file_is_422_and_loads_nothing(client, storage, warehouse, content):
    generation = storage.upload(URI, content)

    response = client.post("/load", json=body(generation))

    assert response.status_code == 422
    assert response.get_json()["retryable"] is False
    assert warehouse.row_count("partner_returns") == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"generation": "0"},
        {"generation": "abc"},
        {"generation": True},
        {"bucket": "Bad_Bucket!"},
        {"object": "/abs"},
        {"run_id": "bad id"},
        {"entity": ""},
    ],
)
def test_malformed_load_requests_are_400(client, changes):
    assert client.post("/load", json=body(1, **changes)).status_code == 400


def test_generation_may_be_an_integer(client, storage, warehouse):
    generation = storage.upload(URI, returns_file("10.00"))

    assert client.post("/load", json=body(generation, generation=generation)).status_code == 200


def test_unknown_file_entity_is_404(client):
    assert client.post("/load", json=body(1, entity="nope")).status_code == 404


def test_fail_rate_applies_to_loads_before_any_work(make_client, storage, warehouse):
    generation = storage.upload(URI, returns_file("10.00"))

    response = make_client(fail_rate=1.0).post("/load", json=body(generation))

    assert response.status_code == 503
    assert warehouse.row_count("partner_returns") == 0


def test_startup_provisions_the_file_tables(make_client, warehouse):
    make_client()

    assert PARTNER_RETURNS_TABLE.name in warehouse.ensured
