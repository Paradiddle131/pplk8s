from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    warehouse_dsn: str
    storage_emulator_host: str | None
    gcs_bucket: str
    gcp_project: str
    page_size: int
    fail_rate: float
    catalog_path: Path
    open_meteo_url: str
    port: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Config:
        warehouse_dsn = env.get("WAREHOUSE_DSN", "").strip()
        if not warehouse_dsn:
            raise ConfigError("WAREHOUSE_DSN is required")
        fail_rate = _float(env, "FAIL_RATE", 0.0)
        if not 0.0 <= fail_rate <= 1.0:
            raise ConfigError("FAIL_RATE must be between 0 and 1")
        page_size = _int(env, "PAGE_SIZE", 100)
        if page_size < 1:
            raise ConfigError("PAGE_SIZE must be at least 1")
        return cls(
            warehouse_dsn=warehouse_dsn,
            storage_emulator_host=env.get("STORAGE_EMULATOR_HOST") or None,
            gcs_bucket=env.get("GCS_BUCKET", "staging"),
            gcp_project=env.get("GCP_PROJECT", "pplk8s"),
            page_size=page_size,
            fail_rate=fail_rate,
            catalog_path=Path(env.get("CATALOG_PATH", str(_default_catalog_path()))),
            open_meteo_url=env.get("OPEN_METEO_URL", DEFAULT_OPEN_METEO_URL),
            port=_int(env, "PORT", 8080),
        )


def _default_catalog_path() -> Path:
    # Repo layout: services/el-factory/catalog.yaml; image layout: /app/catalog.yaml.
    return Path(__file__).resolve().parents[2] / "catalog.yaml"


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def _float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number") from exc
