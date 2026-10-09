import os
import tempfile

_home = tempfile.mkdtemp(prefix="airflow-test-")
os.environ.setdefault("AIRFLOW_HOME", _home)
os.environ.setdefault("AIRFLOW__CORE__LOAD_EXAMPLES", "False")
os.environ.setdefault("AIRFLOW__CORE__UNIT_TEST_MODE", "True")
os.environ.setdefault("AIRFLOW__DATABASE__SQL_ALCHEMY_CONN", f"sqlite:///{_home}/airflow.db")
os.environ["AIRFLOW_CONN_EL_FACTORY"] = "http://el-factory.test:80"
os.environ.setdefault(
    "AIRFLOW_CONN_WAREHOUSE", "postgres://warehouse:warehouse@localhost:5433/warehouse"
)
