import asyncio
import importlib
from datetime import UTC, datetime, timedelta

import pytest
from airflow.exceptions import TaskDeferred
from pplk8s import sensors
from pplk8s.sensors import ReadinessSensor, ReadinessTrigger

START = "2026-10-01T00:00:00+00:00"
END = "2026-10-02T00:00:00+00:00"
READY = {"status": "ready", "watermark": "2026-10-01T23:00:00+00:00", "run_id": "run-1"}


def sensor(**kwargs):
    return ReadinessSensor(
        task_id="wait", product="sales.gold", interval_start=START, interval_end=END, **kwargs
    )


def test_trigger_serialises_to_an_importable_classpath_and_round_trips():
    trigger = ReadinessTrigger("sales.gold", START, END, poll_interval=5, conn_id="wh")

    classpath, kwargs = trigger.serialize()
    module, _, name = classpath.rpartition(".")
    rebuilt = getattr(importlib.import_module(module), name)(**kwargs)

    assert classpath == "pplk8s.sensors.ReadinessTrigger"
    assert rebuilt.serialize() == (classpath, kwargs)


def test_trigger_polls_until_ready_and_fires_once(mocker):
    states = iter([None, {**READY, "status": "running"}, READY])
    calls = mocker.patch.object(
        sensors, "readiness_state", side_effect=lambda *a, **k: next(states)
    )
    sleep = mocker.patch.object(sensors.asyncio, "sleep", mocker.AsyncMock())

    async def collect():
        return [event async for event in ReadinessTrigger("sales.gold", START, END).run()]

    events = asyncio.run(collect())

    assert [e.payload for e in events] == [
        {"product": "sales.gold", "watermark": READY["watermark"], "run_id": "run-1"}
    ]
    assert calls.call_count == 3
    assert sleep.await_count == 2


def test_sensor_returns_at_once_when_the_product_is_already_ready(mocker):
    mocker.patch.object(sensors, "readiness_state", return_value=READY)

    assert sensor().execute({}) == {
        "product": "sales.gold",
        "watermark": READY["watermark"],
        "run_id": "run-1",
    }


def test_sensor_defers_to_the_trigger_with_the_whole_timeout(mocker):
    mocker.patch.object(sensors, "readiness_state", return_value=None)

    with pytest.raises(TaskDeferred) as deferred:
        sensor(timeout=timedelta(minutes=20), poll_interval=7).execute({})

    assert isinstance(deferred.value.trigger, ReadinessTrigger)
    assert deferred.value.trigger.poll_interval == 7
    assert deferred.value.method_name == "execute_complete"
    assert deferred.value.timeout == timedelta(minutes=20)


def test_sensor_passes_datetime_intervals_as_iso_strings(mocker):
    state = mocker.patch.object(sensors, "readiness_state", return_value=None)
    start = datetime(2026, 10, 1, tzinfo=UTC)

    with pytest.raises(TaskDeferred) as deferred:
        sensor().__class__(
            task_id="w", product="p", interval_start=start, interval_end=start + timedelta(days=1)
        ).execute({})

    assert state.call_args.args[1:] == (START, END)
    assert deferred.value.trigger.interval_start == START


def test_execute_complete_returns_the_event_payload():
    payload = {"product": "sales.gold", "watermark": None, "run_id": "r"}
    assert sensor().execute_complete({}, payload) == payload


def test_interval_fields_are_templated():
    assert {"product", "interval_start", "interval_end"} <= set(ReadinessSensor.template_fields)
