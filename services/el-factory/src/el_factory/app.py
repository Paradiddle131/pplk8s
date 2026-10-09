from __future__ import annotations

import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests
from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

from el_factory.config import Config
from el_factory.errors import ApiError, BadRequest, NotFound, UpstreamError
from el_factory.model import Interval
from el_factory.sources import build_registry, load_catalog
from el_factory.staging import object_uri, read_staged, stage_page
from el_factory.storage import GcsStorage, Storage
from el_factory.warehouse import PageLoad, PostgresWarehouse, Warehouse

RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9_.:+-]+")
CURSOR_PATTERN = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class ExtractRequest:
    source: str
    entity: str
    run_id: str
    interval: Interval
    cursor: int


def create_app(config: Config, storage: Storage, warehouse: Warehouse) -> Flask:
    registry = build_registry(config.page_size, config.open_meteo_url)
    catalog = load_catalog(config.catalog_path, registry)
    app = Flask(__name__)

    @app.errorhandler(ApiError)
    def api_error(exc: ApiError) -> tuple[Response, int]:
        return _error(exc.status, exc.message, exc.retryable)

    @app.errorhandler(requests.RequestException)
    def upstream_failure(exc: requests.RequestException) -> tuple[Response, int]:
        return _error(503, f"upstream request failed: {exc}", retryable=True)

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException) -> tuple[Response, int]:
        return _error(exc.code or 500, exc.description or exc.name, retryable=False)

    @app.errorhandler(Exception)
    def unexpected(exc: Exception) -> tuple[Response, int]:
        app.logger.exception("unexpected error", exc_info=exc)
        return _error(500, "internal error", retryable=False)

    @app.get("/healthz")
    def healthz() -> Response:
        return jsonify({"status": "ok"})

    @app.get("/catalog")
    def get_catalog() -> Response:
        pipeline = request.args.get("pipeline")
        if not pipeline:
            raise BadRequest("query parameter 'pipeline' is required")
        entries = catalog.get(pipeline)
        if entries is None:
            raise NotFound(f"unknown pipeline: {pipeline}")
        return jsonify([{"source": e.source, "entity": e.entity} for e in entries])

    @app.post("/extract")
    def extract() -> Response:
        # Injected before any work so a retry drill never leaves partial state behind.
        if random.random() < config.fail_rate:
            raise UpstreamError("injected transient failure (FAIL_RATE)")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise BadRequest("request body must be a JSON object")
        parsed = _parse_extract(body, request.args.get("cursor"))
        entity = registry.get(parsed.source, parsed.entity)

        page = entity.fetch(parsed.interval, parsed.cursor)
        uri = object_uri(
            config.gcs_bucket, entity.source, entity.name, parsed.run_id, parsed.cursor
        )
        stage_page(storage, uri, page.rows)

        warehouse.ensure_table(entity.table)
        load = PageLoad(parsed.run_id, parsed.interval, parsed.cursor, uri)
        loaded = warehouse.replace_page(entity.table, load, read_staged(storage, uri))

        next_url = None if page.next_cursor is None else f"/extract?cursor={page.next_cursor}"
        return jsonify(
            {
                "status": "ok",
                "source": entity.source,
                "entity": entity.name,
                "page": parsed.cursor,
                "rows": loaded,
                "object": uri,
                "next_url": next_url,
            }
        )

    return app


def create_app_from_env() -> Flask:
    config = Config.from_env()
    return create_app(
        config,
        GcsStorage.from_config(config),
        PostgresWarehouse(config.warehouse_dsn),
    )


def _error(status: int, message: str, retryable: bool) -> tuple[Response, int]:
    return jsonify({"status": "error", "retryable": retryable, "error": message}), status


def _parse_extract(body: dict[str, Any], query_cursor: str | None) -> ExtractRequest:
    run_id = _required_str(body, "run_id")
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise BadRequest("run_id may contain only letters, digits, and _ . : + -")
    start = _timestamp(body, "interval_start")
    end = _timestamp(body, "interval_end")
    if end <= start:
        raise BadRequest("interval_end must be after interval_start")
    raw_cursor = query_cursor if query_cursor is not None else body.get("cursor")
    return ExtractRequest(
        source=_required_str(body, "source"),
        entity=_required_str(body, "entity"),
        run_id=run_id,
        interval=Interval(start=start, end=end),
        cursor=_cursor(raw_cursor),
    )


def _required_str(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise BadRequest(f"'{key}' is required and must be a non-empty string")
    return value


def _timestamp(body: dict[str, Any], key: str) -> datetime:
    raw = _required_str(body, key)
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise BadRequest(f"'{key}' must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise BadRequest(f"'{key}' must include a timezone offset")
    return parsed.astimezone(UTC)


def _cursor(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise BadRequest("cursor must be a non-negative integer")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and CURSOR_PATTERN.fullmatch(value):
        return int(value)
    raise BadRequest("cursor must be a non-negative integer")
