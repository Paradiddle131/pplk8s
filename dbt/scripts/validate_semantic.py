"""Validate the semantic layer as `mf validate-configs` does, querying the warehouse only for some pipelines.

`mf validate-configs` checks the whole semantic manifest, then queries every semantic model, dimension,
entity, simple metric and metric on the warehouse.  Run inside one pipeline's DAG, that warehouse half
fails until every other domain has loaded at least once (issue #168: `finance_daily` failed on
`silver.bookings` before `marketing_elt` had ever run).  A gate in one pipeline must not wait for
another pipeline's first load.

So this runs MetricFlow's own validators in two halves:

- the manifest half on the whole semantic manifest, as `mf validate-configs` runs it (no warehouse);
- the warehouse half on the semantic models owned by the given pipelines (their models' pipeline tags,
  PLAN.md D20) and the metrics that read only those models, the rest named as out of scope.

With no `--pipelines` it queries every semantic model, as `mf validate-configs` does.

Usage, from dbt/ after `dbt parse`, with the image's pins:
    python scripts/validate_semantic.py [--pipelines sales,returns] [target_dir]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_catalog import SemanticIndex, _pipelines


def scope(index: SemanticIndex, pipelines: set[str] | None) -> tuple[list[str], list[str]]:
    """The semantic models and metrics whose warehouse half runs: all of them without `pipelines`, else
    the models owned by one of the pipelines and the metrics that read only those models."""
    models = sorted(
        name
        for name, tags in index.tags_of_semantic_model.items()
        if pipelines is None or pipelines & set(_pipelines(tags))
    )
    metrics = sorted(
        metric["name"]
        for metric in index.metrics
        if all(model["name"] in models for model in index.models_of_metric(metric))
    )
    return models, metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pipelines", help="comma-separated pipeline tags whose semantic models are queried")
    parser.add_argument("target", nargs="?", default="target")
    args = parser.parse_args(argv)
    pipelines = {name.strip() for name in args.pipelines.split(",") if name.strip()} if args.pipelines else None

    from dbt_metricflow.cli.cli_configuration import CLIConfiguration
    from dbt_metricflow.cli.validation_result_formatter import ValidationResultFormatter
    from metricflow.validation.data_warehouse_model_validator import DataWarehouseModelValidator
    from metricflow_semantic_interfaces.validations.semantic_manifest_validator import SemanticManifestValidator
    from metricflow_semantic_interfaces.validations.validator_helpers import SemanticManifestValidationResults
    from metricflow_semantics.model.dbt_manifest_parser import parse_manifest_from_dbt_generated_manifest

    target = Path(args.target)
    raw = (target / "semantic_manifest.json").read_text()
    index = SemanticIndex(json.loads((target / "manifest.json").read_text()), json.loads(raw))
    manifest = parse_manifest_from_dbt_generated_manifest(manifest_json_string=raw)

    results = [SemanticManifestValidator().validate_semantic_manifest(manifest)]
    print(f"validate_semantic: the semantic manifest, {ValidationResultFormatter.format_summary(results[0])}")

    owners = {pipeline for tags in index.tags_of_semantic_model.values() for pipeline in _pipelines(tags)}
    if pipelines is not None and pipelines - owners:
        # A misspelt pipeline would otherwise query nothing and pass.
        unknown = ", ".join(sorted(pipelines - owners))
        print(f"validate_semantic: no semantic model belongs to {unknown}", file=sys.stderr)
        return 1
    models, metrics = scope(index, pipelines)
    if not results[0].has_blocking_issues:
        # Saved queries are never queried on the warehouse; they would name metrics out of scope.
        scoped = manifest.copy(
            update={
                "semantic_models": [model for model in manifest.semantic_models if model.name in models],
                "metrics": [metric for metric in manifest.metrics if metric.name in metrics],
                "saved_queries": [],
            }
        )
        config = CLIConfiguration()
        config.setup(dbt_project_path=Path(__file__).resolve().parents[1])
        validator = DataWarehouseModelValidator(sql_client=config.sql_client)
        for check in (
            validator.validate_semantic_models,
            validator.validate_dimensions,
            validator.validate_entities,
            validator.validate_simple_metrics,
            validator.validate_metrics,
        ):
            results.append(check(scoped))
        skipped = sorted(set(index.semantic_models) - set(models))
        print(
            f"validate_semantic: queried {len(models)} semantic models and {len(metrics)} metrics on the warehouse"
            + (f" for {', '.join(sorted(pipelines))}" if pipelines else "")
            + (f"; out of scope: {', '.join(skipped)}" if skipped else "")
        )

    merged = SemanticManifestValidationResults.merge(results)
    for issue in merged.errors:
        print(f"• {ValidationResultFormatter.format_validation_issue(issue)}", file=sys.stderr)
    if merged.has_blocking_issues:
        print(f"validate_semantic: FAIL, {ValidationResultFormatter.format_summary(merged)}", file=sys.stderr)
        return 1
    print(f"validate_semantic: ok, {ValidationResultFormatter.format_summary(merged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
