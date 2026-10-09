"""Staged page files: NDJSON with sorted keys, so re-staging the same page writes the same bytes."""

from __future__ import annotations

import json
from typing import Any

from el_factory.storage import Storage


def object_uri(bucket: str, source: str, entity: str, run_id: str, page: int) -> str:
    return f"gs://{bucket}/{source}/{entity}/{run_id}/page-{page:05d}.jsonl"


def stage_page(storage: Storage, uri: str, rows: list[dict[str, Any]]) -> None:
    body = "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    storage.upload(uri, body.encode("utf-8"))


def read_staged(storage: Storage, uri: str) -> list[dict[str, Any]]:
    text = storage.download(uri).decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line]
