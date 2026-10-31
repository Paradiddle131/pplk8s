"""check_free_path.py on the real platform/gcp/ and on copies that stray off the free path."""

from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

import pytest

GCP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GCP))

from check_free_path import problems


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    shutil.copy(GCP / "free-path.yaml", tmp_path)
    (tmp_path / "infra").mkdir()
    for f in [*(GCP / "infra").glob("*.tf"), *(GCP / "infra").glob("*.yaml")]:
        shutil.copy(f, tmp_path / "infra")
    return tmp_path


def test_the_repo_is_on_the_free_path() -> None:
    assert problems(GCP) == []


def test_a_paid_resource_type_fails(copy: Path) -> None:
    (copy / "infra" / "vm.tf").write_text(
        'resource "google_compute_instance" "vm" {}\n'
    )
    assert any("google_compute_instance" in p for p in problems(copy))


def test_a_paid_api_fails(copy: Path) -> None:
    spec = copy / "free-path.yaml"
    spec.write_text(
        spec.read_text().replace(
            "apis:\n",
            "apis:\n  compute.googleapis.com: {enable: true, source: https://x}\n",
            1,
        )
    )
    assert any("paid list" in p for p in problems(copy))


def test_an_api_named_but_not_enabled_fails(copy: Path) -> None:
    (copy / "infra" / "run.tf").write_text(
        "# calls https://run.googleapis.com/v2/projects\n"
    )
    assert any("run.googleapis.com" in p for p in problems(copy))


def test_a_dated_exception_expires(copy: Path) -> None:
    spec = copy / "free-path.yaml"
    text = spec.read_text().replace(
        "geminidataanalytics.googleapis.com: {enable: false",
        "geminidataanalytics.googleapis.com: {enable: true",
    )
    spec.write_text(text)
    assert problems(copy, dt.date(2026, 12, 1)) == []
    assert any("free window" in p for p in problems(copy, dt.date(2027, 1, 1)))
