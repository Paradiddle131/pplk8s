from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import requests
from flask import Flask, Response, jsonify, request
from google.api_core import exceptions as gcs_exceptions
from werkzeug.exceptions import HTTPException

from el_factory.config import Config
from el_factory.errors import ApiError, BadRequest, NotFound, Superseded, UpstreamError
from el_factory.model import Interval, Table
from el_factory.sources import Registry, build_registry, files, load_catalog
from el_factory.sources.base import Entity
from el_factory.staging import object_uri, read_staged, stage_page
from el_factory.storage import GcsStorage, Storage
from el_factory.warehouse import FileLedger, FileLoad, PageLoad, Warehouse, WarehouseError
from el_factory.warehouse import warehouse as configured_warehouse

if TYPE_CHECKING:
    from el_factory.tlc.routes import FileSources

RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9_.:+-]+")
CURSOR_PATTERN = re.compile(r"[0-9]+")
GENERATION_PATTERN = re.compile(r"[1-9][0-9]{0,18}")
# GCS bucket naming rules, simplified (no dotted names).
BUCKET_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,61}[a-z0-9]")


@dataclass(frozen=True)
class ExtractRequest:
    source: str
    entity: str
    run_id: str
    interval: Interval
    cursor: int


@dataclass(frozen=True)
class LoadRequest:
    entity: str
    run_id: str
    uri: str
    generation: int


def create_app(
    config: Config,
    storage: Storage,
    warehouse: Warehouse,
    clock: Callable[[], float] = time.monotonic,
) -> Flask:
    file_sources = _file_sources(config, storage, warehouse, clock)
    registry = build_registry(
        config.page_size,
        config.open_meteo_url,
        file_sources.entities() if file_sources else None,
    )
    catalog = load_catalog(config.catalog_path, registry)
    file_registry = files.FileRegistry(files.entities())
    app = Flask(__name__)
    if file_sources:
        app.register_blueprint(file_sources.blueprint(registry))
    landing = _landing_tables(warehouse, registry, file_registry)
    _provision_tables(app, landing)

    @app.errorhandler(ApiError)
    def api_error(exc: ApiError) -> tuple[Response, int]:
        return _error(exc.status, exc.message, exc.retryable, **exc.extra)

    @app.errorhandler(requests.RequestException)
    def upstream_failure(exc: requests.RequestException) -> tuple[Response, int]:
        return _error(503, f"upstream request failed: {exc}", retryable=True)

    # GCS 5xx/429 are transient; the caller's retry is the remedy.
    @app.errorhandler(gcs_exceptions.ServerError)
    @app.errorhandler(gcs_exceptions.TooManyRequests)
    def transient_dependency_failure(exc: Exception) -> tuple[Response, int]:
        app.logger.warning("transient dependency failure: %s", exc)
        return _error(503, f"dependency temporarily unavailable: {exc}", retryable=True)

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException) -> tuple[Response, int]:
        return _error(exc.code or 500, exc.description or exc.name, retryable=False)

    @app.errorhandler(Exception)
    def unexpected(exc: Exception) -> tuple[Response, int]:
        app.logger.exception("unexpected error", exc_info=exc)
        return _error(500, "internal error", retryable=False)

    # The warehouse's errors, whatever its driver: transient ones are retryable, the rest are 500s.
    @app.errorhandler(WarehouseError)
    def warehouse_failure(exc: WarehouseError) -> tuple[Response, int]:
        if exc.transient:
            return transient_dependency_failure(exc)
        return unexpected(exc)

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
        if file_sources and file_sources.owns(entity):
            return jsonify(file_sources.extract(entity, parsed.run_id, parsed.interval))
        assert isinstance(entity, Entity)

        # Time-boxed (D34): load pages until the budget is spent, then hand back the rest as
        # next_url. The first page always runs, so every request makes progress, and the budget
        # is checked between pages, so a request can overrun it by one page.
        started = clock()
        _ensure(landing)
        cursor, pages, loaded, uri = parsed.cursor, 0, 0, ""
        while True:
            page = entity.fetch(parsed.interval, cursor)
            uri = object_uri(config.gcs_bucket, entity.source, entity.name, parsed.run_id, cursor)
            stage_page(storage, uri, page.rows)
            load = PageLoad(parsed.run_id, parsed.interval, cursor, uri)
            loaded += warehouse.replace_page(entity.table, load, read_staged(storage, uri))
            pages += 1
            if page.next_cursor is None or clock() - started >= config.max_run_time:
                break
            cursor = page.next_cursor

        next_url = None if page.next_cursor is None else f"/extract?cursor={page.next_cursor}"
        return jsonify(
            {
                "status": "ok",
                "source": entity.source,
                "entity": entity.name,
                "page": parsed.cursor,
                "pages": pages,
                "rows": loaded,
                "object": uri,
                "next_url": next_url,
            }
        )

    @app.post("/load")
    def load() -> Response:
        if random.random() < config.fail_rate:
            raise UpstreamError("injected transient failure (FAIL_RATE)")
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise BadRequest("request body must be a JSON object")
        parsed = _parse_load(body)
        entity = file_registry.get(parsed.entity)

        data = storage.download_generation(parsed.uri, parsed.generation)
        if data is None:
            raise Superseded(f"{parsed.uri} generation {parsed.generation} is no longer live")
        rows = files.parse_ndjson(entity, data)

        _ensure(landing)
        loaded = warehouse.replace_file(
            entity.table, FileLoad(parsed.run_id, parsed.uri, parsed.generation), rows
        )
        if loaded is None:
            raise Superseded(f"a newer generation of {parsed.uri} is already loaded")
        return jsonify(
            {
                "status": "ok",
                "entity": entity.name,
                "object": parsed.uri,
                "generation": str(parsed.generation),
                "rows": loaded,
            }
        )

    return app


def _landing_tables(
    warehouse: Warehouse, registry: Registry, file_registry: files.FileRegistry
) -> list[tuple[Callable[[Table], None], Table]]:
    """Every ds_source table dbt reads as a source, with the call that creates it.

    File-source landing tables (tlc) are left out: their first chunk creates them, from the
    file's schema.
    """
    landing = [
        (warehouse.ensure_table, e.table) for e in registry.entities() if isinstance(e, Entity)
    ]
    landing += [(warehouse.ensure_file_table, e.table) for e in file_registry.entities()]
    return landing


def _ensure(landing: list[tuple[Callable[[Table], None], Table]]) -> None:
    # dbt sources expect every ds_source table to exist even before its first extract or load, and
    # one pipeline's dbt build reads tables that another pipeline's extract lands (the weather
    # models are tagged sales, PLAN.md D20). So every extract or load ensures all of them, not
    # only its own: a warehouse reset under a running service would otherwise stay without the
    # tables no request names (issue #172).
    for ensure, table in landing:
        ensure(table)


def _provision_tables(app: Flask, landing: list[tuple[Callable[[Table], None], Table]]) -> None:
    # Best effort: a warehouse outage at boot must not stop the service; each request re-ensures.
    for ensure, table in landing:
        try:
            ensure(table)
        except (WarehouseError, OSError) as exc:
            app.logger.warning("could not provision %s at startup: %s", table.name, exc)


def _file_sources(
    config: Config, storage: Storage, warehouse: Warehouse, clock: Callable[[], float]
) -> FileSources | None:
    """The file sources (el_factory.tlc), where the warehouse keeps their ledger and the build
    carries them with pyarrow (the `files` extra); else None, and no TLC module is imported."""
    if not isinstance(warehouse, FileLedger):
        return None
    try:
        from el_factory.tlc.routes import FileSources
    except ModuleNotFoundError as e:
        if e.name not in ("el_factory.tlc", "pyarrow"):
            raise
        return None
    return FileSources(config, storage, warehouse, clock)


def create_app_from_env() -> Flask:
    config = Config.from_env()
    return create_app(
        config,
        GcsStorage.from_config(config),
        configured_warehouse(config),
    )


def _error(status: int, message: str, retryable: bool, **extra: object) -> tuple[Response, int]:
    return jsonify({"status": "error", "retryable": retryable, "error": message, **extra}), status


def _parse_load(body: dict[str, Any]) -> LoadRequest:
    run_id = _required_str(body, "run_id")
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise BadRequest("run_id may contain only letters, digits, and _ . : + -")
    bucket = _required_str(body, "bucket")
    if not BUCKET_PATTERN.fullmatch(bucket):
        raise BadRequest("bucket is not a valid bucket name")
    name = _required_str(body, "object")
    if name.startswith("/") or "\n" in name:
        raise BadRequest("object must be a relative object name")
    # GCS reports generations as decimal strings (int64); accept either form.
    raw = body.get("generation")
    if isinstance(raw, int) and not isinstance(raw, bool):
        raw = str(raw)
    if not isinstance(raw, str) or not GENERATION_PATTERN.fullmatch(raw):
        raise BadRequest("generation must be a positive integer")
    return LoadRequest(
        entity=_required_str(body, "entity"),
        run_id=run_id,
        uri=f"gs://{bucket}/{name}",
        generation=int(raw),
    )


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
