from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from el_factory.config import ConfigError
from el_factory.errors import NotFound
from el_factory.sources import open_meteo, synthetic
from el_factory.sources.base import Entity


@dataclass(frozen=True)
class CatalogEntry:
    source: str
    entity: str


class Registry:
    def __init__(self, entities: list[Entity]) -> None:
        self._entities = {(e.source, e.name): e for e in entities}
        self._sources = {e.source for e in entities}

    def get(self, source: str, entity: str) -> Entity:
        found = self._entities.get((source, entity))
        if found is not None:
            return found
        if source not in self._sources:
            raise NotFound(f"unknown source: {source}")
        raise NotFound(f"unknown entity: {source}/{entity}")


def build_registry(page_size: int, open_meteo_url: str) -> Registry:
    return Registry([*synthetic.entities(page_size), *open_meteo.entities(open_meteo_url)])


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
        entries = [_catalog_entry(path, pipeline, item) for item in items]
        for entry in entries:
            try:
                registry.get(entry.source, entry.entity)
            except NotFound as exc:
                raise ConfigError(f"{path}: pipeline {pipeline}: {exc.message}") from exc
        catalog[str(pipeline)] = entries
    return catalog


def _catalog_entry(path: Path, pipeline: object, item: Any) -> CatalogEntry:
    if not isinstance(item, dict) or "source" not in item or "entity" not in item:
        raise ConfigError(f"{path}: pipeline {pipeline} entries need source and entity")
    return CatalogEntry(str(item["source"]), str(item["entity"]))
