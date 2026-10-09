"""Deterministic synthetic sources: the same inputs always yield identical rows."""

from __future__ import annotations

import random
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import NamedTuple

from el_factory.model import Interval, Page, Table
from el_factory.sources.base import Entity, Fetch
from el_factory.sources.paging import paginate

SOURCE = "synthetic"
CUSTOMER_COUNT = 200
COUNTRIES = ("NL", "TR", "GB", "DE", "FR", "US")
FIRST_NAMES = ("Ada", "Bram", "Chen", "Dilara", "Elif", "Finn", "Gwen", "Hugo", "Ines", "Jan")
LAST_NAMES = ("de Jong", "Yilmaz", "Smith", "Mueller", "Dubois", "Kaya", "Brown", "Visser")
ORDER_STATUSES = ("placed", "shipped", "cancelled")
ORDER_STATUS_WEIGHTS = (70, 25, 5)

CUSTOMERS_TABLE = Table(
    "synthetic_customers",
    (
        ("customer_id", "integer"),
        ("name", "text"),
        ("email", "text"),
        ("country", "text"),
        ("signup_date", "date"),
    ),
)
ORDERS_TABLE = Table(
    "synthetic_orders",
    (
        ("order_id", "text"),
        ("customer_id", "integer"),
        ("order_ts", "timestamptz"),
        ("status", "text"),
        ("amount", "numeric(12,2)"),
        ("currency", "text"),
    ),
)


class _Order(NamedTuple):
    order_id: str
    customer_id: int
    order_ts: datetime
    status: str
    amount: Decimal
    currency: str


def entities(page_size: int) -> list[Entity]:
    customers = build_customers()
    return [
        Entity(SOURCE, "customers", CUSTOMERS_TABLE, _snapshot(customers, page_size)),
        Entity(SOURCE, "orders", ORDERS_TABLE, _orders(page_size)),
    ]


def _snapshot(rows: list[dict[str, object]], page_size: int) -> Fetch:
    def fetch(interval: Interval, cursor: int) -> Page:
        return paginate(rows, cursor, page_size)

    return fetch


def _orders(page_size: int) -> Fetch:
    def fetch(interval: Interval, cursor: int) -> Page:
        return paginate(build_orders(interval), cursor, page_size)

    return fetch


def build_customers() -> list[dict[str, object]]:
    rng = random.Random("customers")
    rows: list[dict[str, object]] = []
    for customer_id in range(1, CUSTOMER_COUNT + 1):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        signup = date(2025, 1, 1) + timedelta(days=rng.randint(0, 364))
        rows.append(
            {
                "customer_id": customer_id,
                "name": f"{first} {last}",
                "email": f"customer{customer_id}@example.com",
                "country": rng.choice(COUNTRIES),
                "signup_date": signup.isoformat(),
            }
        )
    return rows


def build_orders(interval: Interval) -> list[dict[str, object]]:
    """Orders with order_ts in [start, end), ordered by time then id.

    Each UTC day is generated from its own seed, so an order never depends on which
    interval asked for it.
    """
    orders: list[_Order] = []
    day = interval.start.astimezone(UTC).date()
    last_day = interval.end.astimezone(UTC).date()
    while day <= last_day:
        orders.extend(_day_orders(day))
        day += timedelta(days=1)
    kept = [o for o in orders if interval.start <= o.order_ts < interval.end]
    kept.sort(key=lambda o: (o.order_ts, o.order_id))
    return [_serialise(o) for o in kept]


def _day_orders(day: date) -> Sequence[_Order]:
    rng = random.Random(f"orders:{day.isoformat()}")
    midnight = datetime(day.year, day.month, day.day, tzinfo=UTC)
    count = 20 + rng.randint(0, 30)
    orders: list[_Order] = []
    for seq in range(1, count + 1):
        orders.append(
            _Order(
                order_id=f"O-{day:%Y%m%d}-{seq:04d}",
                customer_id=rng.randint(1, CUSTOMER_COUNT),
                order_ts=midnight + timedelta(seconds=rng.randint(0, 86_399)),
                status=rng.choices(ORDER_STATUSES, ORDER_STATUS_WEIGHTS)[0],
                amount=Decimal(rng.randint(500, 50_000)) / 100,
                currency="EUR",
            )
        )
    return orders


def _serialise(order: _Order) -> dict[str, object]:
    return {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "order_ts": order.order_ts.isoformat(),
        "status": order.status,
        "amount": f"{order.amount:.2f}",
        "currency": order.currency,
    }
