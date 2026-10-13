"""Deferrable waits of the seam: on the readiness ledger (D19) and on a source's publication (D35).

**Readiness:** how a consumer DAG waits for another pipeline.

The wait reads ``ops.readiness`` in the warehouse, not Airflow Assets: the ledger is shared with
producers outside this Airflow deployment, carries the watermark, and survives a move to Composer.

While waiting, the task holds no worker slot: :class:`ReadinessSensor` checks once on the worker,
then defers to :class:`ReadinessTrigger`, which polls from the triggerer.  The trigger calls the
same synchronous ledger query in a thread (``sync_to_async``), so there is one query to test.

**Publication:** how ``tlc_monthly`` waits for TLC to publish a month (1-3 months of lag, #36).
:class:`PublicationSensor` asks EL Factory's ``GET /publication`` once on the worker, then defers
to :class:`PublicationTrigger`, which asks again every few hours from the triggerer for up to 120
days.  "Not published" and a retryable failure (a CDN block, EL Factory restarting) both keep the
wait going; a non-retryable answer (unknown entity, malformed reply) ends it as a failure.  The
trigger speaks only HTTP to EL Factory and never touches the metadata DB, so it runs unchanged on
Composer (D12).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

from airflow.sdk.bases.sensor import BaseSensorOperator
from airflow.sdk.exceptions import AirflowFailException
from airflow.triggers.base import BaseTrigger, TriggerEvent
from asgiref.sync import sync_to_async

from pplk8s.el_factory import DEFAULT_CONN_ID as EL_FACTORY_CONN_ID
from pplk8s.el_factory import ElFactoryHook, ElFactoryTransientError
from pplk8s.readiness import DEFAULT_CONN_ID, readiness_state

READY = "ready"
DEFAULT_POLL_SECONDS = 30.0
PUBLICATION_POLL = timedelta(hours=3)
PUBLICATION_TIMEOUT = timedelta(days=120)


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


def _seconds(value: float | timedelta) -> float:
    return value.total_seconds() if isinstance(value, timedelta) else float(value)


class PublicationTrigger(BaseTrigger):
    """Fire once EL Factory reports ``source/entity`` published for ``month`` (``YYYY-MM``).

    The event is ``{status: published, published, source_uri, etag, size}``, or
    ``{status: error, error}`` when EL Factory gives a non-retryable answer.
    """

    def __init__(
        self,
        source: str,
        entity: str,
        month: str,
        poll_interval: float = PUBLICATION_POLL.total_seconds(),
        conn_id: str = EL_FACTORY_CONN_ID,
    ) -> None:
        super().__init__()
        self.source = source
        self.entity = entity
        self.month = month
        self.poll_interval = poll_interval
        self.conn_id = conn_id

    def serialize(self) -> tuple[str, dict[str, Any]]:
        return (
            f"{type(self).__module__}.{type(self).__qualname__}",
            {
                "source": self.source,
                "entity": self.entity,
                "month": self.month,
                "poll_interval": self.poll_interval,
                "conn_id": self.conn_id,
            },
        )

    async def run(self) -> AsyncIterator[TriggerEvent]:
        ask = sync_to_async(ElFactoryHook(self.conn_id).publication)
        while True:
            try:
                answer = await ask(self.source, self.entity, self.month)
            except ElFactoryTransientError as exc:
                self.log.warning(
                    "publication of %s.%s %s: %s", self.source, self.entity, self.month, exc
                )
            except AirflowFailException as exc:
                yield TriggerEvent({"status": "error", "error": str(exc)})
                return
            else:
                if answer["published"]:
                    yield TriggerEvent({"status": "published", **answer})
                    return
                self.log.info("%s.%s %s not published yet", self.source, self.entity, self.month)
            await asyncio.sleep(self.poll_interval)


class PublicationSensor(BaseSensorOperator):
    """Wait until EL Factory reports a file source's data month published (``GET /publication``).

    Returns (and pushes to XCom) ``{published, source_uri, etag, size}``.  ``timeout`` (120 days by
    default) bounds the whole wait; past it the task fails, which is the missing-month alert.
    """

    template_fields = ("source", "entity", "month")

    def __init__(
        self,
        *,
        source: str,
        entity: str,
        month: str,
        poll_interval: float | timedelta = PUBLICATION_POLL,
        timeout: timedelta = PUBLICATION_TIMEOUT,
        deferrable: bool = True,
        conn_id: str = EL_FACTORY_CONN_ID,
        **kwargs: Any,
    ) -> None:
        poll = _seconds(poll_interval)
        super().__init__(poke_interval=poll, timeout=timeout, **kwargs)
        self.source = source
        self.entity = entity
        self.month = month
        self.poll_interval = poll
        self.deferrable = deferrable
        self.conn_id = conn_id

    def _published(self) -> dict[str, Any] | None:
        """The publication if published; None while not published or after a transient error."""
        try:
            answer = ElFactoryHook(self.conn_id).publication(self.source, self.entity, self.month)
        except ElFactoryTransientError as exc:
            self.log.warning("publication check failed, will ask again: %s", exc)
            return None
        return answer if answer["published"] else None

    def poke(self, context: Any) -> bool:
        return self._published() is not None

    def execute(self, context: Any) -> dict[str, Any] | None:
        published = self._published()
        if published is not None:
            return published
        if not self.deferrable:
            super().execute(context)
            return self._published()
        self.defer(
            trigger=PublicationTrigger(
                self.source,
                self.entity,
                self.month,
                poll_interval=self.poll_interval,
                conn_id=self.conn_id,
            ),
            method_name="execute_complete",
            timeout=timedelta(seconds=self.timeout),
        )

    def execute_complete(self, context: Any, event: dict[str, Any]) -> dict[str, Any]:
        if event.get("status") != "published":
            raise AirflowFailException(
                f"{self.source}.{self.entity} {self.month}: {event.get('error', event)}"
            )
        self.log.info("%s.%s %s published: %s", self.source, self.entity, self.month, event)
        return {k: v for k, v in event.items() if k != "status"}
