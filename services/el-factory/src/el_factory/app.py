from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
import requests
from flask import Flask, Response, jsonify, request
from google.api_core import exceptions as gcs_exceptions
from werkzeug.exceptions import HTTPException

from el_factory import retention
from el_factory.chunks import extract_file
from el_factory.config import Config
from el_factory.errors import ApiError, BadRequest, NotFound, Superseded, UpstreamError
from el_factory.model import Interval, Table
from el_factory.remote_file import NotPublished, head
from el_factory.sources import Registry, build_registry, files, load_catalog, tlc
from el_factory.sources.base import Entity
from el_factory.staging import object_uri, read_staged, stage_page
from el_factory.storage import GcsStorage, Storage
from el_factory.warehouse import FileLoad, PageLoad, PostgresWarehouse, Warehouse

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
    registry = build_registry(config.page_size, config.open_meteo_url, config.tlc_base_url)
    catalog = load_catalog(config.catalog_path, registry)
    file_registry = files.FileRegistry(files.entities())
    app = Flask(__name__)
    landing = _landing_tables(warehouse, registry, file_registry)
    _provision_tables(app, landing)

    @app.errorhandler(ApiError)
    def api_error(exc: ApiError) -> tuple[Response, int]:
        return _error(exc.status, exc.message, exc.retryable, **exc.extra)

    @app.errorhandler(requests.RequestException)
    def upstream_failure(exc: requests.RequestException) -> tuple[Response, int]:
        return _error(503, f"upstream request failed: {exc}", retryable=True)

    # Dropped connections and GCS 5xx/429 are transient; the caller's retry is the remedy.
    @app.errorhandler(psycopg.OperationalError)
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

    @app.get("/publication")
    def publication() -> Response:
        # Is a file source's month published yet (D34)? One HEAD, no download. S3's AccessDenied
        # answers not_published; a CDN block or an upstream failure is a retryable 503, so a
        # waiting sensor keeps polling instead of reading a block as "not yet".
        entity = _file_entity(registry, request.args)
        month = tlc.parse_month(request.args.get("month"))
        url = entity.url(month)
        answer = {"source": entity.source, "entity": entity.name, "month": month, "source_uri": url}
        try:
            remote = head(url)
        except NotPublished:
            return jsonify({"status": "not_published", **answer})
        return jsonify({"status": "published", **answer, "etag": remote.etag, "size": remote.size})

    @app.get("/months")
    def months() -> Response:
        # The months a file source holds in landing, so the caller can decide what to keep (D35).
        entity = _file_entity(registry, request.args)
        held = retention.held_months(entity, warehouse)  # type: ignore[arg-type]
        return jsonify({"source": entity.source, "entity": entity.name, "months": held})

    @app.post("/retire")
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
            or not all(isinstance(m, str) and tlc.MONTH_PATTERN.fullmatch(m) for m in keep)
        ):
            raise BadRequest("'keep' is required and must be a non-empty list of YYYY-MM months")
        return jsonify(retention.retire(entity, keep, warehouse))  # type: ignore[arg-type]

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
        if isinstance(entity, tlc.TlcEntity):
            # File sources resume from the chunk ledger, not from the cursor (D34).
            return jsonify(
                extract_file(
                    entity,
                    parsed.run_id,
                    parsed.interval,
                    bucket=config.gcs_bucket,
                    storage=storage,
                    warehouse=warehouse,  # type: ignore[arg-type]
                    max_run_time=config.max_run_time,
                    clock=clock,
                )
            )

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
        except (psycopg.Error, OSError) as exc:
            app.logger.warning("could not provision %s at startup: %s", table.name, exc)


def create_app_from_env() -> Flask:
    config = Config.from_env()
    return create_app(
        config,
        GcsStorage.from_config(config),
        PostgresWarehouse(config.warehouse_dsn),
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


def _file_entity(registry: Registry, params: Any) -> tlc.TlcEntity:
    entity = registry.get(_query(params, "source"), _query(params, "entity"))
    if not isinstance(entity, tlc.TlcEntity):
        raise BadRequest(f"{entity.source}/{entity.name} is not a file source")
    return entity


def _query(args: Any, key: str) -> str:
    value = args.get(key)
    if not value:
        raise BadRequest(f"query parameter '{key}' is required")
    return str(value)


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
