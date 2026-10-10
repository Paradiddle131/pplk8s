"""Pure event handling: which GCS events start which DAG, and under which run id (PLAN.md D18).

No I/O here, so every routing and naming rule is unit-tested without Pub/Sub or Airflow.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

FINALIZE = "OBJECT_FINALIZE"
# Airflow's dag_run_id column is 250 characters; keep well inside it.
MAX_RUN_ID = 200
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")
_GENERATION = re.compile(r"[1-9][0-9]{0,18}")


@dataclass(frozen=True)
class Route:
    bucket: str
    prefix: str
    dag_id: str


@dataclass(frozen=True)
class Trigger:
    dag_id: str
    run_id: str
    conf: dict[str, str]


@dataclass(frozen=True)
class Ignore:
    reason: str


class ConfigError(Exception):
    pass


def load_routes(path: Path) -> list[Route]:
    """Parse ``routes: [{bucket, prefix, dag_id}]``; a bad file is a deploy error."""
    document: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = document.get("routes") if isinstance(document, dict) else None
    if not isinstance(items, list) or not items:
        raise ConfigError(f"{path}: expected a non-empty top-level 'routes' list")
    routes = []
    for item in items:
        if not (
            isinstance(item, dict)
            and all(
                isinstance(item.get(k), str) and item[k] for k in ("bucket", "prefix", "dag_id")
            )
        ):
            raise ConfigError(f"{path}: every route needs string bucket, prefix, dag_id: {item!r}")
        routes.append(Route(item["bucket"], item["prefix"], item["dag_id"]))
    return routes


def run_id_for(bucket: str, name: str, generation: str) -> str:
    """Deterministic run id: the same object generation always maps to the same run.

    The readable part is a lossy slug (``/`` becomes ``_``), so a short hash of the exact
    ``bucket/object`` keeps two different objects from ever sharing a run id.
    """
    digest = hashlib.sha256(f"{bucket}/{name}".encode()).hexdigest()[:8]
    slug = _UNSAFE.sub("_", f"{bucket}__{name}")
    tail = f"__{generation}__{digest}"
    return f"gcs__{slug[: MAX_RUN_ID - len(tail) - 5]}{tail}"


def decide(attributes: dict[str, str], routes: list[Route]) -> Trigger | Ignore:
    """Map one Pub/Sub message (GCS notification attributes) to a DAG trigger, or ignore it."""
    if attributes.get("eventType") != FINALIZE:
        return Ignore(f"event type {attributes.get('eventType')!r} is not {FINALIZE}")
    bucket = attributes.get("bucketId", "")
    name = attributes.get("objectId", "")
    generation = attributes.get("objectGeneration", "")
    if not bucket or not name or not _GENERATION.fullmatch(generation):
        return Ignore(f"incomplete GCS notification attributes: {attributes!r}")
    for route in routes:
        if route.bucket == bucket and name.startswith(route.prefix):
            return Trigger(
                dag_id=route.dag_id,
                run_id=run_id_for(bucket, name, generation),
                conf={"bucket": bucket, "object": name, "generation": generation},
            )
    return Ignore(f"no route for gs://{bucket}/{name}")
