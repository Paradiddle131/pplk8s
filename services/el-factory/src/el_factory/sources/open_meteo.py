"""Open-Meteo archive (public, no auth): one page per fixed location."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, NamedTuple

import requests

from el_factory.errors import UpstreamError, UpstreamRejected
from el_factory.model import Interval, Page, Table
from el_factory.sources.base import Entity, Fetch

SOURCE = "open_meteo"
TIMEOUT_SECONDS = 10
HOURLY_VARIABLES = "temperature_2m,precipitation"
HOURLY_TABLE = Table(
    "open_meteo_hourly_weather",
    (
        ("location", "text"),
        ("latitude", "numeric(8,4)"),
        ("longitude", "numeric(8,4)"),
        ("observed_at", "timestamptz"),
        ("temperature_c", "numeric(5,2)"),
        ("precipitation_mm", "numeric(6,2)"),
    ),
)


class Location(NamedTuple):
    name: str
    latitude: float
    longitude: float


LOCATIONS = (
    Location("Amsterdam", 52.3676, 4.9041),
    Location("Istanbul", 41.0082, 28.9784),
    Location("London", 51.5072, -0.1276),
)


def entities(base_url: str) -> list[Entity]:
    return [Entity(SOURCE, "hourly_weather", HOURLY_TABLE, _hourly_weather(base_url))]


def _hourly_weather(base_url: str) -> Fetch:
    def fetch(interval: Interval, cursor: int) -> Page:
        if cursor >= len(LOCATIONS):
            return Page(rows=[], next_cursor=None)
        location = LOCATIONS[cursor]
        payload = _request_archive(base_url, location, interval)
        rows = _parse_hourly(payload, location, interval)
        next_cursor = cursor + 1 if cursor + 1 < len(LOCATIONS) else None
        return Page(rows=rows, next_cursor=next_cursor)

    return fetch


def _request_archive(base_url: str, location: Location, interval: Interval) -> dict[str, Any]:
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "start_date": interval.start.astimezone(UTC).date().isoformat(),
        "end_date": interval.end.astimezone(UTC).date().isoformat(),
        "hourly": HOURLY_VARIABLES,
        "timezone": "UTC",
    }
    response = requests.get(base_url, params=params, timeout=TIMEOUT_SECONDS)
    if response.status_code >= 500:
        raise UpstreamError(f"open-meteo answered {response.status_code} for {location.name}")
    if response.status_code >= 400:
        raise UpstreamRejected(
            f"open-meteo rejected the request for {location.name}: {response.status_code}"
        )
    return response.json()


def _parse_hourly(
    payload: dict[str, Any], location: Location, interval: Interval
) -> list[dict[str, object]]:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise UpstreamError(f"open-meteo response for {location.name} has no hourly block")
    rows: list[dict[str, object]] = []
    for stamp, temperature, precipitation in zip(
        hourly["time"], hourly["temperature_2m"], hourly["precipitation"], strict=True
    ):
        observed = datetime.fromisoformat(stamp).replace(tzinfo=UTC)
        if not interval.start <= observed < interval.end:
            continue
        rows.append(
            {
                "location": location.name,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "observed_at": observed.isoformat(),
                "temperature_c": temperature,
                "precipitation_mm": precipitation,
            }
        )
    return rows
