from returns_asset_watch import summarize

# Shape observed on the cluster on 2026-10-10 (one asset event from one pull of three messages).
EXTRA = {
    "from_trigger": True,
    "payload": {
        "status": "success",
        "message": [
            {
                "ack_id": f"projects/pplk8s/subscriptions/file-arrivals-assetwatcher:{n}",
                "message": {
                    "data": "e30=",
                    "attributes": {
                        "bucketId": "landing",
                        "objectId": name,
                        "objectGeneration": generation,
                        "eventType": "OBJECT_FINALIZE",
                    },
                    "message_id": str(n),
                },
                "delivery_attempt": 0,
            }
            for n, name, generation in (
                (1, "probe/p.jsonl", "1"),
                (2, "returns/2026-10-01.jsonl", "2"),
                (3, "returns/2026-10-01.jsonl", "3"),
            )
        ],
    },
}


def test_summarize_lists_every_message_of_one_asset_event():
    assert summarize(EXTRA) == [
        {"bucket": "landing", "object": "probe/p.jsonl", "generation": "1"},
        {"bucket": "landing", "object": "returns/2026-10-01.jsonl", "generation": "2"},
        {"bucket": "landing", "object": "returns/2026-10-01.jsonl", "generation": "3"},
    ]


def test_summarize_tolerates_an_empty_event():
    assert summarize({}) == []
