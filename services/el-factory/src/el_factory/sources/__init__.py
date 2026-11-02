from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import yaml

from el_factory.config import ConfigError
from el_factory.errors import NotFound
from el_factory.sources import (
    call_transcripts,
    customer_actions,
    marketing,
    open_meteo,
    partner_outreach,
    recruitment,
    synthetic,
)

# Sources a build may leave out: the file sources (el_factory.tlc), served only where the image
# carries them and the warehouse keeps their ledger (semantic/PLAN.md SL-19). Where they are not
# served, the catalog leaves their entries out and a request for one is a 404 that says so.
FILE_SOURCES = frozenset({"tlc"})


class Sourced(Protocol):
    """A registered entity: a paged ``Entity`` or a file source's entity."""

    @property
    def source(self) -> str: ...

    @property
    def name(self) -> str: ...


@dataclass(frozen=True)
class CatalogEntry:
    source: str
    entity: str


class Registry:
    """Paged entities (``Entity``) and file sources' entities by (source, name).

    ``unserved`` names the sources this build leaves out: the catalog drops their entries.
    """

    def __init__(self, entities: Sequence[Sourced], unserved: frozenset[str] = frozenset()) -> None:
        self._entities = {(e.source, e.name): e for e in entities}
        self._sources = {e.source for e in entities}
        self.unserved = unserved - self._sources

    def entities(self) -> list[Sourced]:
        return list(self._entities.values())

    def get(self, source: str, entity: str) -> Sourced:
        found = self._entities.get((source, entity))
        if found is not None:
            return found
        if source in self.unserved:
            raise NotFound(f"{source} is a file source this build does not serve")
        if source not in self._sources:
            raise NotFound(f"unknown source: {source}")
        raise NotFound(f"unknown entity: {source}/{entity}")


def build_registry(
    page_size: int, open_meteo_url: str, file_entities: Sequence[Sourced] | None = None
) -> Registry:
    """The paged sources, and the file sources' entities where the build serves them (else None)."""
    return Registry(
        [
            *synthetic.entities(page_size),
            *marketing.entities(page_size),
            *customer_actions.entities(page_size),
            *partner_outreach.entities(page_size),
            *recruitment.entities(page_size),
            *call_transcripts.entities(page_size),
            *open_meteo.entities(open_meteo_url),
            *(file_entities or ()),
        ],
        unserved=FILE_SOURCES if file_entities is None else frozenset(),
    )


def load_catalog(path: Path, registry: Registry) -> dict[str, list[CatalogEntry]]:
    """Parse the catalog once at startup; a catalog naming an unknown source is a deploy error.

    Entries of a source the build does not serve are left out, and so is a pipeline left empty
    by that (the tlc pipeline where the file sources are not served).
    """
    with path.open(encoding="utf-8") as handle:
        document: Any = yaml.safe_load(handle)
    pipelines = document.get("pipelines") if isinstance(document, dict) else None
    if not isinstance(pipelines, dict):
        raise ConfigError(f"{path}: expected a top-level 'pipelines' mapping")
    catalog: dict[str, list[CatalogEntry]] = {}
    for pipeline, items in pipelines.items():
        if not isinstance(items, list):
            raise ConfigError(f"{path}: pipeline {pipeline} must be a list")
        parsed = [_catalog_entry(path, pipeline, item) for item in items]
        entries = [e for e in parsed if e and e.source not in registry.unserved]
        if not entries and any(e and e.source in registry.unserved for e in parsed):
            continue
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
