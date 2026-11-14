from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from el_factory.warehouse import IMPLEMENTATIONS

DEFAULT_OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_MAX_RUN_TIME = 45.0
# NYC TLC trip files (D34); the one host the TLC page links to (issue #36).
DEFAULT_TLC_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
# Bytes one BigQuery query job may bill: platform/gcp/free-path.yaml's
# caps.bigquery_maximum_bytes_billed (1 GiB), as dbt's `gcp` output and the agent.
DEFAULT_MAXIMUM_BYTES_BILLED = 1073741824


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
    max_run_time: float
    catalog_path: Path
    open_meteo_url: str
    tlc_base_url: str
    port: int
    # The warehouse implementation (warehouse.py, SL-19); warehouse_dsn is its Postgres DSN.
    warehouse: str = "postgres"
    # BigQuery (ELF_WAREHOUSE=bigquery, warehouse_bigquery.py): the emulator's endpoint
    # (BQ_API_ENDPOINT), an access token a proxy injects (GCP_ACCESS_TOKEN; else application
    # default credentials), and every query job's byte cap (BQ_MAXIMUM_BYTES_BILLED).
    bigquery_endpoint: str | None = None
    gcp_access_token: str | None = field(default=None, repr=False)
    bigquery_maximum_bytes_billed: int = DEFAULT_MAXIMUM_BYTES_BILLED

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Config:
        warehouse = env.get("ELF_WAREHOUSE", "").strip() or "postgres"
        if warehouse not in IMPLEMENTATIONS:
            raise ConfigError(
                f"ELF_WAREHOUSE={warehouse!r} is not one of {', '.join(sorted(IMPLEMENTATIONS))}"
            )
        warehouse_dsn = env.get("WAREHOUSE_DSN", "").strip()
        if warehouse == "postgres" and not warehouse_dsn:
            raise ConfigError("WAREHOUSE_DSN is required")
        if warehouse == "bigquery" and not env.get("GCP_PROJECT", "").strip():
            raise ConfigError("GCP_PROJECT is required: the BigQuery warehouse loads that project")
        maximum_bytes_billed = _int(env, "BQ_MAXIMUM_BYTES_BILLED", DEFAULT_MAXIMUM_BYTES_BILLED)
        if maximum_bytes_billed < 1:
            raise ConfigError("BQ_MAXIMUM_BYTES_BILLED must be at least 1")
        fail_rate = _float(env, "FAIL_RATE", 0.0)
        if not 0.0 <= fail_rate <= 1.0:
            raise ConfigError("FAIL_RATE must be between 0 and 1")
        # Seconds a /extract request keeps loading pages before it answers next_url (D34).
        max_run_time = _float(env, "MAX_RUN_TIME", DEFAULT_MAX_RUN_TIME)
        if max_run_time < 0:
            raise ConfigError("MAX_RUN_TIME must not be negative")
        page_size = _int(env, "PAGE_SIZE", 100)
        if page_size < 1:
            raise ConfigError("PAGE_SIZE must be at least 1")
        return cls(
            warehouse=warehouse,
            warehouse_dsn=warehouse_dsn,
            storage_emulator_host=env.get("STORAGE_EMULATOR_HOST") or None,
            gcs_bucket=env.get("GCS_BUCKET", "staging"),
            gcp_project=env.get("GCP_PROJECT", "").strip() or "pplk8s",
            page_size=page_size,
            fail_rate=fail_rate,
            max_run_time=max_run_time,
            catalog_path=Path(env.get("CATALOG_PATH", str(_default_catalog_path()))),
            open_meteo_url=env.get("OPEN_METEO_URL", DEFAULT_OPEN_METEO_URL),
            tlc_base_url=env.get("TLC_BASE_URL", DEFAULT_TLC_BASE_URL),
            port=_int(env, "PORT", 8080),
            bigquery_endpoint=env.get("BQ_API_ENDPOINT") or None,
            gcp_access_token=env.get("GCP_ACCESS_TOKEN") or None,
            bigquery_maximum_bytes_billed=maximum_bytes_billed,
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
