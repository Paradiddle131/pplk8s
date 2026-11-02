"""SL-19's check (semantic/PLAN.md), offline in `make gcp-validate`: what each GCP image build would carry.

For every image built for GCP (`--build-arg WAREHOUSE=bigquery`), it reads the build's lockfile and fails on a
Postgres package, on a package the build leaves out (dbt/requirements-bigquery.exclude) and on a lock that is
stale: one that no longer holds a top-level pin (dbt's, compiled from requirements-bigquery.in) or that differs
from a fresh export of uv.lock (the agent's, `uv export`). It walks the files the build's stage and the stages it
is built on copy, from its context (less .dockerignore) and from its named build contexts (`--build-context
dbt=dbt`), less each COPY's `--exclude`s, and fails on a TLC or a Postgres-only path. Each image joins BUILDS in
the issue that first builds it for GCP (#206 dbt, #209 the agent, #227 EL Factory).
Run from the repo root; prints one line per problem and exits 1 on any.
"""

from __future__ import annotations

import fnmatch
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Build:
    context: str  # the build context, from the repo root
    lock: str  # the lockfile the GCP stage installs, in the context
    stage: str = "bigquery"  # the Dockerfile's GCP stage
    top: str | None = (
        None  # the top-level pins the lock was compiled from, in the context
    )
    export: tuple[
        str, ...
    ] = ()  # the `uv export` arguments that write the lock from uv.lock
    contexts: dict[str, str] = field(
        default_factory=dict
    )  # named build contexts, from the repo root


# What the GCP builds leave out of their locks: dbt-bigquery requires it only for Python models and DataFrames.
EXCLUDED = "dbt/requirements-bigquery.exclude"
BUILDS = {
    "dbt": Build("dbt", "requirements-bigquery.txt", top="requirements-bigquery.in"),
    "semantic-agent": Build(
        "services/semantic-agent",
        "requirements-bigquery.txt",
        export=(
            "--frozen",
            "--no-default-groups",
            "--extra",
            "bigquery",
            "--no-emit-project",
        ),
        contexts={"dbt": "dbt"},
    ),
}
POSTGRES = re.compile(
    r"^(dbt-postgres|psycopg|psycopg2|psycopg2-binary|psycopg-binary|psycopg-c|psycopg-pool|asyncpg)$"
)
# What only a local build copies: the Airflow lab's TLC pipeline, and code or pins for the Postgres warehouse.
LOCAL_ONLY = {"tlc": "TLC", "postgres": "Postgres-only"}
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s;\\]+)")


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pins(path: Path) -> dict[str, str]:
    """Package name (normalised) to version, for every `name==version` line of a requirements file."""
    found = {}
    for line in path.read_text().splitlines():
        if m := PIN.match(line.strip()):
            found[normalise(m.group(1))] = m.group(2)
    return found


def names(path: Path) -> list[str]:
    """The package names a list file holds, one per line, `#` comments aside."""
    lines = (line.split("#", 1)[0].strip() for line in path.read_text().splitlines())
    return [normalise(line) for line in lines if line]


def body(text: str) -> str:
    """A requirements file less its leading comment header (uv's command line)."""
    lines = text.splitlines()
    while lines and lines[0].startswith("#"):
        lines.pop(0)
    return "\n".join(lines).strip()


def stale_export(ctx: Path, lock: str, args: tuple[str, ...]) -> str | None:
    """Why the lock differs from a fresh `uv export` of the context's uv.lock, or None."""
    uv = shutil.which("uv")
    if uv is None:
        return (
            "uv is missing, so the export cannot be checked against uv.lock: install uv"
        )
    result = subprocess.run(
        [uv, "export", "--quiet", "--no-header", *args],
        cwd=ctx,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return f"`uv export {' '.join(args)}` failed: {result.stderr.strip().splitlines()[-1:]}"
    if body(result.stdout) != body((ctx / lock).read_text()):
        return f"differs from `uv export {' '.join(args)}` of uv.lock: re-export it with `-o {lock}`"
    return None


@dataclass(frozen=True)
class Copy:
    source_from: str | None  # --from, if any
    sources: tuple[str, ...]
    excludes: tuple[str, ...]


def stages(dockerfile: Path) -> dict[str, tuple[str, list[Copy]]]:
    """Each named stage: the image or stage it is built on, and its COPY instructions."""
    text = re.sub(r"\\\n", " ", dockerfile.read_text())
    found: dict[str, tuple[str, list[Copy]]] = {}
    current: list[Copy] | None = None
    for line in text.splitlines():
        if m := re.match(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", line, re.IGNORECASE):
            current = []
            if m.group(2):
                found[m.group(2)] = (m.group(1), current)
        elif current is not None and line.startswith("COPY "):
            words = shlex.split(line)[1:]
            flags = [w for w in words if w.startswith("--")]
            paths = [w for w in words if not w.startswith("--")]
            source_from = next(
                (f.split("=", 1)[1] for f in flags if f.startswith("--from=")), None
            )
            excludes = tuple(
                f.split("=", 1)[1] for f in flags if f.startswith("--exclude=")
            )
            current.append(Copy(source_from, tuple(paths[:-1]), excludes))
    return found


def chain(found: dict[str, tuple[str, list[Copy]]], stage: str) -> list[str]:
    """The stage and the stages of the same Dockerfile it is built on, nearest first."""
    out = []
    while stage in found and stage not in out:
        out.append(stage)
        stage = found[stage][0]
    return out


def ignored(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    """Docker's matching, as far as these files use it: a pattern names a path or a directory above it."""
    parts = path.split("/")
    prefixes = ["/".join(parts[: i + 1]) for i in range(len(parts))]
    return any(
        fnmatch.fnmatch(p, pattern.rstrip("/"))
        for pattern in patterns
        for p in prefixes
    )


def copied(root: Path, build: Build) -> tuple[list[str], list[str]]:
    """The repo paths the build's stage copies from its contexts, and the problems in reading them."""
    ctx = root / build.context
    dockerignore = ctx / ".dockerignore"
    ignore = [
        line.strip()
        for line in (
            dockerignore.read_text().splitlines() if dockerignore.exists() else []
        )
        if line.strip() and not line.startswith("#")
    ]
    found = stages(ctx / "Dockerfile")
    if build.stage not in found:
        return [], [f"{build.context}/Dockerfile has no stage {build.stage}"]
    copies = [c for s in chain(found, build.stage) for c in found[s][1]]
    if not any(c.excludes for c in found[build.stage][1]):
        return [], [
            f"{build.context}/Dockerfile has no COPY --exclude in stage {build.stage}"
        ]
    paths = set()
    for c in copies:
        if c.source_from is None:
            base, context_ignore = ctx, ignore
        elif c.source_from in build.contexts:
            # A named context's .dockerignore is not read: walking more files can only find more.
            base, context_ignore = root / build.contexts[c.source_from], []
        else:
            continue  # another stage's output, checked where that stage installs it
        for source in c.sources:
            top = (base / source).resolve()
            files = (
                [top]
                if top.is_file()
                else sorted(f for f in top.rglob("*") if f.is_file())
            )
            for file in files:
                in_context = file.relative_to(base.resolve()).as_posix()
                in_source = (
                    file.name if top.is_file() else file.relative_to(top).as_posix()
                )
                if not ignored(in_context, context_ignore) and not ignored(
                    in_source, c.excludes
                ):
                    paths.add(file.relative_to(root.resolve()).as_posix())
    return sorted(paths), []


def problems(root: Path = ROOT) -> list[str]:
    found = []
    left_out = set(names(root / EXCLUDED))
    for image, build in BUILDS.items():
        ctx = root / build.context
        locked = pins(ctx / build.lock)
        where = f"{build.context}/{build.lock}"
        found += [
            f"{image}: {where} holds the Postgres package {n}"
            for n in locked
            if POSTGRES.match(n)
        ]
        found += [
            f"{image}: {where} holds {n}, which {EXCLUDED} leaves out"
            for n in locked
            if n in left_out
        ]
        if build.top:
            found += [
                f"{image}: {where} has {name}=={locked.get(name)}, not {build.top}'s {version}: recompile it"
                for name, version in pins(ctx / build.top).items()
                if locked.get(name) != version
            ]
        if build.export and (why := stale_export(ctx, build.lock, build.export)):
            found.append(f"{image}: {where} {why}")
        paths, unreadable = copied(root, build)
        found += [f"{image}: {p}" for p in unreadable]
        for path in paths:
            for word, label in LOCAL_ONLY.items():
                if word in path.lower():
                    found.append(
                        f"{image}: the {build.stage} build copies the {label} path {path}"
                    )
    return found


if __name__ == "__main__":
    out = problems()
    print(
        "\n".join(out)
        or f"gcp builds: {', '.join(BUILDS)} carry no Postgres package and no TLC or Postgres-only path,"
        " and their locks are current"
    )
    sys.exit(1 if out else 0)
