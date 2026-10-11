"""Celery config for the lab's workers: Airflow's default plus a backport of a Celery 5.7 fix (#15).

After a broker reconnect, Celery's prefork pool forgets which processes are still running a task:
``Consumer.on_close`` calls ``AsynPool.flush``, which ends with ``_busy_workers.clear()``.
The fair scheduler then writes the next task into the pipe of a process that is mid-task, and it
waits there until that task ends while the other processes sit idle (runbook drill 8b).
Celery fixed this upstream (celery/celery#10346, first released in 5.7.0a1) by trimming the set to
the processes still running an accepted job instead of clearing it; this module applies the same
result to Celery < 5.7 by wrapping ``flush``.
Point ``[celery] celery_config_options`` at ``pplk8s.celery_config.CELERY_CONFIG``; drop both
once the Airflow constraints move to a Celery release with the fix.
Composer manages its own workers, so none of this carries over.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

import celery
from airflow.providers.celery.executors.default_celery import DEFAULT_CELERY_CONFIG
from celery.concurrency.asynpool import AsynPool

FIXED_IN = (5, 7)


def keep_busy_workers(flush: Callable[[AsynPool], None]) -> Callable[[AsynPool], None]:
    """Wrap ``AsynPool.flush`` so processes still running an accepted job stay marked busy."""

    @wraps(flush)
    def wrapper(pool: AsynPool) -> None:
        busy = set(pool._busy_workers)
        try:
            flush(pool)
        finally:
            still_busy = set()
            for job in pool._cache.values():
                proc = job._write_to or job._scheduled_for
                if job._accepted and proc is not None and proc._is_alive():
                    still_busy.add(proc.inqW_fd)
            # Only fds that were busy before the flush come back, so a dead or idle process is
            # never sidelined; this equals upstream's intersection_update after the clear.
            pool._busy_workers.update(busy & still_busy)

    wrapper.keeps_busy_workers = True
    return wrapper


def patch_asynpool() -> bool:
    """Apply :func:`keep_busy_workers` once, on Celery releases without the upstream fix."""
    if celery.VERSION[:2] >= FIXED_IN or getattr(AsynPool.flush, "keeps_busy_workers", False):
        return False
    AsynPool.flush = keep_busy_workers(AsynPool.flush)
    return True


patch_asynpool()
CELERY_CONFIG = DEFAULT_CELERY_CONFIG
