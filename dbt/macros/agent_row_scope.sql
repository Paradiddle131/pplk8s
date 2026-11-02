-- Row scopes for agent identities: the stand-in for BigQuery row access policies (semantic/PLAN.md SL-21).
-- A scoped role, listed in ops.agent_scopes with its countries, reads only those countries' customers and
-- the orders and returns of those customers; every other role reads every row, and the tables' owner (the
-- dbt user, which builds gold from silver) is never subject to a policy.
-- The rule of each scoped silver model is below; ops.agent_countries(role) is the scope a role has (null
-- when it has none), created with the roles by agent_warehouse.
-- dbt rebuilds a table on every run and a policy goes with the old one, so each scoped model re-applies its
-- rule as a post-hook; agent_warehouse applies the rules to the tables that already exist, so the order in
-- which the two first run does not matter.

{% macro agent_row_scopes() -%}
  {#- silver.customers by schema and alias (generate_schema_name keeps the custom schema verbatim): a
      policy's subquery runs under the reader's own policy on customers, so an order is visible exactly
      when its customer is; MetricFlow joins dimensions with a left outer join, so a policy on customers
      alone would leave every order counted with a null country. -#}
  {% set visible_customer = "customer_id in (select customer_id from silver.customers)" %}
  {{ return({
    "slv_customers": "country = any(ops.agent_countries(current_user))",
    "slv_orders": visible_customer,
    "slv_returns": visible_customer,
  }) }}
{%- endmacro %}

-- The post-hook of a scoped model: `post_hook="{{ agent_row_scope() }}"`.
{% macro agent_row_scope() -%}
  {{ return(adapter.dispatch("agent_row_scope")(this, agent_row_scopes()[model.name])) }}
{%- endmacro %}

-- Postgres: row level security with one select policy for every role. Skipped until agent_warehouse has
-- created ops.agent_countries, which then applies it to the table itself.
{% macro default__agent_row_scope(relation, rule) -%}
do $scope$
begin
  if to_regprocedure('ops.agent_countries(name)') is not null then
    execute $ddl$
      alter table {{ relation }} enable row level security;
      drop policy if exists agent_scope on {{ relation }};
      create policy agent_scope on {{ relation }} for select
        using (ops.agent_countries(current_user) is null or {{ rule }});
    $ddl$;
  end if;
end
$scope$
{%- endmacro %}

-- BigQuery: dbt-bigquery has no row policy config; a post-hook running CREATE ROW ACCESS POLICY is the
-- counterpart (docs/semantic-layer-on-bigquery.md), which the lab leaves out with the agents' IAM identities.
{% macro bigquery__agent_row_scope(relation, rule) -%}
{%- endmacro %}
