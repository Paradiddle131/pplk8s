"""The BigQuery emulator's front door (semantic/PLAN.md SL-7): forwards every request to the
emulator and covers the three gaps dbt-bigquery hits there.

- `routines.list` is unsupported, and dbt-bigquery lists routines beside tables in every dataset
  it caches, retrying the emulator's error until it gives up; answer it with an empty list.
- Every job reports `statementType: SELECT`, so after a CREATE dbt reads the job's destination
  table, which a DDL job does not have; report a DDL job as a SCRIPT, as dbt then reads nothing.
- A load job without `sourceFormat` fails ("not support sourceFormat"), where BigQuery reads it as
  CSV, and dbt-bigquery loads seeds without one; give such a job CSV (semantic/PLAN.md SL-18).

Standard library only; the emulator stays the engine, nothing here interprets SQL beyond the
statement's first keyword.
"""

import http.server
import json
import os
import re
import urllib.error
import urllib.request

UPSTREAM = os.environ.get("UPSTREAM", "http://bigquery:9050")
PORT = int(os.environ.get("PORT", "9050"))
ROUTINES = re.compile(r"/datasets/[^/]+/routines(\?|$)")
DDL = ("create", "drop", "alter")
REQUEST_SKIP = {"host", "content-length", "accept-encoding"}
RESPONSE_SKIP = {"transfer-encoding", "content-length", "connection"}


def first_keyword(sql: str) -> str:
    """The statement's first word, past leading comments (dbt prefixes a /* {...} */ header)."""
    sql = sql.lstrip()
    while sql.startswith(("/*", "--")):
        end = "*/" if sql.startswith("/*") else "\n"
        sql = sql.split(end, 1)[-1].lstrip()
    return sql.split(None, 1)[0].lower() if sql else ""


def relabel(body: bytes) -> bytes:
    """A job resource whose query is DDL, reported as a SCRIPT; any other body unchanged."""
    try:
        job = json.loads(body)
    except ValueError:
        return body
    stats = job.get("statistics", {}).get("query") if isinstance(job, dict) else None
    sql = (
        job.get("configuration", {}).get("query", {}).get("query", "") if stats else ""
    )
    if stats is None or first_keyword(sql) not in DDL:
        return body
    stats["statementType"] = "SCRIPT"
    return json.dumps(job).encode()


def default_source_format(body: bytes) -> bytes:
    """A load job's configuration without sourceFormat given BigQuery's default, CSV."""
    try:
        job = json.loads(body)
    except ValueError:
        return body
    load = job.get("configuration", {}).get("load") if isinstance(job, dict) else None
    if not isinstance(load, dict) or load.get("sourceFormat"):
        return body
    load["sourceFormat"] = "CSV"
    return json.dumps(job).encode()


class Handler(http.server.BaseHTTPRequestHandler):
    def forward(self) -> None:
        if self.command == "GET" and ROUTINES.search(self.path):
            self.reply(200, {"Content-Type": "application/json"}, b'{"routines": []}')
            return
        length = int(self.headers.get("Content-Length") or 0)
        headers = {
            k: v for k, v in self.headers.items() if k.lower() not in REQUEST_SKIP
        }
        data = self.rfile.read(length) if length else None
        if data and self.command == "POST" and "/jobs" in self.path:
            data = default_source_format(data)
        request = urllib.request.Request(
            UPSTREAM + self.path,
            data=data,
            method=self.command,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                code, response_headers, body = (
                    response.status,
                    response.headers,
                    response.read(),
                )
        except urllib.error.HTTPError as error:
            code, response_headers, body = error.code, error.headers, error.read()
        if "/jobs" in self.path:
            body = relabel(body)
        self.reply(code, response_headers, body)

    def reply(self, code, headers, body: bytes) -> None:
        self.send_response(code)
        for key, value in headers.items():
            if key.lower() not in RESPONSE_SKIP:
                self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = forward

    def log_message(self, *args) -> None:
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
