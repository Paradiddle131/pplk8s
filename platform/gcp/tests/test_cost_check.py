"""cost-check.sh against a fake `bq` on PATH: how it reads each answer bq can give (#271)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "cost-check.sh"
TABLE = "gcp_billing_export_v1_000000_000000_000000"
HEADER = "service,sku,net,month_total,exported_until"


def fake_bq(tmp_path: Path, ls: str, query: str = "") -> Path:
    """A `bq` whose `ls` and `query` run the given shell snippets."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    bq = bindir / "bq"
    bq.write_text(
        "#!/usr/bin/env bash\n"
        'case "$1" in\n'
        f"  ls) {ls} ;;\n"
        f"  query) {query or 'exit 99'} ;;\n"
        "esac\n"
    )
    bq.chmod(0o755)
    return bindir


def run(bindir: Path) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "GCP_PROJECT": "lab-test",
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def test_a_crashing_bq_is_reported_as_itself(tmp_path: Path) -> None:
    bindir = fake_bq(
        tmp_path,
        "echo \"AttributeError: module 'absl.flags' has no attribute 'FLAGS'\" >&2; exit 1",
    )
    r = run(bindir)
    assert r.returncode == 3
    assert "UNKNOWN: bq failed:" in r.stderr
    assert "absl.flags" in r.stderr
    assert "table" not in r.stderr


def test_bq_errors_on_stdout_are_reported(tmp_path: Path) -> None:
    bindir = fake_bq(
        tmp_path,
        "echo 'BigQuery error in ls operation: Access Denied: Dataset lab-test:billing_export'; exit 2",
    )
    r = run(bindir)
    assert r.returncode == 3
    assert "bq failed: BigQuery error in ls operation: Access Denied" in r.stderr


def test_a_missing_dataset_is_the_no_export_case(tmp_path: Path) -> None:
    bindir = fake_bq(
        tmp_path,
        "echo 'BigQuery error in ls operation: Not found: Dataset lab-test:billing_export'; exit 2",
    )
    r = run(bindir)
    assert r.returncode == 3
    assert "no gcp_billing_export_v1_* table in lab-test:billing_export yet" in r.stderr


@pytest.mark.parametrize(
    "listing", ["", "[]", '[{"tableReference": {"tableId": "other"}}]']
)
def test_no_export_table_yet(tmp_path: Path, listing: str) -> None:
    bindir = fake_bq(tmp_path, f"echo '{listing}'")
    r = run(bindir)
    assert r.returncode == 3
    assert "table in lab-test:billing_export yet" in r.stderr


def listing() -> str:
    return f'echo \'[{{"tableReference": {{"tableId": "{TABLE}"}}}}]\''


def test_zero_cost_passes(tmp_path: Path) -> None:
    rows = f"{HEADER}\\nBigQuery,Analysis,0.000000,0.00,2026-11-01T10:00Z"
    bindir = fake_bq(tmp_path, listing(), f"printf '{rows}\\n'")
    r = run(bindir)
    assert r.returncode == 0, r.stderr
    assert "has cost $0.00" in r.stdout


def test_any_cost_fails(tmp_path: Path) -> None:
    rows = f"{HEADER}\\nBigQuery,Analysis,0.000100,0.00,2026-11-01T10:00Z"
    bindir = fake_bq(tmp_path, listing(), f"printf '{rows}\\n'")
    r = run(bindir)
    assert r.returncode == 1
    assert "BigQuery / Analysis" in r.stderr


def test_a_failed_query_is_unknown(tmp_path: Path) -> None:
    bindir = fake_bq(tmp_path, listing(), "exit 1")
    r = run(bindir)
    assert r.returncode == 3
    assert "query failed" in r.stderr
