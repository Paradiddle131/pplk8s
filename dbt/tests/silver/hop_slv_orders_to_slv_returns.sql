{{ config(tags=['silver', 'returns']) }}

-- Silver orders -> silver returns (semantic/PLAN.md SL-9): per customer, the returned amounts reached through
-- each return's order in silver.orders equal those silver.returns records under its own customer_id, so a
-- return counts for its order's customer, the path revenue takes, and net revenue by country adds up.
{% set upstream %}
    select o.customer_id, sum(r.amount) as amount
    from {{ ref('slv_returns') }} as r
    left join {{ ref('slv_orders') }} as o
        on o.order_id = r.order_id
    group by o.customer_id
{% endset %}

{% set downstream %}
    select customer_id, sum(amount) as amount
    from {{ ref('slv_returns') }}
    group by customer_id
{% endset %}

{{ hop_mismatches('silver orders -> returns customer', upstream, downstream, ['customer_id'], ['amount']) }}
