from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from el_factory.config import ConfigError
from el_factory.errors import NotFound
from el_factory.sources import (
    customer_actions,
    marketing,
    open_meteo,
    partner_outreach,
    recruitment,
    synthetic,
    tlc,
)
from el_factory.sources.base import Entity


@dataclass(frozen=True)
class CatalogEntry:
    source: str
    entity: str


class Registry:
    """Paged entities (``Entity``) and file entities (``tlc.TlcEntity``) by (source, name)."""

    def __init__(self, entities: list[Entity | tlc.TlcEntity]) -> None:
        self._entities = {(e.source, e.name): e for e in entities}
        self._sources = {e.source for e in entities}

    def entities(self) -> list[Entity | tlc.TlcEntity]:
        return list(self._entities.values())

    def get(self, source: str, entity: str) -> Entity | tlc.TlcEntity:
        found = self._entities.get((source, entity))
        if found is not None:
            return found
        if source not in self._sources:
            raise NotFound(f"unknown source: {source}")
        raise NotFound(f"unknown entity: {source}/{entity}")


def build_registry(page_size: int, open_meteo_url: str, tlc_base_url: str) -> Registry:
    return Registry(
        [
            *synthetic.entities(page_size),
            *marketing.entities(page_size),
            *customer_actions.entities(page_size),
            *partner_outreach.entities(page_size),
            *recruitment.entities(page_size),
            *open_meteo.entities(open_meteo_url),
            *tlc.entities(tlc_base_url),
        ]
    )


def load_catalog(path: Path, registry: Registry) -> dict[str, list[CatalogEntry]]:
    """Parse the catalog once at startup; a catalog naming an unknown source is a deploy error."""
    with path.open(encoding="utf-8") as handle:
        document: Any = yaml.safe_load(handle)
    pipelines = document.get("pipelines") if isinstance(document, dict) else None
    if not isinstance(pipelines, dict):
        raise ConfigError(f"{path}: expected a top-level 'pipelines' mapping")
    catalog: dict[str, list[CatalogEntry]] = {}
    for pipeline, items in pipelines.items():
        if not isinstance(items, list):
            raise ConfigError(f"{path}: pipeline {pipeline} must be a list")
        entries = [
            entry for entry in (_catalog_entry(path, pipeline, item) for item in items) if entry
        ]
        for entry in entries:
            try:
                registry.get(entry.source, entry.entity)
            except NotFound as exc:
                raise ConfigError(f"{path}: pipeline {pipeline}: {exc.message}") from exc
        catalog[str(pipeline)] = entries
    return catalog


def _catalog_entry(path: Path, pipeline: object, item: Any) -> CatalogEntry | None:
    """Parse one entry; a disabled entry (enabled: false) yields None and is left out."""
    if not isinstance(item, dict) or "source" not in item or "entity" not in item:
        raise ConfigError(f"{path}: pipeline {pipeline} entries need source and entity")
    enabled = item.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(f"{path}: pipeline {pipeline}: enabled must be true or false")
    return CatalogEntry(str(item["source"]), str(item["entity"])) if enabled else None
