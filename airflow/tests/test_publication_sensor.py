import asyncio
import importlib
from datetime import timedelta

import pytest
from airflow.exceptions import TaskDeferred
from airflow.sdk.exceptions import AirflowFailException
from pplk8s import sensors
from pplk8s.el_factory import ElFactoryTransientError
from pplk8s.sensors import PublicationSensor, PublicationTrigger

PUBLISHED = {"published": True, "source_uri": "u", "etag": '"e"', "size": 1}
NOT_YET = {"published": False, "source_uri": "u"}


def sensor(**kwargs):
    return PublicationSensor(
        task_id="wait", source="tlc", entity="yellow", month="2026-08", **kwargs
    )


def answers(mocker, *results):
    """Patch the hook so each publication() call returns or raises the next result."""
    queue = iter(results)

    def publication(*args, **kwargs):
        result = next(queue)
        if isinstance(result, Exception):
            raise result
        return result

    hook = mocker.patch.object(sensors, "ElFactoryHook")
    hook.return_value.publication.side_effect = publication
    return hook.return_value.publication


def run_trigger(trigger):
    async def collect():
        return [event.payload async for event in trigger.run()]

    return asyncio.run(collect())


def test_trigger_serialises_to_an_importable_classpath_and_round_trips():
    trigger = PublicationTrigger("tlc", "yellow", "2026-08", poll_interval=60, conn_id="elf")

    classpath, kwargs = trigger.serialize()
    module, _, name = classpath.rpartition(".")
    rebuilt = getattr(importlib.import_module(module), name)(**kwargs)

    assert classpath == "pplk8s.sensors.PublicationTrigger"
    assert rebuilt.serialize() == (classpath, kwargs)


def test_trigger_keeps_waiting_through_unpublished_and_cdn_blocks_then_fires(mocker):
    calls = answers(mocker, NOT_YET, ElFactoryTransientError("503 CDN block"), PUBLISHED)
    sleep = mocker.patch.object(sensors.asyncio, "sleep", mocker.AsyncMock())

    events = run_trigger(PublicationTrigger("tlc", "yellow", "2026-08", poll_interval=60))

    assert events == [{"status": "published", **PUBLISHED}]
    assert calls.call_count == 3
    assert [c.args for c in sleep.await_args_list] == [(60,), (60,)]


def test_trigger_reports_a_non_retryable_answer_instead_of_waiting(mocker):
    answers(mocker, AirflowFailException("404 unknown entity"))
    mocker.patch.object(sensors.asyncio, "sleep", mocker.AsyncMock())

    events = run_trigger(PublicationTrigger("tlc", "purple", "2026-08"))

    assert events == [{"status": "error", "error": "404 unknown entity"}]


def test_sensor_returns_at_once_when_the_month_is_published(mocker):
    answers(mocker, PUBLISHED)
    assert sensor().execute({}) == PUBLISHED


@pytest.mark.parametrize("first", [NOT_YET, ElFactoryTransientError("503")])
def test_sensor_defers_with_the_whole_timeout(mocker, first):
    answers(mocker, first)

    with pytest.raises(TaskDeferred) as deferred:
        sensor(poll_interval=timedelta(hours=2), timeout=timedelta(days=120)).execute({})

    assert isinstance(deferred.value.trigger, PublicationTrigger)
    assert deferred.value.trigger.poll_interval == 7200
    assert deferred.value.method_name == "execute_complete"
    assert deferred.value.timeout == timedelta(days=120)


def test_defaults_poll_every_few_hours_for_120_days():
    waiting = sensor()
    assert waiting.poll_interval == timedelta(hours=3).total_seconds()
    assert waiting.timeout == timedelta(days=120).total_seconds()
    assert waiting.deferrable is True


def test_sensor_fails_fast_on_a_non_retryable_first_answer(mocker):
    answers(mocker, AirflowFailException("400 not a file source"))
    with pytest.raises(AirflowFailException):
        sensor().execute({})


def test_execute_complete_returns_the_publication_or_fails_on_error():
    assert sensor().execute_complete({}, {"status": "published", **PUBLISHED}) == PUBLISHED
    with pytest.raises(AirflowFailException):
        sensor().execute_complete({}, {"status": "error", "error": "boom"})


def test_month_and_entity_are_templated():
    assert {"source", "entity", "month"} <= set(PublicationSensor.template_fields)
