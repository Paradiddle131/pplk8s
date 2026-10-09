import pytest

from el_factory.config import Config, ConfigError


def test_defaults_apply_when_only_dsn_is_set():
    config = Config.from_env({"WAREHOUSE_DSN": "postgresql://w"})

    assert config.gcs_bucket == "staging"
    assert config.gcp_project == "pplk8s"
    assert config.page_size == 100
    assert config.fail_rate == 0.0
    assert config.storage_emulator_host is None
    assert config.port == 8080
    assert config.catalog_path.name == "catalog.yaml"


def test_dsn_is_required():
    with pytest.raises(ConfigError, match="WAREHOUSE_DSN"):
        Config.from_env({})


@pytest.mark.parametrize("value", ["1.5", "-0.1", "abc"])
def test_fail_rate_must_be_a_probability(value):
    with pytest.raises(ConfigError):
        Config.from_env({"WAREHOUSE_DSN": "postgresql://w", "FAIL_RATE": value})


def test_page_size_must_be_positive():
    with pytest.raises(ConfigError):
        Config.from_env({"WAREHOUSE_DSN": "postgresql://w", "PAGE_SIZE": "0"})
