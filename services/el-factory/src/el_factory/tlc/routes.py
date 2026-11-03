"""What the app serves of the file sources: their entities, their `/extract`, and a blueprint."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Blueprint, Response, jsonify, request

from el_factory.config import Config
from el_factory.errors import BadRequest
from el_factory.model import Interval
from el_factory.sources import Registry
from el_factory.storage import Storage
from el_factory.tlc import retention
from el_factory.tlc.chunks import extract_file
from el_factory.tlc.remote_file import NotPublished, head
from el_factory.tlc.source import MONTH_PATTERN, TlcEntity, entities, parse_month
from el_factory.warehouse import FileLedger


class FileSources:
    def __init__(
        self,
        config: Config,
        storage: Storage,
        warehouse: FileLedger,
        clock: Callable[[], float],
    ) -> None:
        self._config = config
        self._storage = storage
        self._warehouse = warehouse
        self._clock = clock

    def entities(self) -> list[TlcEntity]:
        return entities(self._config.tlc_base_url)

    def owns(self, entity: object) -> bool:
        return isinstance(entity, TlcEntity)

    def extract(self, entity: TlcEntity, run_id: str, interval: Interval) -> dict[str, Any]:
        # File sources resume from the chunk ledger, not from the cursor (D34).
        return extract_file(
            entity,
            run_id,
            interval,
            bucket=self._config.gcs_bucket,
            storage=self._storage,
            warehouse=self._warehouse,
            max_run_time=self._config.max_run_time,
            clock=self._clock,
        )

    def blueprint(self, registry: Registry) -> Blueprint:
        routes = Blueprint("file_sources", __name__)
        warehouse = self._warehouse

        @routes.get("/publication")
        def publication() -> Response:
            # Is a file source's month published yet (D34)? One HEAD, no download. S3's
            # AccessDenied answers not_published; a CDN block or an upstream failure is a retryable
            # 503, so a waiting sensor keeps polling instead of reading a block as "not yet".
            entity = _file_entity(registry, request.args)
            month = parse_month(request.args.get("month"))
            url = entity.url(month)
            answer = {
                "source": entity.source,
                "entity": entity.name,
                "month": month,
                "source_uri": url,
            }
            try:
                remote = head(url)
            except NotPublished:
                return jsonify({"status": "not_published", **answer})
            return jsonify(
                {"status": "published", **answer, "etag": remote.etag, "size": remote.size}
            )

        @routes.get("/months")
        def months() -> Response:
            # The months a file source holds in landing, so the caller can decide what to keep
            # (D35).
            entity = _file_entity(registry, request.args)
            held = retention.held_months(entity, warehouse)
            return jsonify({"source": entity.source, "entity": entity.name, "months": held})

        @routes.post("/retire")
        def retire() -> Response:
            # Deletes every held month not in `keep` from landing and the chunk ledgers (D35, #87).
            # An empty `keep` is refused: retiring everything is never what a run means.
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                raise BadRequest("request body must be a JSON object")
            entity = _file_entity(registry, body)
            keep = body.get("keep")
            if (
                not isinstance(keep, list)
                or not keep
                or not all(isinstance(m, str) and MONTH_PATTERN.fullmatch(m) for m in keep)
            ):
                raise BadRequest(
                    "'keep' is required and must be a non-empty list of YYYY-MM months"
                )
            return jsonify(retention.retire(entity, keep, warehouse))

        return routes


def _file_entity(registry: Registry, params: Any) -> TlcEntity:
    entity = registry.get(_query(params, "source"), _query(params, "entity"))
    if not isinstance(entity, TlcEntity):
        raise BadRequest(f"{entity.source}/{entity.name} is not a file source")
    return entity


def _query(args: Any, key: str) -> str:
    value = args.get(key)
    if not value:
        raise BadRequest(f"query parameter '{key}' is required")
    return str(value)
