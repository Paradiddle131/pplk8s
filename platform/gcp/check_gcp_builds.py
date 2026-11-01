"""SL-19's check (semantic/PLAN.md), offline in `make gcp-validate`: what each GCP image build would carry.

For every image built for GCP (`--build-arg WAREHOUSE=bigquery`), it reads the build's lockfile and fails on a
Postgres package or on a lock that no longer holds a top-level pin, and it walks the files the build's stage copies
(its context, less .dockerignore and the stage's `COPY --exclude`s) and fails on a TLC path. Each image joins
BUILDS in the issue that first builds it for GCP (#206 dbt, #209 the agent, #227 EL Factory).
Run from the repo root; prints one line per problem and exits 1 on any.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILDS = {
    # image: (build context, its lockfile and the top-level pins it was compiled from, the Dockerfile's stage)
    "dbt": ("dbt", "requirements-bigquery.txt", "requirements-bigquery.in", "bigquery"),
}
POSTGRES = re.compile(
    r"^(dbt-postgres|psycopg|psycopg2|psycopg2-binary|psycopg-binary|psycopg-c|psycopg-pool|asyncpg)$"
)
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;]+)")


def pins(path: Path) -> dict[str, str]:
    """Package name (normalised) to version, for every `name==version` line of a requirements file."""
    found = {}
    for line in path.read_text().splitlines():
        if m := PIN.match(line.strip()):
            found[re.sub(r"[-_.]+", "-", m.group(1)).lower()] = m.group(2)
    return found


def excludes(dockerfile: Path, stage: str) -> list[str]:
    """The `--exclude` patterns of the COPY lines in the Dockerfile's `stage`."""
    patterns, current = [], None
    for line in dockerfile.read_text().splitlines():
        if m := re.match(r"^FROM\s+\S+(?:\s+AS\s+(\S+))?", line, re.IGNORECASE):
            current = m.group(1)
        elif current == stage and line.startswith("COPY "):
            patterns += re.findall(r"--exclude=(\S+)", line)
    return patterns


def ignored(path: str, patterns: list[str]) -> bool:
    """Docker's matching, as far as these files use it: a pattern names a path or a directory above it."""
    parts = path.split("/")
    prefixes = ["/".join(parts[: i + 1]) for i in range(len(parts))]
    return any(
        fnmatch.fnmatch(p, pattern.rstrip("/"))
        for pattern in patterns
        for p in prefixes
    )


def problems(root: Path = ROOT) -> list[str]:
    found = []
    for image, (context, lock, top, stage) in BUILDS.items():
        ctx = root / context
        locked, wanted = pins(ctx / lock), pins(ctx / top)
        found += [
            f"{image}: {context}/{lock} holds the Postgres package {name}"
            for name in locked
            if POSTGRES.match(name)
        ]
        found += [
            f"{image}: {context}/{lock} has {name}=={locked.get(name)}, not {top}'s {version}: recompile it"
            for name, version in wanted.items()
            if locked.get(name) != version
        ]
        dockerignore = ctx / ".dockerignore"
        patterns = [
            line.strip()
            for line in (
                dockerignore.read_text().splitlines() if dockerignore.exists() else []
            )
            if line.strip() and not line.startswith("#")
        ]
        stage_excludes = excludes(ctx / "Dockerfile", stage)
        if not stage_excludes:
            found.append(
                f"{image}: {context}/Dockerfile has no COPY --exclude in stage {stage}"
            )
        for file in sorted(f for f in ctx.rglob("*") if f.is_file()):
            path = file.relative_to(ctx).as_posix()
            if not ignored(path, patterns + stage_excludes) and "tlc" in path.lower():
                found.append(
                    f"{image}: the {stage} build copies the TLC path {context}/{path}"
                )
    return found


if __name__ == "__main__":
    out = problems()
    print(
        "\n".join(out)
        or f"gcp builds: {', '.join(BUILDS)} carry no Postgres package and no TLC path"
    )
    sys.exit(1 if out else 0)
