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


def run(bindir: Path, **extra: str) -> subprocess.CompletedProcess[str]:
    """The script with the fake bq first on PATH; the tolerance is its default unless `extra` sets it."""
    env = {k: v for k, v in os.environ.items() if k != "GCP_COST_TOLERANCE_USD"}
    env |= {
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "GCP_PROJECT": "lab-test",
        **extra,
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


def cost_rows(*lines: str) -> str:
    return "\\n".join([HEADER, *lines])


def test_a_cost_under_the_accepted_tolerance_passes_and_is_listed(
    tmp_path: Path,
) -> None:
    """The owner accepts incidental charges under $1.00 a month (#338): the check passes but names them."""
    rows = cost_rows(
        "Artifact Registry,Network Internet Egress Intercontinental,0.000010,0.00,2026-11-03T01:12Z",
        "BigQuery,Analysis,0.000000,0.00,2026-11-03T01:12Z",
    )
    bindir = fake_bq(tmp_path, listing(), f"printf '{rows}\\n'")
    r = run(bindir)
    assert r.returncode == 0, r.stderr
    assert (
        "ok: lab-test has cost $0.000010 this month, under the accepted $1.00"
        in r.stdout
    )
    assert "Artifact Registry / Network Internet Egress Intercontinental" in r.stdout
    assert "BigQuery / Analysis" not in r.stdout


def test_a_cost_at_the_tolerance_fails(tmp_path: Path) -> None:
    """The tolerance is on the month's total, not per SKU: two small lines that reach it stop the work."""
    rows = cost_rows(
        "Cloud Run,CPU,0.600000,1.00,2026-11-01T10:00Z",
        "BigQuery,Analysis,0.400000,1.00,2026-11-01T10:00Z",
    )
    bindir = fake_bq(tmp_path, listing(), f"printf '{rows}\\n'")
    r = run(bindir)
    assert r.returncode == 1
    assert (
        "FAIL: lab-test has cost $1.000000 this month, at or above the accepted $1.00"
        in r.stderr
    )
    assert "Cloud Run / CPU" in r.stderr and "BigQuery / Analysis" in r.stderr


def test_a_zero_tolerance_is_the_strict_rule(tmp_path: Path) -> None:
    rows = cost_rows("BigQuery,Analysis,0.000100,0.00,2026-11-01T10:00Z")
    bindir = fake_bq(tmp_path, listing(), f"printf '{rows}\\n'")
    r = run(bindir, GCP_COST_TOLERANCE_USD="0")
    assert r.returncode == 1
    assert "BigQuery / Analysis" in r.stderr


def test_credits_that_net_a_cost_to_zero_pass_as_zero(tmp_path: Path) -> None:
    rows = cost_rows("BigQuery,Analysis,0.000000,0.00,2026-11-01T10:00Z")
    bindir = fake_bq(tmp_path, listing(), f"printf '{rows}\\n'")
    r = run(bindir, GCP_COST_TOLERANCE_USD="0")
    assert r.returncode == 0, r.stderr
    assert "has cost $0.00" in r.stdout


def test_a_malformed_tolerance_is_refused(tmp_path: Path) -> None:
    rows = cost_rows("BigQuery,Analysis,0.000000,0.00,2026-11-01T10:00Z")
    bindir = fake_bq(tmp_path, listing(), f"printf '{rows}\\n'")
    r = run(bindir, GCP_COST_TOLERANCE_USD="lots")
    assert r.returncode == 3
    assert "GCP_COST_TOLERANCE_USD" in r.stderr


def test_a_failed_query_is_unknown(tmp_path: Path) -> None:
    bindir = fake_bq(tmp_path, listing(), "echo 'BigQuery error: boom'; exit 1")
    r = run(bindir)
    assert r.returncode == 3
    assert "the billing export query failed: BigQuery error: boom" in r.stderr
    assert "fence" not in r.stderr


# The error bq gave on 2026-11-03 once the fence was spent (#369); the quoted middle is from the issue, the
# "BigQuery error in query operation" prefix and the tail are bq's usual framing around it.
SPENT = (
    "BigQuery error in query operation: Error processing job 'lab-test:bqjob_r1': "
    "Custom quota exceeded: Your usage exceeded the custom quota for {quota}, "
    "which is set by your administrator. For more information, see "
    "https://cloud.google.com/bigquery/cost-controls"
)


@pytest.mark.parametrize("quota", ["QueryUsagePerDay", "QueryUsagePerUserPerDay"])
@pytest.mark.parametrize("stream", ["", " >&2"])
def test_a_spent_daily_fence_is_named(tmp_path: Path, quota: str, stream: str) -> None:
    """The cost check's own query is refused by a spent fence: wait for the reset, the export is fine (#369)."""
    bindir = fake_bq(
        tmp_path, listing(), f'echo "{SPENT.format(quota=quota)}"{stream}; exit 2'
    )
    r = run(bindir)
    assert r.returncode == 3
    assert f"UNKNOWN: BigQuery's daily query fence ({quota}," in r.stderr
    assert "wait for its reset at 00:00 Pacific" in r.stderr
    assert "query failed" not in r.stderr


@pytest.mark.parametrize("output", ["", HEADER])
def test_no_rows_this_month_is_unknown(tmp_path: Path, output: str) -> None:
    """An export table with no rows for the project this month proves nothing yet (the export's lag)."""
    bindir = fake_bq(tmp_path, listing(), f"printf '{output}\\n'")
    r = run(bindir)
    assert r.returncode == 3, r.stdout
    assert "UNKNOWN: no billing export rows for lab-test this month yet" in r.stderr
    assert "$0.00" not in r.stdout
