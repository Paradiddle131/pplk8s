from airflow.providers.google.cloud.log.gcs_task_handler import GCSRemoteLogIO
from google.api_core.exceptions import Forbidden, NotFound
from pplk8s.emulator_logging import EmulatorGCSRemoteLogIO, _emulator_io


def test_emulator_not_found_counts_as_missing_log():
    # fake-gcs's 404 body says "Not Found", not real GCS's "No such object".
    assert EmulatorGCSRemoteLogIO.no_log_found(NotFound("GET .../o/x?alt=media: Not Found"))


def test_real_gcs_wording_still_counts_as_missing_log():
    assert EmulatorGCSRemoteLogIO.no_log_found(Exception("No such object: airflow-logs/x"))


def test_other_read_failures_still_refuse_to_overwrite():
    assert not EmulatorGCSRemoteLogIO.no_log_found(Forbidden("denied"))


def test_default_io_is_rebuilt_field_for_field():
    default = GCSRemoteLogIO(
        remote_base="gs://airflow-logs",
        base_log_folder="/opt/airflow/logs",
        delete_local_copy=False,
    )
    io = _emulator_io(default)
    assert type(io) is EmulatorGCSRemoteLogIO
    assert (io.remote_base, str(io.base_log_folder)) == ("gs://airflow-logs", "/opt/airflow/logs")


def test_no_remote_logging_is_left_alone():
    assert _emulator_io(None) is None
