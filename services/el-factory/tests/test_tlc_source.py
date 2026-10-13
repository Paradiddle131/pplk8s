from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from el_factory.errors import BadRequest, UpstreamError
from el_factory.model import Interval
from el_factory.remote_file import FileChanged, NotPublished, RangeReader, head
from el_factory.sources.tlc import (
    BIGINT,
    DOUBLE,
    INTEGER,
    SchemaConflict,
    chunk_span,
    data_month,
    plan_columns,
)
from tests.tlc_fixtures import TlcServer, yellow_2023, yellow_2025

OCT = datetime(2025, 10, 1)


@pytest.fixture
def server():
    tlc = TlcServer()
    yield tlc
    tlc.close()


def schema(**fields: pa.DataType) -> pa.Schema:
    return pa.schema(list(fields.items()))


def test_data_month_accepts_exactly_one_calendar_month():
    december = Interval(datetime(2025, 12, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC))
    assert data_month(december) == "2025-12"
    for start, end in [
        (datetime(2025, 12, 2, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
        (datetime(2025, 12, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC)),
    ]:
        with pytest.raises(BadRequest):
            data_month(Interval(start, end))


def test_a_new_table_takes_every_typed_column_lower_cased():
    plan = plan_columns(
        schema(VendorID=pa.int32(), Airport_fee=pa.float64(), ehail_fee=pa.null()), {}
    )
    assert plan.columns == (("vendorid", INTEGER), ("airport_fee", DOUBLE))
    assert plan.add == plan.columns
    assert plan.widen == ()


def test_numeric_columns_widen_and_never_narrow():
    existing = {"vendorid": INTEGER, "passenger_count": BIGINT, "total_amount": DOUBLE}
    plan = plan_columns(
        schema(VendorID=pa.int64(), passenger_count=pa.float64(), total_amount=pa.int32()),
        existing,
    )
    assert plan.widen == (("vendorid", BIGINT), ("passenger_count", DOUBLE))
    assert plan.add == ()


def test_any_other_type_change_is_refused_without_retry():
    with pytest.raises(SchemaConflict) as raised:
        plan_columns(schema(store_and_fwd_flag=pa.int64()), {"store_and_fwd_flag": "text"})
    assert raised.value.status == 502
    assert raised.value.retryable is False


def test_columns_that_collide_when_lower_cased_are_refused():
    with pytest.raises(SchemaConflict):
        plan_columns(schema(Airport_fee=pa.float64(), airport_fee=pa.float64()), {})


def test_a_row_group_is_read_with_one_ranged_get(server):
    url = server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(12, 4, OCT))
    reader = RangeReader(head(url))
    parquet = pq.ParquetFile(reader)
    assert parquet.metadata.num_row_groups == 3

    before = reader.requests
    reader.prefetch(*chunk_span(parquet.metadata, 1))
    table = parquet.read_row_group(1)

    assert reader.requests == before + 1
    assert table.num_rows == 4
    assert table.column("PULocationID").to_pylist() == [204, 205, 206, 207]


def test_a_file_republished_mid_read_fails_retryably(server):
    url = server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(12, 4, OCT))
    reader = RangeReader(head(url))
    server.publish("yellow_tripdata_2025-10.parquet", yellow_2023(12, 4, OCT))

    with pytest.raises(FileChanged) as raised:
        pq.ParquetFile(reader)
    assert raised.value.retryable is True


def test_s3_access_denied_means_not_published(server):
    with pytest.raises(NotPublished) as raised:
        head(f"{server.base_url}/yellow_tripdata_2099-01.parquet")
    assert raised.value.retryable is False
    assert raised.value.extra == {"published": False}


def test_a_cdn_block_is_retryable_not_unpublished(server):
    url = server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(4, 4, OCT))
    server.blocked = True

    with pytest.raises(UpstreamError) as raised:
        head(url)
    assert not isinstance(raised.value, NotPublished)
    assert raised.value.retryable is True
