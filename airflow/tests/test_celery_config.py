from types import SimpleNamespace

import pplk8s.celery_config as celery_config
from airflow.providers.celery.executors.default_celery import DEFAULT_CELERY_CONFIG
from celery.concurrency.asynpool import AsynPool
from pplk8s.celery_config import CELERY_CONFIG, keep_busy_workers


def proc(fd, alive=True):
    return SimpleNamespace(inqW_fd=fd, _is_alive=lambda: alive)


def job(accepted, write_to=None, scheduled_for=None):
    return SimpleNamespace(_accepted=accepted, _write_to=write_to, _scheduled_for=scheduled_for)


def clearing_flush(pool):
    # What Celery 5.6's AsynPool.flush ends with, whatever else it did.
    pool._busy_workers.clear()


def flushed(busy, jobs):
    pool = SimpleNamespace(_busy_workers=set(busy), _cache=dict(enumerate(jobs)))
    keep_busy_workers(clearing_flush)(pool)
    return pool._busy_workers


def test_a_process_running_an_accepted_job_stays_busy():
    # The drill 8b case: fd 4 runs a long task when the broker reconnects; 1-3 are idle.
    assert flushed({4}, [job(True, write_to=proc(4))]) == {4}


def test_a_job_scheduled_but_not_yet_written_counts_its_target():
    assert flushed({2}, [job(True, scheduled_for=proc(2))]) == {2}


def test_a_job_not_yet_accepted_frees_its_process():
    # flush discards unaccepted jobs; the broker redelivers them.
    assert flushed({3}, [job(False, write_to=proc(3))]) == set()


def test_a_dead_process_is_not_kept_busy():
    # Its fd may already belong to a fresh replacement process.
    assert flushed({4}, [job(True, write_to=proc(4, alive=False))]) == set()


def test_a_process_idle_before_the_flush_is_never_marked_busy():
    assert flushed(set(), [job(True, write_to=proc(4))]) == set()


def test_busy_workers_are_restored_even_when_flush_raises():
    def failing_flush(pool):
        pool._busy_workers.clear()
        raise OSError("broken pipe")

    pool = SimpleNamespace(_busy_workers={4}, _cache={0: job(True, write_to=proc(4))})
    try:
        keep_busy_workers(failing_flush)(pool)
    except OSError:
        pass
    assert pool._busy_workers == {4}


def test_the_installed_celery_is_patched_once():
    # Importing the module patched the installed Celery (5.6, without the upstream fix).
    assert AsynPool.flush.keeps_busy_workers
    patched = AsynPool.flush
    assert not celery_config.patch_asynpool()
    assert AsynPool.flush is patched


def test_celery_with_the_upstream_fix_is_left_alone(monkeypatch):
    monkeypatch.setattr(AsynPool, "flush", clearing_flush)
    monkeypatch.setattr(celery_config, "FIXED_IN", (0, 0))
    assert not celery_config.patch_asynpool()
    assert AsynPool.flush is clearing_flush


def test_config_is_airflows_default():
    assert CELERY_CONFIG is DEFAULT_CELERY_CONFIG
