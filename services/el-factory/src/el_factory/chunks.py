"""One time-boxed ``/extract`` request of a file source: load chunks until the budget is spent.

A chunk is one Parquet row group (D34).
The resume point is never the request's cursor: it is the first chunk ``ops.file_chunks`` has not
recorded for the file's current ``etag``, so a retry without a cursor redoes at most the chunk that
was in flight, and a republished file (new ``etag``) starts over.
The last chunk writes ``ops.file_versions`` and drops every other version's rows.
"""

from __future__ import annotations

import io
import re
import threading
from collections.abc import Callable, Iterator
from typing import Any, Protocol

import pyarrow as pa
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

from el_factory.model import Interval
from el_factory.remote_file import RangeReader, RemoteFile, head
from el_factory.sources.tlc import TlcEntity, chunk_span, data_month, plan_columns
from el_factory.storage import Storage
from el_factory.warehouse import ChunkLoad, FileProgress

# One chunk in flight per gunicorn process: a yellow row group costs ~400 MB while it loads, and
# three concurrent months peaked at 1.24 GiB without this (D35 ceiling: 1 GiB per instance).
# Waiting for the slot counts against the request's MAX_RUN_TIME like the work itself.
CHUNK_SLOT = threading.BoundedSemaphore(1)
CSV_BATCH_ROWS = 100_000  # rows per Arrow batch and per CSV write: bounds memory per chunk


class ChunkWarehouse(Protocol):
    def landing_columns(self, table_name: str) -> dict[str, str]: ...

    def prepare_landing_table(self, table_name: str, add: Any, widen: Any) -> None: ...

    def file_progress(self, source_uri: str, etag: str) -> FileProgress: ...

    def replace_chunk(
        self, table_name: str, load: ChunkLoad, columns: Any, csv: Iterator[bytes]
    ) -> int: ...

    def complete_version(self, table_name: str, source_uri: str, etag: str) -> None: ...


def extract_file(
    entity: TlcEntity,
    run_id: str,
    interval: Interval,
    *,
    bucket: str,
    storage: Storage,
    warehouse: ChunkWarehouse,
    max_run_time: float,
    clock: Callable[[], float],
) -> dict[str, Any]:
    started = clock()
    month = data_month(interval)
    remote = head(entity.url(month))
    progress = warehouse.file_progress(remote.url, remote.etag)
    reader = RangeReader(remote)
    parquet = pq.ParquetFile(reader)
    total = parquet.metadata.num_row_groups

    plan = plan_columns(parquet.schema_arrow, warehouse.landing_columns(entity.table_name))
    warehouse.prepare_landing_table(entity.table_name, plan.add, plan.widen)

    pending = [chunk for chunk in range(total) if chunk not in progress.loaded]
    loaded_chunks, rows, staged = 0, 0, ""
    for chunk in pending:
        load = ChunkLoad(run_id, remote.url, remote.etag, chunk)
        with CHUNK_SLOT:
            staged = _stage_chunk(
                entity, month, remote, chunk, bucket, storage, reader, parquet, plan
            )
            rows += warehouse.replace_chunk(
                entity.table_name,
                load,
                [name for name, _ in plan.columns],
                _csv_parts(storage.download(staged), load),
            )
        loaded_chunks += 1
        if clock() - started >= max_run_time:
            break

    remaining = pending[loaded_chunks:]
    if not remaining and not progress.completed:
        warehouse.complete_version(entity.table_name, remote.url, remote.etag)
    next_url = (
        f"/extract?cursor={remaining[0]}&etag={_clean_etag(remote.etag)}" if remaining else None
    )
    return {
        "status": "ok",
        "source": entity.source,
        "entity": entity.name,
        "page": pending[0] if pending else total,
        "pages": loaded_chunks,
        "rows": rows,
        "object": staged or None,
        "next_url": next_url,
        "source_uri": remote.url,
        "etag": remote.etag,
        "chunks": total,
    }


def _stage_chunk(
    entity: TlcEntity,
    month: str,
    remote: RemoteFile,
    chunk: int,
    bucket: str,
    storage: Storage,
    reader: RangeReader,
    parquet: pq.ParquetFile,
    plan: Any,
) -> str:
    """Read one row group in one ranged GET and stage its typed columns, lower-cased, as Parquet.

    Batch by batch, so a million-row group never sits in memory as one table (D35: 1 GiB).
    """
    order = [name for name, _ in plan.columns]  # the plan's order is the COPY column list
    by_lower = {f.name.lower(): f for f in parquet.schema_arrow}
    schema = pa.schema([by_lower[name].with_name(name) for name in order])
    buffer = io.BytesIO()
    reader.prefetch(*chunk_span(parquet.metadata, chunk))
    try:
        with pq.ParquetWriter(buffer, schema, compression="zstd") as writer:
            for batch in parquet.iter_batches(
                batch_size=CSV_BATCH_ROWS,
                row_groups=[chunk],
                columns=[by_lower[name].name for name in order],
            ):
                writer.write_batch(pa.RecordBatch.from_arrays(batch.columns, schema=schema))
    finally:
        reader.drop_prefetch()
    uri = (
        f"gs://{bucket}/{entity.source}/{entity.name}/{month}/"
        f"{_clean_etag(remote.etag)}/chunk-{chunk:05d}.parquet"
    )
    storage.upload(uri, buffer.getvalue())
    return uri


def _csv_parts(staged: bytes, load: ChunkLoad) -> Iterator[bytes]:
    """The staged chunk as CSV batches: data columns, then the chunk's metadata columns."""
    options = pacsv.WriteOptions(include_header=False)
    for batch in pq.ParquetFile(io.BytesIO(staged)).iter_batches(batch_size=CSV_BATCH_ROWS):
        size = batch.num_rows
        extended = pa.Table.from_batches([batch])
        for name, value, kind in (
            ("_run_id", load.run_id, pa.string()),
            ("_source_uri", load.source_uri, pa.string()),
            ("_etag", load.etag, pa.string()),
            ("_chunk", load.chunk, pa.int32()),
        ):
            extended = extended.append_column(name, pa.repeat(pa.scalar(value, kind), size))
        out = io.BytesIO()
        pacsv.write_csv(extended, out, options)
        yield out.getvalue()


def _clean_etag(etag: str) -> str:
    return re.sub(r"[^A-Za-z0-9-]", "", etag)
