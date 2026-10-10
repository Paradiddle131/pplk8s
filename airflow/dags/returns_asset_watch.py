"""Spike (PLAN.md D17): the same GCS object events, delivered by an AssetWatcher, not the adapter.

The triggerer runs the google provider's Pub/Sub pull trigger on its own subscription
(``file-arrivals-assetwatcher``, same topic as the adapter's), and each trigger event becomes an
asset event that schedules this DAG.  The task only logs what arrived; it never loads data, so the
adapter path stays the single writer.  ``docs/events.md`` compares the two paths.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from airflow.providers.common.messaging.triggers.msg_queue import MessageQueueTrigger
from airflow.sdk import Asset, AssetWatcher, dag, get_current_context, task

SUBSCRIPTION = "file-arrivals-assetwatcher"

landing_events = Asset(
    name="landing_object_events",
    watchers=[
        AssetWatcher(
            name="landing_object_events_pubsub",
            trigger=MessageQueueTrigger(
                scheme="google+pubsub",
                project_id="pplk8s",
                subscription=SUBSCRIPTION,
                ack_messages=True,  # acked by the triggerer on pull, before any run exists
                max_messages=10,
                gcp_conn_id="pubsub_emulator",
                poke_interval=5.0,
            ),
        )
    ],
)


def summarize(extra: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact ``{bucket, object, generation}`` per Pub/Sub message carried by one asset event.

    The trigger's payload is ``{"status": ..., "message": [ReceivedMessage, ...]}``: one pull, so
    one asset event (and one run) can carry several object events.
    """
    received = (extra.get("payload") or {}).get("message") or []
    found = []
    for item in received:
        attributes = (item.get("message") or {}).get("attributes") or {}
        found.append(
            {
                "bucket": attributes.get("bucketId"),
                "object": attributes.get("objectId"),
                "generation": attributes.get("objectGeneration"),
            }
        )
    return found


@dag(
    dag_id="returns_asset_watch",
    schedule=[landing_events],
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    tags=["events", "spike", "phase5"],
    default_args={"owner": "data-platform"},
    doc_md=__doc__,
)
def returns_asset_watch():
    @task
    def log_events() -> list[dict[str, Any]]:
        triggering = get_current_context()["triggering_asset_events"]
        seen: list[dict[str, Any]] = []
        for events in triggering.values():
            for event in events:
                extra = dict(event.extra or {})
                print(
                    "asset event extra keys:", sorted(extra), json.dumps(extra, default=str)[:2000]
                )
                seen.extend(summarize(extra))
        print(f"{len(seen)} message(s) in this run:", json.dumps(seen))
        return seen

    log_events()


returns_asset_watch()
