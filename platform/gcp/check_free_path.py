"""Fail when platform/gcp/ reaches beyond the free path (semantic/PLAN.md SL-13), offline.

Checks, against free-path.yaml:
- every API listed has an https source and is not on its `paid` list;
- an API past its `until` date is not enabled;
- every resource type the OpenTofu root declares is listed, and its API is enabled;
- every `*.googleapis.com` host the root names (resources, workflow sources) is an enabled API.

Usage: python platform/gcp/check_free_path.py [gcp dir]; run by `make gcp-validate`.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import yaml

RESOURCE = re.compile(r'^\s*resource\s+"([a-z0-9_]+)"', re.MULTILINE)
HOST = re.compile(r"\b([a-z0-9-]+\.googleapis\.com)\b")


def problems(gcp: Path, today: dt.date | None = None) -> list[str]:
    today = today or dt.datetime.now(dt.UTC).date()
    spec = yaml.safe_load((gcp / "free-path.yaml").read_text())
    apis: dict[str, dict] = spec.get("apis") or {}
    resources: dict[str, str] = spec.get("resources") or {}
    paid = set(spec.get("paid") or [])
    out: list[str] = []

    for name, api in apis.items():
        if name in paid:
            out.append(f"{name}: on the paid list, so it cannot be on the free path")
        if not str(api.get("source", "")).startswith("https://"):
            out.append(f"{name}: no https source for its free tier")
        until = api.get("until")
        if until and api.get("enable") and today > dt.date.fromisoformat(str(until)):
            out.append(f"{name}: enabled past its free window ({until})")
    enabled = {name for name, api in apis.items() if api.get("enable")}

    infra = gcp / "infra"
    for path in sorted([*infra.glob("*.tf"), *infra.glob("*.yaml")]):
        text = path.read_text()
        for kind in RESOURCE.findall(text):
            api = resources.get(kind)
            if api is None:
                out.append(f"{path.name}: resource type {kind} is not on the free path")
            elif api not in enabled:
                out.append(f"{path.name}: {kind} needs {api}, which is not enabled")
        for host in HOST.findall(text):
            if host not in enabled:
                out.append(
                    f"{path.name}: names {host}, which is not an enabled free-path API"
                )
    return out


def main() -> int:
    gcp = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    found = problems(gcp)
    for p in found:
        print(f"free path: {p}", file=sys.stderr)
    if not found:
        print("free path: every API and resource type is on the allowlist")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
