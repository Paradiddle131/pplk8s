"""Deferrable wait on the readiness ledger: how a consumer DAG waits for another pipeline (D19).

The wait reads ``ops.readiness`` in the warehouse, not Airflow Assets: the ledger is shared with
producers outside this Airflow deployment, carries the watermark, and survives a move to Composer.

While waiting, the task holds no worker slot: :class:`ReadinessSensor` checks once on the worker,
then defers to :class:`ReadinessTrigger`, which polls from the triggerer.  The trigger calls the
same synchronous ledger query in a thread (``sync_to_async``), so there is one query to test.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

from airflow.sdk.bases.sensor import BaseSensorOperator
from airflow.triggers.base import BaseTrigger, TriggerEvent
from asgiref.sync import sync_to_async

from pplk8s.readiness import DEFAULT_CONN_ID, readiness_state

READY = "ready"
DEFAULT_POLL_SECONDS = 30.0


def _iso(value: str | datetime) -> str:
    return value.isoformat() if isinstance(value, datetime) else value


def _ready(product: str, state: dict[str, Any] | None) -> dict[str, Any] | None:
    if state is None or state["status"] != READY:
        return None
    return {"product": product, "watermark": state["watermark"], "run_id": state["run_id"]}


class ReadinessTrigger(BaseTrigger):
    """Fire once ``product`` is ``ready`` for the interval, polling every ``poll_interval`` s."""

    def __init__(
        self,
        product: str,
        interval_start: str,
        interval_end: str,
        poll_interval: float = DEFAULT_POLL_SECONDS,
        conn_id: str = DEFAULT_CONN_ID,
    ) -> None:
        super().__init__()
        self.product = product
        self.interval_start = interval_start
        self.interval_end = interval_end
        self.poll_interval = poll_interval
        self.conn_id = conn_id

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return (
            f"{type(self).__module__}.{type(self).__qualname__}",
            {
                "product": self.product,
                "interval_start": self.interval_start,
                "interval_end": self.interval_end,
                "poll_interval": self.poll_interval,
                "conn_id": self.conn_id,
            },
        )

    async def run(self) -> AsyncIterator[TriggerEvent]:
        check = sync_to_async(readiness_state)
        while True:
            state = await check(
                self.product, self.interval_start, self.interval_end, conn_id=self.conn_id
            )
            ready = _ready(self.product, state)
            if ready is not None:
                yield TriggerEvent(ready)
                return
            self.log.info(
                "%s not ready for [%s, %s): %s",
                self.product,
                self.interval_start,
                self.interval_end,
                state["status"] if state else "no ledger row",
            )
            await asyncio.sleep(self.poll_interval)


class ReadinessSensor(BaseSensorOperator):
    """Wait until ``product`` is ``ready`` in ``ops.readiness`` for one interval.

    Returns (and pushes to XCom) ``{product, watermark, run_id}`` of the producer's ledger row.
    ``timeout`` bounds the whole wait; past it the task fails.
    """

    template_fields = ("product", "interval_start", "interval_end")

    def __init__(
        self,
        *,
        product: str,
        interval_start: str | datetime,
        interval_end: str | datetime,
        poll_interval: float = DEFAULT_POLL_SECONDS,
        timeout: timedelta = timedelta(hours=6),
        deferrable: bool = True,
        conn_id: str = DEFAULT_CONN_ID,
        **kwargs: Any,
    ) -> None:
        super().__init__(poke_interval=poll_interval, timeout=timeout, **kwargs)
        self.product = product
        self.interval_start = interval_start
        self.interval_end = interval_end
        self.poll_interval = poll_interval
        self.deferrable = deferrable
        self.conn_id = conn_id

    def _state(self) -> dict[str, Any] | None:
        return _ready(
            self.product,
            readiness_state(
                self.product,
                _iso(self.interval_start),
                _iso(self.interval_end),
                conn_id=self.conn_id,
            ),
        )

    def poke(self, context: Any) -> bool:
        return self._state() is not None

    def execute(self, context: Any) -> dict[str, Any] | None:
        ready = self._state()
        if ready is not None:
            return ready
        if not self.deferrable:
            super().execute(context)
            return self._state()
        self.defer(
            trigger=ReadinessTrigger(
                self.product,
                _iso(self.interval_start),
                _iso(self.interval_end),
                poll_interval=self.poll_interval,
                conn_id=self.conn_id,
            ),
            method_name="execute_complete",
            timeout=timedelta(seconds=self.timeout),
        )

    def execute_complete(self, context: Any, event: dict[str, Any]) -> dict[str, Any]:
        self.log.info("%s ready: %s", self.product, event)
        return event
