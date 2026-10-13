"""Tiny synthetic TLC files and a local server that answers like the TLC CDN (issue #36).

Never download real files in tests: these mimic the shapes that matter (row groups, the 2024 case
change of ``Airport_fee``, the 2025 ``cbd_congestion_fee``) in a few rows.
"""

from __future__ import annotations

import hashlib
import io
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pyarrow as pa
import pyarrow.parquet as pq

S3_DENIED = (
    b"<?xml version='1.0'?><Error><Code>AccessDenied</Code><Message>Access Denied</Message></Error>"
)
CDN_BLOCKED = b"<html><body>Request blocked. There might be too much traffic.</body></html>"


def yellow_2023(rows: int, row_group: int, month: datetime) -> bytes:
    """Pre-2024 types: int64 ids, double passenger_count, lower-case airport_fee."""
    pickups = [month + timedelta(hours=i) for i in range(rows)]
    table = pa.table(
        {
            "VendorID": pa.array([1 + i % 2 for i in range(rows)], pa.int64()),
            "tpep_pickup_datetime": pa.array(pickups, pa.timestamp("us")),
            "passenger_count": pa.array([1.0] * rows, pa.float64()),
            "PULocationID": pa.array([100 + i for i in range(rows)], pa.int64()),
            "store_and_fwd_flag": pa.array(["N"] * rows, pa.string()),
            "total_amount": pa.array([10.5 + i for i in range(rows)], pa.float64()),
            "airport_fee": pa.array([0.0] * rows, pa.float64()),
        }
    )
    return _parquet(table, row_group)


def yellow_2025(rows: int, row_group: int, month: datetime) -> bytes:
    """2025 types: int32 ids, int64 passenger_count, Airport_fee, cbd_congestion_fee, a null."""
    pickups = [month + timedelta(hours=i) for i in range(rows)]
    table = pa.table(
        {
            "VendorID": pa.array([2] * rows, pa.int32()),
            "tpep_pickup_datetime": pa.array(pickups, pa.timestamp("us")),
            "passenger_count": pa.array([2] * rows, pa.int64()),
            "PULocationID": pa.array([200 + i for i in range(rows)], pa.int32()),
            "store_and_fwd_flag": pa.array(["Y"] * rows, pa.large_string()),
            "total_amount": pa.array([20.0] * rows, pa.float64()),
            "Airport_fee": pa.array([1.75] * rows, pa.float64()),
            "cbd_congestion_fee": pa.array([0.75] * rows, pa.float64()),
            "ehail_fee": pa.nulls(rows),
        }
    )
    return _parquet(table, row_group)


def retyped_flag(rows: int, month: datetime) -> bytes:
    """``store_and_fwd_flag`` as an integer: a change no load job accepts."""
    table = pa.table(
        {
            "VendorID": pa.array([1] * rows, pa.int32()),
            "tpep_pickup_datetime": pa.array([month] * rows, pa.timestamp("us")),
            "store_and_fwd_flag": pa.array([0] * rows, pa.int64()),
        }
    )
    return _parquet(table, rows)


def _parquet(table: pa.Table, row_group: int) -> bytes:
    buffer = io.BytesIO()
    pq.write_table(table, buffer, row_group_size=row_group, compression="zstd")
    return buffer.getvalue()


class TlcServer:
    """Serves ``/trip-data/<name>`` with ETag, byte ranges and If-Match, like CloudFront over S3."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.blocked = False
        self.gets = 0
        server = self

        class Handler(BaseHTTPRequestHandler):
            server_name = "AmazonS3"

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

            def version_string(self) -> str:
                return self.server_name

            def do_HEAD(self) -> None:
                self._answer(body=False)

            def do_GET(self) -> None:
                server.gets += 1
                self._answer(body=True)

            def _answer(self, body: bool) -> None:
                if server.blocked:
                    return self._send(403, CDN_BLOCKED, {"Server": "CloudFront"}, body)
                data = server.files.get(self.path.removeprefix("/trip-data/"))
                if data is None:
                    return self._send(403, S3_DENIED, {"Server": "AmazonS3"}, body)
                etag = f'"{hashlib.md5(data).hexdigest()}"'
                headers = {"ETag": etag, "Accept-Ranges": "bytes", "Server": "AmazonS3"}
                match = self.headers.get("If-Match")
                if match is not None and match != etag:
                    return self._send(412, b"", headers, body)
                wanted = self.headers.get("Range")
                if wanted is None:
                    return self._send(200, data, headers, body)
                start, end = (int(x) for x in wanted.removeprefix("bytes=").split("-"))
                headers["Content-Range"] = f"bytes {start}-{end}/{len(data)}"
                return self._send(206, data[start : end + 1], headers, body)

            def _send(self, status: int, data: bytes, headers: dict, body: bool) -> None:
                self.server_name = headers.pop("Server")
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                if body:
                    self.wfile.write(data)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base_url = f"http://127.0.0.1:{self._httpd.server_port}/trip-data"
        threading.Thread(target=self._httpd.serve_forever, daemon=True).start()

    def publish(self, name: str, data: bytes) -> str:
        self.files[name] = data
        return f"{self.base_url}/{name}"

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
