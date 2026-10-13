"""A published file read by HTTP byte range, pinned to one ``etag`` (PLAN.md D34).

Every read sends ``If-Match: <etag>``, so a file republished halfway through a month answers 412
instead of mixing two versions; the caller's retry then sees the new ``etag`` and starts over.
Reads are served from one prefetched span per chunk, so a row group costs one GET, which keeps a
backfill well under the CDN's request-rate block (issue #36: ~500 requests in 4 minutes).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import requests

from el_factory.errors import UpstreamError, UpstreamRejected

TIMEOUT = (10, 60)  # connect, read: a stalled CDN edge must fail inside one MAX_RUN_TIME


class NotPublished(UpstreamRejected):
    """The file does not exist (yet); S3 answers 403 AccessDenied for any missing key."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.extra = {"published": False}


class FileChanged(UpstreamError):
    """The file's etag changed mid-read; a retry starts over on the new version."""


@dataclass(frozen=True)
class RemoteFile:
    url: str
    size: int
    etag: str


def head(url: str, session: requests.Session | None = None) -> RemoteFile:
    response = (session or requests).head(url, timeout=TIMEOUT, allow_redirects=True)
    _raise_for_status(url, response)
    etag = response.headers.get("ETag")
    length = response.headers.get("Content-Length")
    if not etag or not length or not length.isdigit():
        raise UpstreamRejected(f"{url}: HEAD lacks ETag or Content-Length")
    if response.headers.get("Accept-Ranges", "").lower() != "bytes":
        raise UpstreamRejected(f"{url}: the server does not accept byte ranges")
    return RemoteFile(url=url, size=int(length), etag=etag)


def classify_403(url: str, response: requests.Response) -> UpstreamError | UpstreamRejected:
    """S3's AccessDenied means not published; CloudFront's own block means slow down (#36)."""
    # A HEAD has no body, so the Server header decides: S3 behind CloudFront says AmazonS3, and
    # CloudFront's own block says CloudFront with an HTML page.
    server = response.headers.get("Server", "")
    if "AmazonS3" in server or b"<Code>AccessDenied</Code>" in response.content[:512]:
        return NotPublished(f"{url}: not published (S3 AccessDenied)")
    return UpstreamError(f"{url}: blocked by the CDN (HTTP 403 from {server or 'unknown'})")


def _raise_for_status(url: str, response: requests.Response) -> None:
    status = response.status_code
    if status in (200, 206):
        return
    if status == 403:
        raise classify_403(url, response)
    if status == 412:
        raise FileChanged(f"{url}: changed while it was being read (ETag no longer matches)")
    if status in (408, 429) or status >= 500:
        raise UpstreamError(f"{url}: HTTP {status}")
    raise UpstreamRejected(f"{url}: HTTP {status}")


class RangeReader(io.RawIOBase):
    """A seekable, read-only file over HTTP ranges of one etag, for ``pyarrow.parquet``."""

    def __init__(self, remote: RemoteFile, session: requests.Session | None = None) -> None:
        super().__init__()
        self._remote = remote
        self._session = session or requests.Session()
        self._pos = 0
        self._span_start = 0
        self._span = b""
        self.requests = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self._remote.size}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    def prefetch(self, start: int, end: int) -> None:
        """Fetch ``[start, end)`` in one request; later reads inside it hit memory."""
        self._span_start, self._span = start, self._get(start, end)

    def drop_prefetch(self) -> None:
        self._span_start, self._span = 0, b""

    def readinto(self, buffer: memoryview) -> int:  # type: ignore[override]
        want = min(len(buffer), self._remote.size - self._pos)
        if want <= 0:
            return 0
        offset = self._pos - self._span_start
        if offset >= 0 and offset + want <= len(self._span):
            data = self._span[offset : offset + want]
        else:
            data = self._get(self._pos, self._pos + want)
        buffer[: len(data)] = data
        self._pos += len(data)
        return len(data)

    def _get(self, start: int, end: int) -> bytes:
        headers = {"Range": f"bytes={start}-{end - 1}", "If-Match": self._remote.etag}
        self.requests += 1
        response = self._session.get(self._remote.url, headers=headers, timeout=TIMEOUT)
        _raise_for_status(self._remote.url, response)
        if response.status_code != 206 or len(response.content) != end - start:
            raise UpstreamError(
                f"{self._remote.url}: asked for {end - start} bytes at {start}, "
                f"got HTTP {response.status_code} with {len(response.content)}"
            )
        return response.content
