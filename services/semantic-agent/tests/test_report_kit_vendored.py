"""The vendored report kit matches its manifest, so changes go upstream and never into the copy."""

import hashlib
from pathlib import Path

KIT = Path(__file__).resolve().parents[3] / "docs/research/semantic-bet/report-kit"
OWN = {"SOURCE.md", "MANIFEST.sha256"}


def manifest():
    out = {}
    for line in (KIT / "MANIFEST.sha256").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        out[name.lstrip("*")] = digest
    return out


def test_every_vendored_file_matches_the_manifest():
    listed = manifest()
    assert listed, "the manifest lists the vendored files"
    changed = [
        name
        for name, digest in listed.items()
        if not (KIT / name).is_file() or hashlib.sha256((KIT / name).read_bytes()).hexdigest() != digest
    ]
    assert not changed, f"vendored files that differ from MANIFEST.sha256 (change them upstream): {changed}"


def test_no_file_sits_in_the_copy_without_a_manifest_line():
    on_disk = {str(p.relative_to(KIT)) for p in KIT.rglob("*") if p.is_file()} - OWN
    assert on_disk == set(manifest()), sorted(on_disk ^ set(manifest()))
