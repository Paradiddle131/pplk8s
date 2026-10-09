from __future__ import annotations

from typing import Protocol
from urllib.parse import urlsplit

from google.auth.credentials import AnonymousCredentials
from google.cloud import storage

from el_factory.config import Config


class Storage(Protocol):
    def upload(self, uri: str, data: bytes) -> None: ...

    def download(self, uri: str) -> bytes: ...


class GcsStorage:
    """Google Cloud Storage; with STORAGE_EMULATOR_HOST set it talks to fake-gcs-server."""

    def __init__(self, client: storage.Client) -> None:
        self._client = client

    @classmethod
    def from_config(cls, config: Config) -> GcsStorage:
        credentials = AnonymousCredentials() if config.storage_emulator_host else None
        client = storage.Client(project=config.gcp_project, credentials=credentials)
        return cls(client)

    def upload(self, uri: str, data: bytes) -> None:
        bucket, name = _split_gs_uri(uri)
        blob = self._client.bucket(bucket).blob(name)
        blob.upload_from_string(data, content_type="application/x-ndjson")

    def download(self, uri: str) -> bytes:
        bucket, name = _split_gs_uri(uri)
        return self._client.bucket(bucket).blob(name).download_as_bytes()


def _split_gs_uri(uri: str) -> tuple[str, str]:
    parts = urlsplit(uri)
    if parts.scheme != "gs" or not parts.netloc or not parts.path.lstrip("/"):
        raise ValueError(f"not a gs:// object uri: {uri}")
    return parts.netloc, parts.path.lstrip("/")
