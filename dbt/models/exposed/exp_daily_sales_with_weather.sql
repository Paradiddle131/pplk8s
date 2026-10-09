{{ config(alias='daily_sales_with_weather') }}

-- Toy example of combining data products: each day's sales with Amsterdam's weather for the same UTC date.
-- Days without an Amsterdam observation keep their sales and get NULL weather columns.
select
    s.order_date,
    s.orders_total,
    s.orders_cancelled,
    s.revenue_eur,
    s.customers_distinct,
    w.avg_temperature_c as amsterdam_avg_temperature_c,
    w.total_precipitation_mm as amsterdam_total_precipitation_mm
from {{ ref('gld_daily_sales') }} as s
left join {{ ref('gld_daily_weather') }} as w
    on w.date = s.order_date
   and w.location = 'Amsterdam'
