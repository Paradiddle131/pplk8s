from google.api_core.exceptions import Forbidden, NotFound
from pplk8s.emulator_logging import EmulatorGCSRemoteLogIO


def test_emulator_not_found_counts_as_missing_log():
    # fake-gcs's 404 body says "Not Found", not real GCS's "No such object".
    assert EmulatorGCSRemoteLogIO.no_log_found(NotFound("GET .../o/x?alt=media: Not Found"))


def test_real_gcs_wording_still_counts_as_missing_log():
    assert EmulatorGCSRemoteLogIO.no_log_found(Exception("No such object: airflow-logs/x"))


def test_other_read_failures_still_refuse_to_overwrite():
    assert not EmulatorGCSRemoteLogIO.no_log_found(Forbidden("denied"))
